"""Sensor platform for OcuMow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
import unicodedata

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    UnitOfArea,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .entity import OcuMowEntity


@dataclass(frozen=True, kw_only=True)
class OcuMowSensorDescription(SensorEntityDescription):
    property_keys: tuple[str, ...]
    value_fn: Callable[[Any], Any] = lambda value: value


def milliseconds_to_datetime(value: Any) -> datetime | None:
    """Convert a millisecond Unix timestamp into a UTC datetime."""
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def seconds_to_whole_hours(value: Any) -> int | None:
    """Convert seconds to the whole-hour value displayed by the app."""
    if value in (None, ""):
        return None
    try:
        return int(float(value)) // 3600
    except (TypeError, ValueError, OverflowError):
        return None


def to_integer(value: Any) -> int | None:
    """Normalise an integer returned as either a number or a string."""
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None


def clean_text(value: Any) -> str | None:
    """Remove control and other non-printing characters from cloud text."""
    if value in (None, ""):
        return None
    return "".join(
        character
        for character in str(value).strip()
        if not unicodedata.category(character).startswith("C")
    )


STATUS_LABELS = {
    0: "Automatically mowing",
    1: "Border mowing",
    2: "Returning to charge",
    3: "Device failure",
    4: "Charging",
    5: "Standby",
    6: "Out of station",
    7: "Hibernate",
    8: "Manual control",
    9: "Spot mowing",
    10: "Borderless signalling",
}


def status_to_label(value: Any) -> str | None:
    """Translate the status enumeration embedded in the OcuMow app."""
    if value in (None, ""):
        return None
    try:
        status = int(value)
    except (TypeError, ValueError):
        return str(value)
    return STATUS_LABELS.get(status, f"Unknown ({status})")


SENSORS: tuple[OcuMowSensorDescription, ...] = (
    OcuMowSensorDescription(
        key="battery", translation_key="battery", property_keys=("Soc", "battery"),
        device_class=SensorDeviceClass.BATTERY, native_unit_of_measurement=PERCENTAGE,
    ),
    OcuMowSensorDescription(
        key="status", translation_key="status",
        property_keys=("Status", "deviceStatus", "runningStatus"),
        value_fn=status_to_label,
        icon="mdi:robot-mower-outline",
    ),
    OcuMowSensorDescription(
        key="signal_quality", translation_key="signal_quality",
        property_keys=("SignalQuality", "signalStrength"),
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OcuMowSensorDescription(
        key="fault", translation_key="fault",
        property_keys=("Fault", "faultCode", "alarmCode"),
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OcuMowSensorDescription(
        key="area", translation_key="area", property_keys=("Area",),
        icon="mdi:ruler-square",
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
        key="working_time", translation_key="working_time",
        property_keys=("BladeTime",), value_fn=seconds_to_whole_hours,
        icon="mdi:power",
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OcuMowSensorDescription(
        key="running_time", translation_key="running_time",
        property_keys=("WorkingTime",), value_fn=seconds_to_whole_hours,
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OcuMowSensorDescription(
        key="blade_time", translation_key="blade_time",
        property_keys=("RunningTime",), value_fn=seconds_to_whole_hours,
        icon="mdi:saw-blade",
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OcuMowSensorDescription(
        key="distance", translation_key="distance", property_keys=("Distance",),
        value_fn=to_integer, icon="mdi:map-marker-distance",
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    OcuMowSensorDescription(
        key="working_distance", translation_key="working_distance",
        property_keys=("TraveledDistance",), value_fn=to_integer,
        icon="mdi:map-marker-path",
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    OcuMowSensorDescription(
        key="firmware", translation_key="firmware", property_keys=("AllFirmwareVer",),
        value_fn=clean_text,
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OcuMowSensorDescription(
        key="last_online",
        translation_key="last_online",
        property_keys=("tsLastOnlineTime",),
        value_fn=milliseconds_to_datetime,
        icon="mdi:cloud-check-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OcuMowSensorDescription(
        key="last_offline",
        translation_key="last_offline",
        property_keys=("tsLastOfflineTime",),
        value_fn=milliseconds_to_datetime,
        icon="mdi:cloud-off-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
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
