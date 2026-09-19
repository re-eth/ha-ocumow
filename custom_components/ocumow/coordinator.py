"""Data update coordinator for OcuMow."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    OcuMowApi,
    OcuMowAuthError,
    OcuMowDevice,
    OcuMowError,
    extract_live_properties,
)
from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OcuMowCoordinator(DataUpdateCoordinator[OcuMowDevice]):
    """Coordinate cloud polling for a mower."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: OcuMowApi) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )
        self.entry = entry
        self.api = api
        self._websocket_task: asyncio.Task[None] | None = None
        self._event_refresh_task: asyncio.Task[None] | None = None
        self._last_event_refresh = 0.0

    def async_start_websocket(self) -> None:
        """Start the persistent live-event connection."""
        if self._websocket_task is None and self.api.websocket_ready:
            self._websocket_task = self.hass.async_create_background_task(
                self._async_websocket_loop(), "OcuMow live cloud events"
            )

    async def async_stop_websocket(self) -> None:
        """Stop the live-event connection and pending event refresh."""
        tasks = tuple(
            task
            for task in (self._websocket_task, self._event_refresh_task)
            if task is not None
        )
        self._websocket_task = None
        self._event_refresh_task = None
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task

    async def _async_websocket_loop(self) -> None:
        """Keep the vendor WebSocket connected with bounded backoff."""
        retry_delay = 5
        while True:
            try:
                await self.api.async_listen_events(self._async_handle_live_event)
                retry_delay = 5
            except asyncio.CancelledError:
                raise
            except OcuMowAuthError:
                try:
                    await self.api.async_login()
                except OcuMowAuthError:
                    self.entry.async_start_reauth(self.hass)
                    return
                except OcuMowError as err:
                    _LOGGER.debug("Unable to renew OcuMow WebSocket login: %s", err)
            except OcuMowError as err:
                _LOGGER.debug(
                    "OcuMow live WebSocket disconnected; retrying in %s seconds: %s",
                    retry_delay,
                    err,
                )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)

    async def _async_handle_live_event(self, event: dict[str, Any]) -> None:
        """Debounce live broadcasts into a fresh complete device snapshot."""
        command = str(event.get("cmd", "")).casefold()
        if command.endswith("_resp") or command == "send_ack":
            return
        _LOGGER.debug("Received OcuMow live event: %s", command or "broadcast")
        changed = extract_live_properties(event)
        if changed and self.data is not None:
            self.async_set_updated_data(
                OcuMowDevice(
                    device_id=self.data.device_id,
                    name=self.data.name,
                    properties={**self.data.properties, **changed},
                    raw=self.data.raw,
                )
            )
        if self._event_refresh_task is None or self._event_refresh_task.done():
            self._event_refresh_task = self.hass.async_create_task(
                self._async_refresh_after_event(), "Refresh OcuMow live event"
            )

    async def _async_refresh_after_event(self) -> None:
        """Reconcile live data without turning event bursts into REST polling."""
        now = asyncio.get_running_loop().time()
        await asyncio.sleep(max(1.0, 15.0 - (now - self._last_event_refresh)))
        await self.async_request_refresh()
        self._last_event_refresh = asyncio.get_running_loop().time()

    async def _async_update_data(self) -> OcuMowDevice:
        try:
            return await self.api.async_get_device(
                self.entry.data[CONF_DEVICE_ID],
                self.entry.data[CONF_DEVICE_NAME],
            )
        except OcuMowAuthError:
            self.entry.async_start_reauth(self.hass)
            raise
        except OcuMowError as err:
            raise UpdateFailed(str(err)) from err
