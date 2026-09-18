"""Tests for vendor-response normalisation that do not require hardware."""

from hashlib import sha256

from custom_components.ocumow.api import (
    OcuMowDevice,
    build_login_payload,
    extract_devices,
    extract_properties,
    find_first_key,
    unwrap_envelope,
)
from custom_components.ocumow.const import (
    API_USER_DOMAIN,
    API_USER_DOMAIN_SECRET,
    COMMAND_DOCK,
    COMMAND_MESSAGE_IDS,
    COMMAND_PAUSE,
    COMMAND_START,
    RESET_DATA_MESSAGE_ID,
)


def test_build_login_payload_matches_apk_algorithm() -> None:
    payload = build_login_payload("owner@example.com", "secret")

    assert payload == {
        "email": "owner@example.com",
        "pwd": "secret",
        "signature": sha256(
            f"owner@example.comsecret{API_USER_DOMAIN_SECRET}".encode()
        ).hexdigest(),
        "userDomain": API_USER_DOMAIN,
    }


def test_command_message_ids_match_apk() -> None:
    assert COMMAND_MESSAGE_IDS == {
        COMMAND_PAUSE: 1012,
        COMMAND_START: 1013,
        COMMAND_DOCK: 1014,
    }
    assert RESET_DATA_MESSAGE_ID == 1001


def test_find_nested_token() -> None:
    assert find_first_key({"data": {"accessToken": "abc"}}, ("accessToken",)) == "abc"


def test_find_wrapped_access_token() -> None:
    assert (
        find_first_key(
            {"data": {"accessToken": {"expirationTime": 123, "token": "abc"}}},
            ("accessToken", "token"),
        )
        == "abc"
    )


def test_extract_devices() -> None:
    devices = extract_devices(
        {
            "code": 200,
            "data": {
                "rows": [
                    {"deviceId": 123, "deviceName": "Back garden"},
                    {"deviceId": "456", "productName": "OcuMow 18B"},
                    {"deviceName": "Missing ID"},
                ]
            },
        }
    )

    assert [(device.device_id, device.name) for device in devices] == [
        ("123", "Back garden"),
        ("456", "OcuMow 18B"),
    ]


def test_unwrap_envelope() -> None:
    assert unwrap_envelope({"code": 0, "data": {"result": {"Soc": 87}}}) == {"Soc": 87}


def test_extract_property_list() -> None:
    payload = {
        "properties": [
            {"code": "Soc", "value": 87},
            {"code": "Status", "value": "mowing"},
        ]
    }
    assert extract_properties(payload) == {"Soc": 87, "Status": "mowing"}


def test_extract_apk_statistic_property_list() -> None:
    payload = {
        "code": 200,
        "data": [
            {"code": "RunningTime", "attributeValue": "123"},
            {"code": "BladeTime", "attributeValue": "45"},
            {"code": "TraveledDistance", "attributeValue": "678"},
        ],
    }

    assert extract_properties(payload) == {
        "RunningTime": "123",
        "BladeTime": "45",
        "TraveledDistance": "678",
    }


def test_extract_sub_device_tsl_properties() -> None:
    payload = {
        "deviceId": 6001,
        "tslProperties": [
            {"code": "Soc", "attributeValue": "84"},
            {"code": "Status", "attributeValue": "1"},
        ],
    }

    assert extract_properties(payload) == {"Soc": "84", "Status": "1"}


def test_device_get_falls_back_to_raw_gateway_fields() -> None:
    device = OcuMowDevice(
        device_id="5599",
        name="Back garden",
        properties={"soc": 100},
        raw={"onlineStatus": 1, "runningStatus": 1, "signalStrength": "-62"},
    )

    assert device.get("Soc") == 100
    assert device.get("onlineStatus") == 1
    assert device.get("runningStatus") == 1
    assert device.get("SignalQuality", "signalStrength") == "-62"
