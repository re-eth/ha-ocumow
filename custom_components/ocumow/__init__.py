"""OcuMow integration setup."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OcuMowApi, OcuMowAuthError, OcuMowConnectionError, OcuMowError
from .const import PLATFORMS
from .coordinator import OcuMowCoordinator


@dataclass(slots=True)
class OcuMowRuntimeData:
    """Runtime objects belonging to one config entry."""

    coordinator: OcuMowCoordinator


type OcuMowConfigEntry = ConfigEntry[OcuMowRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: OcuMowConfigEntry) -> bool:
    """Set up OcuMow from a config entry."""
    api = OcuMowApi(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = OcuMowCoordinator(hass, entry, api)
    try:
        await coordinator.async_config_entry_first_refresh()
    except OcuMowAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (OcuMowConnectionError, OcuMowError) as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = OcuMowRuntimeData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start_websocket()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OcuMowConfigEntry) -> bool:
    """Unload an OcuMow config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.coordinator.async_stop_websocket()
    return unloaded
