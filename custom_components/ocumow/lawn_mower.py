"""Lawn mower platform for OcuMow."""

from __future__ import annotations

import asyncio
from time import monotonic

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
        self._optimistic_activity: LawnMowerActivity | None = None
        self._optimistic_until = 0.0
        self._command_refresh_task: asyncio.Task[None] | None = None
        self.async_on_remove(self._cancel_command_refresh)

    @property
    def activity(self) -> LawnMowerActivity:
        reported_activity = self._reported_activity()
        if self._optimistic_activity is not None:
            fault = self.device.get("Fault", "faultCode", "alarmCode")
            if (
                reported_activity == self._optimistic_activity
                or (
                    self._optimistic_activity == LawnMowerActivity.RETURNING
                    and reported_activity == LawnMowerActivity.DOCKED
                )
                or is_active(fault)
                or monotonic() >= self._optimistic_until
            ):
                self._optimistic_activity = None
            else:
                return self._optimistic_activity
        return reported_activity

    def _reported_activity(self) -> LawnMowerActivity:
        """Translate the latest activity reported by the cloud."""
        status = self.device.get("Status", "deviceStatus", "Mode", "runningStatus")
        fault = self.device.get("Fault", "faultCode", "alarmCode")
        station_connected = self.device.get("ConnectStationStates")
        battery_state = self.device.get("BatteryStates")
        stopped = self.device.get("DeviceStoped")

        # Error 183 means the mower is outside its permitted mowing time. The
        # app treats this as an operating restriction rather than a hardware
        # failure, so represent it as paused while the Fault sensor preserves
        # the reason.
        try:
            if int(fault) == 183:
                return (
                    LawnMowerActivity.DOCKED
                    if is_cloud_true(station_connected)
                    else LawnMowerActivity.PAUSED
                )
        except (TypeError, ValueError):
            pass

        if is_active(fault):
            return LawnMowerActivity.ERROR

        # Status 5 means standby regardless of location. The app exposes a
        # separate station-contact boolean, which distinguishes a mower safely
        # docked at its charger from one paused elsewhere on the lawn.
        if is_cloud_true(station_connected):
            return LawnMowerActivity.DOCKED

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

        text = " ".join(
            str(value).casefold()
            for value in (status, station_connected, battery_state)
            if value is not None
        )
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
            "station_connected": self.device.get("ConnectStationStates"),
            "battery_state": self.device.get("BatteryStates"),
            "mode": self.device.get("Mode"),
            "last_command_message_id": self.coordinator.api.last_command_message_id,
            "last_command_result": self.coordinator.api.last_command_result,
        }

    async def async_start_mowing(self) -> None:
        """Start or resume mowing."""
        await self.coordinator.api.async_send_command(COMMAND_START)
        self._begin_command_refresh(LawnMowerActivity.MOWING)

    async def async_pause(self) -> None:
        """Pause mowing."""
        await self.coordinator.api.async_send_command(COMMAND_PAUSE)
        self._begin_command_refresh(LawnMowerActivity.PAUSED)

    async def async_dock(self) -> None:
        """Return the mower to its charging station."""
        await self.coordinator.api.async_send_command(COMMAND_DOCK)
        self._begin_command_refresh(LawnMowerActivity.RETURNING)

    def _begin_command_refresh(self, activity: LawnMowerActivity) -> None:
        """Show the acknowledged command and temporarily poll more quickly."""
        self._cancel_command_refresh()
        self._optimistic_activity = activity
        self._optimistic_until = monotonic() + 120
        self.async_write_ha_state()
        self._command_refresh_task = self.hass.async_create_task(
            self._async_command_refresh(activity),
            f"Refresh OcuMow after {activity}",
        )

    def _cancel_command_refresh(self) -> None:
        """Cancel an earlier command's follow-up polling."""
        if self._command_refresh_task is not None:
            self._command_refresh_task.cancel()
            self._command_refresh_task = None

    async def _async_command_refresh(self, expected: LawnMowerActivity) -> None:
        """Refresh promptly while the cloud catches up with a command."""
        try:
            # These are delays between requests, giving refreshes at roughly
            # 0, 5, 15, 30, 60 and 120 seconds after the command.
            for delay in (0, 5, 10, 15, 30, 60):
                if delay:
                    await asyncio.sleep(delay)
                await self.coordinator.async_request_refresh()
                reported = self._reported_activity()
                fault = self.device.get("Fault", "faultCode", "alarmCode")
                if (
                    reported == expected
                    or (
                        expected == LawnMowerActivity.RETURNING
                        and reported == LawnMowerActivity.DOCKED
                    )
                    or is_active(fault)
                ):
                    break
        finally:
            if asyncio.current_task() is self._command_refresh_task:
                self._optimistic_activity = None
                self._optimistic_until = 0.0
                self._command_refresh_task = None
                self.async_write_ha_state()


def is_active(value: object) -> bool:
    """Interpret common truthy fault/stopped values."""
    if value in (None, False, 0):
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in ("", "0", "false", "none", "normal", "ok")
    return True


def is_cloud_true(value: object) -> bool:
    """Interpret the explicit cloud true/one representation."""
    return value is True or str(value).strip().casefold() in ("1", "true", "on")
