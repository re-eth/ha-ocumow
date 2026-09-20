"""Number platform for OcuMow."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .binary_sensor import cloud_boolean
from .entity import OcuMowEntity
from .sensor import nested_value, rain_delay_hours


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OcuMow number controls."""
    async_add_entities([OcuMowRainDelayNumber(entry.runtime_data.coordinator)])


class OcuMowRainDelayNumber(OcuMowEntity, NumberEntity):
    """Set the mower's post-rain delay in hours."""

    _attr_translation_key = "rain_delay_control"
    _attr_icon = "mdi:weather-pouring"
    _attr_native_min_value = 0
    _attr_native_max_value = 9
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_rain_delay_control"

    @property
    def available(self) -> bool:
        return super().available and self.device.get("RainSet") is not None

    @property
    def native_value(self) -> int | None:
        return rain_delay_hours(self.device.get("RainSet"))

    async def async_set_native_value(self, value: float) -> None:
        enabled = cloud_boolean(
            nested_value(self.device.get("RainSet"), "RainSwitch")
        )
        await self.coordinator.api.async_set_rain_settings(bool(enabled), round(value))
        await self.coordinator.async_request_refresh()
