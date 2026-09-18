"""Async client and response normalisation for the private OcuMow API."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Final

from aiohttp import ClientError, ClientResponse, ClientSession, WSMsgType

from .const import (
    API_DEVICE_INFO_PATH,
    API_DEVICE_LIST_PATH,
    API_DEVICE_PROPERTIES_PATH,
    API_LOGIN_PATH,
    API_SUB_DEVICE_LIST_PATH,
    API_USER_DOMAIN,
    API_USER_DOMAIN_SECRET,
    COMMAND_MESSAGE_IDS,
    DEFAULT_API_BASE_URL,
    DEFAULT_WEBSOCKET_URL,
    DEVICE_LIVE_PROPERTIES,
    DEVICE_STATISTIC_PROPERTIES,
    RESET_DATA_MESSAGE_ID,
)


class OcuMowError(Exception):
    """Base error for the OcuMow client."""


class OcuMowAuthError(OcuMowError):
    """Authentication failed."""


class OcuMowConnectionError(OcuMowError):
    """The cloud service could not be reached."""


class OcuMowApiError(OcuMowError):
    """The cloud service returned an unexpected response."""


TOKEN_KEYS: Final = (
    "accessToken",
    "access_token",
    "token",
    "jwtToken",
    "idToken",
)

AUTH_ERROR_CODES: Final = {
    "400",
    "401",
    "403",
    "1001",
    "1002",
    "40014",
}

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class OcuMowDevice:
    """Normalised mower data used by Home Assistant entities."""

    device_id: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, *keys: str) -> Any:
        """Return the first property matching any key, case-insensitively."""
        lowered = {
            str(key).casefold(): value
            for source in (self.raw, self.properties)
            for key, value in source.items()
        }
        for key in keys:
            if key.casefold() in lowered:
                return unwrap_value(lowered[key.casefold()])
        return None


class OcuMowApi:
    """Small client for the endpoints identified in the Android app."""

    def __init__(
        self,
        session: ClientSession,
        email: str,
        password: str,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        websocket_url: str = DEFAULT_WEBSOCKET_URL,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._websocket_url = websocket_url
        self._access_token: str | None = None
        self._command_device_key: str | None = None
        self._command_product_key: str | None = None

    async def async_login(self) -> None:
        """Authenticate using the endpoint and field names found in the APK."""
        response = await self._async_request(
            "POST",
            API_LOGIN_PATH,
            json=build_login_payload(self._email, self._password),
            authenticated=False,
        )
        token = find_first_key(response, TOKEN_KEYS)
        if not isinstance(token, str) or not token:
            raise OcuMowAuthError("Login response did not contain an access token")
        self._access_token = token

    async def async_get_device(self, device_id: str, name: str) -> OcuMowDevice:
        """Fetch and normalise one mower's current state."""
        if self._access_token is None:
            await self.async_login()

        response = await self._async_request(
            "GET", API_DEVICE_INFO_PATH, params={"deviceId": device_id}
        )
        payload = unwrap_envelope(response)
        if not isinstance(payload, dict):
            raise OcuMowApiError("Device response did not contain an object")

        properties = extract_properties(payload)
        raw = dict(payload)
        statistics_device_id = device_id

        try:
            sub_devices_response = await self._async_request(
                "GET",
                API_SUB_DEVICE_LIST_PATH,
                params={
                    "gateWayDeviceId": device_id,
                    "pageNum": 1,
                    "pageSize": 10,
                    "tslPropertiesCodeStr": ",".join(
                        (*DEVICE_LIVE_PROPERTIES, *DEVICE_STATISTIC_PROPERTIES)
                    ),
                },
            )
        except OcuMowApiError:
            pass
        else:
            rows = find_first_key(sub_devices_response, ("rows",))
            if isinstance(rows, list):
                sub_device = next(
                    (item for item in rows if isinstance(item, dict)), None
                )
                if sub_device is not None:
                    raw["subDevice"] = sub_device
                    properties.update(extract_properties(sub_device))
                    for timestamp_key in (
                        "tsLastOnlineTime",
                        "tsLastOfflineTime",
                    ):
                        timestamp_value = find_first_key(
                            sub_device, (timestamp_key,)
                        )
                        if timestamp_value is not None:
                            properties[timestamp_key] = timestamp_value
                    sub_device_id = find_first_key(sub_device, ("deviceId",))
                    if sub_device_id is not None:
                        statistics_device_id = str(sub_device_id)
                    device_key = find_first_key(sub_device, ("deviceKey",))
                    product_key = find_first_key(sub_device, ("productKey",))
                    if device_key is not None and product_key is not None:
                        self._command_device_key = str(device_key)
                        self._command_product_key = str(product_key)

        try:
            statistics_response = await self._async_request(
                "GET",
                API_DEVICE_PROPERTIES_PATH,
                params={
                    "deviceId": statistics_device_id,
                    "tslPropertiesCodeStr": ",".join(DEVICE_STATISTIC_PROPERTIES),
                },
            )
        except OcuMowApiError:
            # Some gateway firmware versions do not expose this optional
            # endpoint. Keep the basic device record usable when they do not.
            pass
        else:
            statistics = extract_properties(statistics_response)
            properties.update(statistics)
        discovered_name = find_first_key(payload, ("deviceName", "name", "productName"))
        return OcuMowDevice(
            device_id=device_id,
            name=str(discovered_name or name),
            properties=properties,
            raw=raw,
        )

    async def async_send_command(self, command: str) -> None:
        """Send a mower command using the WebSocket payload used by the app."""
        message_id = COMMAND_MESSAGE_IDS.get(command)
        if message_id is None:
            raise OcuMowApiError(f"Unsupported mower command: {command}")

        await self._async_send_attribute(
            message_id=message_id,
            attribute_id=30,
            name="Command",
            attribute_type="ENUM",
            value=command,
        )

    async def async_reset_blade_time(self) -> None:
        """Send the ClearData command used by the app's blade-time reset."""
        await self._async_send_attribute(
            message_id=RESET_DATA_MESSAGE_ID,
            attribute_id=28,
            name="ClearData",
            attribute_type="BOOL",
            value="true",
        )

    async def _async_send_attribute(
        self,
        *,
        message_id: int,
        attribute_id: int,
        name: str,
        attribute_type: str,
        value: str,
    ) -> None:
        """Send one thing-model attribute using the app's WebSocket format."""
        if self._command_device_key is None or self._command_product_key is None:
            raise OcuMowApiError("Mower command details have not been discovered")

        target = {
            "productKey": self._command_product_key,
            "deviceKey": self._command_device_key,
        }
        subscription = {
            "cmd": "subscribe",
            "data": [
                {
                    **target,
                    "messageType": [
                        "ONLINE",
                        "STATUS",
                        "MATTR-REPORT",
                        "MEVENT-INFO",
                        "MEVENT-WARN",
                        "MEVENT-ERROR",
                        "LOCATION-INFO-KV",
                    ],
                }
            ],
        }
        attribute = {
            "id": attribute_id,
            "name": name,
            "type": attribute_type,
            "value": value,
        }
        request = {
            "cmd": "send",
            "data": {
                **target,
                "type": "WRITE-ATTR",
                "msgId": message_id,
                # The Android app sends this array encoded as a JSON string.
                "kv": json.dumps([attribute], separators=(",", ":")),
            },
        }

        try:
            async with self._session.ws_connect(self._websocket_url) as websocket:
                await websocket.send_json(subscription)
                # The app sends commands over a long-lived, already-subscribed
                # socket. Wait for the cloud to acknowledge our fresh
                # subscription before sending anything to the mower.
                await self._async_wait_for_websocket(
                    websocket, timeout=3, response_required=False
                )
                # Match JSONObject.toString() from the Android app exactly.
                await websocket.send_str(json.dumps(request, separators=(",", ":")))
                # Allow the cloud to acknowledge or reject the write before
                # closing the short-lived Home Assistant connection.
                await self._async_wait_for_websocket(
                    websocket, timeout=5, response_required=True
                )
        except (ClientError, TimeoutError) as err:
            raise OcuMowConnectionError(str(err)) from err

    async def _async_wait_for_websocket(
        self,
        websocket,
        *,
        timeout: float,
        response_required: bool,
    ) -> None:
        """Wait for a WebSocket reply and expose command failures."""
        try:
            message = await websocket.receive(timeout=timeout)
        except asyncio.TimeoutError:
            if response_required:
                raise OcuMowApiError(
                    "The OcuMow cloud did not acknowledge the mower command"
                )
            return

        if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
            detail = websocket.exception() or "WebSocket closed unexpectedly"
            raise OcuMowConnectionError(str(detail))
        if message.type != WSMsgType.TEXT:
            return

        try:
            response = json.loads(message.data)
        except (TypeError, ValueError):
            _LOGGER.debug("OcuMow WebSocket returned a non-JSON response")
            return
        if not isinstance(response, dict):
            return

        code = response.get("code", response.get("errorCode"))
        message_text = response.get("message", response.get("msg"))
        _LOGGER.info(
            "OcuMow WebSocket response: cmd=%s type=%s code=%s message=%s",
            response.get("cmd"),
            response.get("type"),
            code,
            message_text,
        )
        if code not in (None, 0, "0", 200, "200", "SUCCESS", "success"):
            raise OcuMowApiError(
                f"Mower rejected the command: {message_text or 'unknown error'} "
                f"(code {code})"
            )

    async def async_get_devices(self) -> list[OcuMowDevice]:
        """Return the mowers associated with the logged-in account."""
        if self._access_token is None:
            await self.async_login()

        response = await self._async_request(
            "GET",
            API_DEVICE_LIST_PATH,
            params={"accessTypeStr": "1", "pageNum": 1, "pageSize": 100},
        )
        return extract_devices(response)

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en-US",
            "Content-Type": "application/json; charset=UTF-8",
        }
        if authenticated and self._access_token:
            # OcuMow 1.3.15 sends the access token verbatim in this header.
            headers["token"] = self._access_token
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                headers=headers,
                **kwargs,
            ) as response:
                return await self._decode_response(response)
        except OcuMowError:
            raise
        except (ClientError, TimeoutError) as err:
            raise OcuMowConnectionError(str(err)) from err

    async def _decode_response(self, response: ClientResponse) -> dict[str, Any]:
        if response.status in (401, 403):
            raise OcuMowAuthError("Invalid OcuMow credentials or expired token")
        if response.status >= 400:
            body = (await response.text())[:300]
            raise OcuMowApiError(f"HTTP {response.status}: {body}")
        try:
            result = await response.json(content_type=None)
        except (ValueError, ClientError) as err:
            raise OcuMowApiError("The service did not return JSON") from err
        if not isinstance(result, dict):
            raise OcuMowApiError("The service returned an unexpected JSON value")

        code = result.get("code", result.get("errorCode"))
        if code not in (None, 0, "0", 200, "200", "SUCCESS", "success"):
            message = result.get("message", result.get("msg", "API request failed"))
            if str(code) in AUTH_ERROR_CODES:
                raise OcuMowAuthError(str(message))
            raise OcuMowApiError(f"{message} (code {code})")
        return result


def build_login_payload(email: str, password: str) -> dict[str, str]:
    """Build the signed email-login body used by OcuMow Android 1.3.15."""
    signature = sha256(
        f"{email}{password}{API_USER_DOMAIN_SECRET}".encode()
    ).hexdigest()
    return {
        "email": email,
        "pwd": password,
        "signature": signature,
        "userDomain": API_USER_DOMAIN,
    }


def extract_devices(payload: dict[str, Any]) -> list[OcuMowDevice]:
    """Extract account devices from the paginated response used by the app."""
    rows = find_first_key(payload, ("rows",))
    if not isinstance(rows, list):
        return []

    devices: list[OcuMowDevice] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        device_id = find_first_key(row, ("deviceId",))
        if device_id is None:
            continue
        name = find_first_key(row, ("deviceName", "name", "productName"))
        devices.append(
            OcuMowDevice(
                device_id=str(device_id),
                name=str(name or f"OcuMow {device_id}"),
                raw=row,
            )
        )
    return devices


def unwrap_envelope(value: Any) -> Any:
    """Unwrap common API response envelopes without losing valid objects."""
    current = value
    for _ in range(4):
        if not isinstance(current, dict):
            break
        next_value = None
        for key in ("data", "result", "object", "deviceInfo"):
            candidate = current.get(key)
            if isinstance(candidate, (dict, list)):
                next_value = candidate
                break
        if next_value is None:
            break
        current = next_value
    return current


def unwrap_value(value: Any) -> Any:
    """Extract a scalar from a thing-model property wrapper."""
    if isinstance(value, dict):
        for key in ("value", "val", "propertyValue", "data", "token"):
            if key in value:
                return unwrap_value(value[key])
    return value


def find_first_key(value: Any, keys: tuple[str, ...]) -> Any:
    """Recursively find the first occurrence of one of the supplied keys."""
    wanted = {key.casefold() for key in keys}
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in wanted:
                return unwrap_value(item)
        for item in value.values():
            found = find_first_key(item, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_first_key(item, keys)
            if found is not None:
                return found
    return None


def extract_properties(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract named Quectel thing-model properties from varying envelopes."""
    for key in (
        "properties",
        "property",
        "propertyList",
        "tslProperties",
        "thingModel",
        "deviceData",
        "statusData",
        "data",
    ):
        candidate = find_first_key(payload, (key,))
        if isinstance(candidate, dict):
            return candidate
        if isinstance(candidate, list):
            converted: dict[str, Any] = {}
            for item in candidate:
                if not isinstance(item, dict):
                    continue
                name = find_first_key(item, ("code", "key", "name", "propertyCode"))
                item_value = find_first_key(
                    item,
                    ("value", "val", "propertyValue", "attributeValue", "data"),
                )
                if name is not None:
                    converted[str(name)] = item_value
            if converted:
                return converted

    # Some responses put thing-model names directly on the device object.
    known = {
        "allfirmwarever", "area", "batterystates", "batterytemp", "bladetime",
        "connectstationstates", "devicestoped", "distance", "fault", "lidstate",
        "alarmcode", "faultcode", "mainboardtemp", "mode", "onlinestatus",
        "runningstatus", "runningtime", "signalquality", "signalstrength", "soc",
        "status", "traveleddistance", "workingtime",
    }
    return {
        str(key): value
        for key, value in payload.items()
        if str(key).casefold() in known
    }
