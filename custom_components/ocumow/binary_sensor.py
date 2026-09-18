"""Binary sensor platform for OcuMow."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .entity import OcuMowEntity
from .sensor import nested_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OcuMow rain setting entity."""
    async_add_entities([OcuMowRainSensorEnabled(entry.runtime_data.coordinator)])


class OcuMowRainSensorEnabled(OcuMowEntity, BinarySensorEntity):
    """Show whether rain sensing is enabled on the mower."""

    _attr_translation_key = "rain_sensor_enabled"
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_rain_sensor_enabled"

    @property
    def is_on(self) -> bool | None:
        value: Any = nested_value(self.device.get("RainSet"), "RainSwitch")
        if value in (None, ""):
            return None
        return value is True or str(value).casefold() in ("1", "true", "on")
