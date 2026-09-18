"""Sensor platform for OcuMow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from typing import Any
import unicodedata

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

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


def mowing_area_label(value: Any) -> str | None:
    """Translate the mower's area selector to the labels used by the app."""
    area = to_integer(value)
    if area is None:
        return None
    return {0: "Main", 1: "Other"}.get(area, f"Unknown ({area})")


def clean_text(value: Any) -> str | None:
    """Remove control and other non-printing characters from cloud text."""
    if value in (None, ""):
        return None
    return "".join(
        character
        for character in str(value).strip()
        if not unicodedata.category(character).startswith("C")
    )


def decode_cloud_json(value: Any) -> Any:
    """Decode values which the cloud sometimes returns as JSON text."""
    current = value
    for _ in range(2):
        if not isinstance(current, str):
            break
        try:
            current = json.loads(current)
        except (TypeError, ValueError):
            break
    return current


def nested_value(value: Any, key: str) -> Any:
    """Find a case-insensitive key inside a structured cloud property."""
    value = decode_cloud_json(value)
    if isinstance(value, dict):
        lowered = {str(item_key).casefold(): item for item_key, item in value.items()}
        property_name = lowered.get("code", lowered.get("name"))
        if str(property_name).casefold() == key.casefold():
            for value_key in ("attributevalue", "value", "propertyvalue", "val"):
                if value_key in lowered:
                    return decode_cloud_json(lowered[value_key])
        for item_key, item_value in value.items():
            if str(item_key).casefold() == key.casefold():
                return decode_cloud_json(item_value)
        for item_value in value.values():
            found = nested_value(item_value, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = nested_value(item, key)
            if found is not None:
                return found
    return None


def rain_delay_hours(value: Any) -> int | None:
    """Extract the post-rain delay configured in the RainSet structure."""
    return to_integer(nested_value(value, "DelayWorkingTime"))


WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def normalise_schedule(value: Any) -> list[dict[str, Any]]:
    """Convert the mower's Schedule array into stable dictionaries."""
    value = decode_cloud_json(value)
    if isinstance(value, dict):
        value = nested_value(value, "Schedule") or nested_value(value, "value")
        value = decode_cloud_json(value)
    if not isinstance(value, list):
        return []

    schedules: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        lowered = {str(key).casefold(): item for key, item in raw.items()}
        try:
            week = int(lowered.get("week"))
            start_hour = int(lowered.get("starthour"))
            start_minute = int(lowered.get("startminute"))
            end_hour = int(lowered.get("endhour"))
            end_minute = int(lowered.get("endminute"))
        except (TypeError, ValueError):
            continue
        valid_value = lowered.get("validflag", lowered.get("valid", True))
        enabled = valid_value is True or str(valid_value).casefold() in ("1", "true")
        # The mower pads its weekly array with enabled-looking zero-length
        # records. The app does not present these as actual mowing periods.
        if start_hour == end_hour and start_minute == end_minute:
            continue
        # The app stores Monday-Saturday as 1-6 and Sunday as 0.
        weekday = 6 if week == 0 else week - 1
        if not 0 <= weekday <= 6:
            continue
        schedules.append(
            {
                "weekday": weekday,
                "day": WEEKDAYS[weekday],
                "start": f"{start_hour:02d}:{start_minute:02d}",
                "end": f"{end_hour:02d}:{end_minute:02d}",
                "enabled": enabled,
            }
        )
    return sorted(schedules, key=lambda item: (item["weekday"], item["start"]))


def schedule_summary(value: Any) -> str:
    """Return a compact readable list of enabled mowing periods."""
    schedules = [item for item in normalise_schedule(value) if item["enabled"]]
    if not schedules:
        return "No enabled schedules"
    summary = "; ".join(
        f"{item['day']} {item['start']}–{item['end']}" for item in schedules
    )
    # Home Assistant limits entity states to 255 characters. The complete
    # unabridged schedule remains available in the entity attributes.
    return summary if len(summary) <= 250 else f"{len(schedules)} enabled schedules"


def next_scheduled_cut(value: Any, now: datetime | None = None) -> datetime | None:
    """Calculate the next enabled schedule start in the HA timezone."""
    local_now = now or dt_util.now()
    candidates: list[datetime] = []
    for item in normalise_schedule(value):
        if not item["enabled"]:
            continue
        hours, minutes = (int(part) for part in item["start"].split(":"))
        days_ahead = (item["weekday"] - local_now.weekday()) % 7
        candidate = (local_now + timedelta(days=days_ahead)).replace(
            hour=hours, minute=minutes, second=0, microsecond=0
        )
        if candidate <= local_now:
            candidate += timedelta(days=7)
        candidates.append(candidate)
    return min(candidates).astimezone(UTC) if candidates else None


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
        value_fn=mowing_area_label,
        icon="mdi:map-marker-radius-outline",
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
    OcuMowSensorDescription(
        key="rain_delay",
        translation_key="rain_delay",
        property_keys=("RainSet",),
        value_fn=rain_delay_hours,
        icon="mdi:weather-pouring",
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = [
        OcuMowSensor(coordinator, description) for description in SENSORS
    ]
    entities.extend(
        (
            OcuMowScheduleSensor(coordinator),
            OcuMowNextCutSensor(coordinator),
        )
    )
    async_add_entities(entities)


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
        converted = self.entity_description.value_fn(value)
        if isinstance(converted, (dict, list)):
            return str(converted)
        return converted


class OcuMowScheduleSensor(OcuMowEntity, SensorEntity):
    """Display the mower's enabled weekly schedules."""

    _attr_translation_key = "schedule"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_schedule"

    @property
    def native_value(self) -> str | None:
        value = self.device.get("Schedule")
        return schedule_summary(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"schedules": normalise_schedule(self.device.get("Schedule"))}


class OcuMowNextCutSensor(OcuMowEntity, SensorEntity):
    """Display the next enabled schedule start."""

    _attr_translation_key = "next_cut"
    _attr_icon = "mdi:calendar-arrow-right"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_next_cut"

    @property
    def native_value(self) -> datetime | None:
        return next_scheduled_cut(self.device.get("Schedule"))
