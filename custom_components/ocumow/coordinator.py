"""Data update coordinator for OcuMow."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OcuMowApi, OcuMowAuthError, OcuMowDevice, OcuMowError
from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN


class OcuMowCoordinator(DataUpdateCoordinator[OcuMowDevice]):
    """Coordinate cloud polling for a mower."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: OcuMowApi) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )
        self.entry = entry
        self.api = api

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
