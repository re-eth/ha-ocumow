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

FAULT_LABELS = {
    0: "No fault",
    49: "Wheel slipping",
    53: "Control system error",
    54: "Control system error",
    55: "Outside border",
    56: "Control system error",
    57: "Control system error",
    65: "Battery error",
    67: "Battery error",
    76: "Mower lifted",
    77: "Motor fault",
    82: "Rolling over",
    83: "Battery temperature too hot/cold",
    84: "Mower tilted",
    88: "Mower blocked",
    97: "Stop button error",
    98: "Control system error",
    99: "Stop button error",
    100: "Rain sensor triggered",
    101: "Too close to garage",
    103: "Too close to charging station",
    110: "Control system error",
    111: "Control system error",
    112: "Control system error",
    113: "Control system error",
    114: "Control system error",
    115: "Unknown error",
    141: "Magnet sensor error",
    147: "No camera signal",
    151: "Control system error",
    152: "Control system error",
    153: "Control system error",
    154: "Control system error",
    155: "Control system error",
    157: "No GPS data",
    158: "Far from station",
    159: "Rain sensor triggered",
    160: "Battery temperature too hot/cold",
    161: "Ribbon not visible",
    163: "Control system error",
    164: "Control system error",
    165: "Control system error",
    166: "Control system error",
    167: "Control system error",
    168: "Battery temperature too hot/cold",
    169: "Battery error",
    171: "No camera signal",
    172: "Close battery hatch",
    173: "Low voltage",
    174: "Magnet sensor error",
    176: "Control system error",
    177: "Control system error",
    178: "No battery",
    180: "Cutter blocked",
    181: "Cutter fault",
    182: "Return home failed",
    183: "Outside permitted mowing time",
    184: "Close battery hatch",
    185: "Battery too low to update",
    186: "Unsupported area",
    187: "Control system error",
    215: "Control system error",
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


def fault_to_label(value: Any) -> str | None:
    """Translate the fault codes embedded in the OcuMow app."""
    if value in (None, ""):
        return None
    try:
        fault = int(value)
    except (TypeError, ValueError):
        return str(value)
    return FAULT_LABELS.get(fault, f"Unknown fault ({fault})")


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
        value_fn=fault_to_label,
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
