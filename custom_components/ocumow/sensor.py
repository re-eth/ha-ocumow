"""Sensor platform for OcuMow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import PERCENTAGE, UnitOfArea, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .entity import OcuMowEntity


@dataclass(frozen=True, kw_only=True)
class OcuMowSensorDescription(SensorEntityDescription):
    property_keys: tuple[str, ...]
    value_fn: Callable[[Any], Any] = lambda value: value


SENSORS: tuple[OcuMowSensorDescription, ...] = (
    OcuMowSensorDescription(
        key="battery", translation_key="battery", property_keys=("Soc", "battery"),
        device_class=SensorDeviceClass.BATTERY, native_unit_of_measurement=PERCENTAGE,
    ),
    OcuMowSensorDescription(
        key="status", translation_key="status",
        property_keys=("Status", "deviceStatus", "runningStatus"),
    ),
    OcuMowSensorDescription(
        key="signal_quality", translation_key="signal_quality",
        property_keys=("SignalQuality", "signalStrength"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OcuMowSensorDescription(
        key="fault", translation_key="fault",
        property_keys=("Fault", "faultCode", "alarmCode"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OcuMowSensorDescription(
        key="area", translation_key="area", property_keys=("Area",),
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
    ),
    OcuMowSensorDescription(
        key="mainboard_temperature", translation_key="mainboard_temperature",
        property_keys=("MainBoardTemp",), device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OcuMowSensorDescription(
        key="battery_temperature", translation_key="battery_temperature",
        property_keys=("BatteryTemp",), device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OcuMowSensorDescription(
        key="working_time", translation_key="working_time", property_keys=("WorkingTime",),
    ),
    OcuMowSensorDescription(
        key="running_time", translation_key="running_time", property_keys=("RunningTime",),
    ),
    OcuMowSensorDescription(
        key="blade_time", translation_key="blade_time", property_keys=("BladeTime",),
    ),
    OcuMowSensorDescription(
        key="distance", translation_key="distance", property_keys=("TraveledDistance", "Distance"),
    ),
    OcuMowSensorDescription(
        key="firmware", translation_key="firmware", property_keys=("AllFirmwareVer",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(OcuMowSensor(coordinator, description) for description in SENSORS)


class OcuMowSensor(OcuMowEntity, SensorEntity):
    """A property reported by an OcuMow mower."""

    entity_description: OcuMowSensorDescription

    def __init__(self, coordinator, description: OcuMowSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.device.device_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        value = self.device.get(*self.entity_description.property_keys)
        if isinstance(value, (dict, list)):
            return str(value)
        return self.entity_description.value_fn(value)
