"""Lawn mower platform for OcuMow."""

from __future__ import annotations

from homeassistant.components.lawn_mower import LawnMowerActivity, LawnMowerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .entity import OcuMowEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([OcuMowLawnMower(entry.runtime_data.coordinator)])


class OcuMowLawnMower(OcuMowEntity, LawnMowerEntity):
    """Representation of an OcuMow mower.

    Controls intentionally remain disabled until command payloads are verified.
    """

    _attr_translation_key = "mower"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_mower"

    @property
    def activity(self) -> LawnMowerActivity:
        status = self.device.get("Status", "deviceStatus", "Mode")
        fault = self.device.get("Fault")
        docked = self.device.get("ConnectStationStates", "BatteryStates")
        stopped = self.device.get("DeviceStoped")

        if is_active(fault):
            return LawnMowerActivity.ERROR

        text = " ".join(str(value).casefold() for value in (status, docked) if value is not None)
        if any(word in text for word in ("mow", "working", "cutting")):
            return LawnMowerActivity.MOWING
        if any(word in text for word in ("return", "homing", "recharging")):
            return LawnMowerActivity.RETURNING
        if any(word in text for word in ("dock", "charging", "charged", "station")):
            return LawnMowerActivity.DOCKED
        if "pause" in text:
            return LawnMowerActivity.PAUSED
        if is_active(stopped) or any(word in text for word in ("idle", "stop", "standby")):
            return LawnMowerActivity.IDLE
        return LawnMowerActivity.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "raw_status": self.device.get("Status", "deviceStatus"),
            "mode": self.device.get("Mode"),
        }


def is_active(value: object) -> bool:
    """Interpret common truthy fault/stopped values."""
    if value in (None, False, 0):
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in ("", "0", "false", "none", "normal", "ok")
    return True
