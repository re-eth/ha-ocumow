"""Binary sensor platform for OcuMow."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .entity import OcuMowEntity
from .sensor import nested_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OcuMow binary sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            OcuMowRainSensorEnabled(coordinator),
            OcuMowOnlineSensor(coordinator),
            OcuMowStoppedSensor(coordinator),
        ]
    )


def cloud_boolean(value: Any) -> bool | None:
    """Convert a cloud boolean or zero/one value."""
    if value in (None, ""):
        return None
    return value is True or str(value).strip().casefold() in ("1", "true", "on")


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
        return cloud_boolean(value)


class OcuMowOnlineSensor(OcuMowEntity, BinarySensorEntity):
    """Show whether the mower is connected to the vendor cloud."""

    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_online"

    @property
    def is_on(self) -> bool | None:
        return cloud_boolean(self.device.get("onlineStatus"))


class OcuMowStoppedSensor(OcuMowEntity, BinarySensorEntity):
    """Expose the mower's DeviceStoped flag reported by the cloud."""

    _attr_translation_key = "stopped"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_stopped"

    @property
    def is_on(self) -> bool | None:
        return cloud_boolean(self.device.get("DeviceStoped"))
