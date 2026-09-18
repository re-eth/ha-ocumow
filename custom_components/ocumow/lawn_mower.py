"""Lawn mower platform for OcuMow."""

from __future__ import annotations

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .const import COMMAND_DOCK, COMMAND_PAUSE, COMMAND_START
from .entity import OcuMowEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([OcuMowLawnMower(entry.runtime_data.coordinator)])


class OcuMowLawnMower(OcuMowEntity, LawnMowerEntity):
    """Representation of an OcuMow mower."""

    _attr_translation_key = "mower"
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_mower"

    @property
    def activity(self) -> LawnMowerActivity:
        status = self.device.get("Status", "deviceStatus", "Mode", "runningStatus")
        fault = self.device.get("Fault", "faultCode", "alarmCode")
        docked = self.device.get("ConnectStationStates", "BatteryStates")
        stopped = self.device.get("DeviceStoped")

        if is_active(fault):
            return LawnMowerActivity.ERROR

        try:
            numeric_status = int(status) if status is not None else None
        except (TypeError, ValueError):
            numeric_status = None
        if numeric_status in (0, 1, 9, 10):
            return LawnMowerActivity.MOWING
        if numeric_status == 2:
            return LawnMowerActivity.RETURNING
        if numeric_status == 3:
            return LawnMowerActivity.ERROR
        if numeric_status == 4:
            return LawnMowerActivity.DOCKED
        if numeric_status in (5, 6, 7, 8):
            return LawnMowerActivity.PAUSED

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
            return LawnMowerActivity.PAUSED
        return LawnMowerActivity.PAUSED

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "raw_status": self.device.get("Status", "deviceStatus", "runningStatus"),
            "mode": self.device.get("Mode"),
        }

    async def async_start_mowing(self) -> None:
        """Start or resume mowing."""
        await self.coordinator.api.async_send_command(COMMAND_START)
        await self.coordinator.async_request_refresh()

    async def async_pause(self) -> None:
        """Pause mowing."""
        await self.coordinator.api.async_send_command(COMMAND_PAUSE)
        await self.coordinator.async_request_refresh()

    async def async_dock(self) -> None:
        """Return the mower to its charging station."""
        await self.coordinator.api.async_send_command(COMMAND_DOCK)
        await self.coordinator.async_request_refresh()


def is_active(value: object) -> bool:
    """Interpret common truthy fault/stopped values."""
    if value in (None, False, 0):
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in ("", "0", "false", "none", "normal", "ok")
    return True
