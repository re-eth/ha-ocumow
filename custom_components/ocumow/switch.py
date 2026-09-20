"""Switch platform for OcuMow."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .api import OcuMowDevice
from .entity import OcuMowEntity
from .binary_sensor import cloud_boolean
from .sensor import nested_value, rain_delay_hours


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OcuMow switches."""
    async_add_entities(
        [
            OcuMowScheduleModeSwitch(entry.runtime_data.coordinator),
            OcuMowRainSensorSwitch(entry.runtime_data.coordinator),
        ]
    )


class OcuMowScheduleModeSwitch(OcuMowEntity, SwitchEntity):
    """Control the mower's automatic schedule mode."""

    _attr_translation_key = "schedule_mode"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_schedule_mode"

    @property
    def available(self) -> bool:
        """Return whether the mower reports its operating mode."""
        return super().available and self.device.get("Mode") is not None

    @property
    def is_on(self) -> bool | None:
        """Return true when the app's schedule mode is selected."""
        value = self.device.get("Mode")
        if value is None:
            return None
        return str(value).strip() == "2"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable scheduled mowing."""
        await self._async_set_schedule_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable scheduled mowing."""
        await self._async_set_schedule_mode(False)

    async def _async_set_schedule_mode(self, enabled: bool) -> None:
        """Send the app-equivalent mode command and update promptly."""
        await self.coordinator.api.async_set_schedule_mode(enabled)
        current = self.coordinator.data
        self.coordinator.async_set_updated_data(
            OcuMowDevice(
                device_id=current.device_id,
                name=current.name,
                properties={**current.properties, "Mode": "2" if enabled else "0"},
                raw=current.raw,
            )
        )
        await self.coordinator.async_request_refresh()


class OcuMowRainSensorSwitch(OcuMowEntity, SwitchEntity):
    """Control whether the mower responds to its rain sensor."""

    _attr_translation_key = "rain_sensor"
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_rain_sensor_control"

    @property
    def available(self) -> bool:
        return super().available and self.device.get("RainSet") is not None

    @property
    def is_on(self) -> bool | None:
        return cloud_boolean(nested_value(self.device.get("RainSet"), "RainSwitch"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        delay = rain_delay_hours(self.device.get("RainSet")) or 0
        await self.coordinator.api.async_set_rain_settings(enabled, delay)
        await self.coordinator.async_request_refresh()
