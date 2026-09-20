"""Calendar platform for OcuMow weekly mowing schedules."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OcuMowConfigEntry
from .api import OcuMowError
from .entity import OcuMowEntity
from .sensor import normalise_schedule


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OcuMow schedule calendar."""
    async_add_entities([OcuMowScheduleCalendar(entry.runtime_data.coordinator)])


def _uid(item: dict[str, Any]) -> str:
    return f"ocumow-{item['weekday']}-{item['start']}-{item['end']}"


def _protocol_schedules(value: Any) -> list[dict[str, int]]:
    schedules: list[dict[str, int]] = []
    for item in normalise_schedule(value):
        start_hour, start_minute = (int(part) for part in item["start"].split(":"))
        end_hour, end_minute = (int(part) for part in item["end"].split(":"))
        schedules.append(
            {
                "week": 0 if item["weekday"] == 6 else item["weekday"] + 1,
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute,
            }
        )
    return schedules


def _occurrence(item: dict[str, Any], after: datetime) -> CalendarEvent:
    start_hour, start_minute = (int(part) for part in item["start"].split(":"))
    end_hour, end_minute = (int(part) for part in item["end"].split(":"))
    days_ahead = (item["weekday"] - after.weekday()) % 7
    start = (after + timedelta(days=days_ahead)).replace(
        hour=start_hour, minute=start_minute, second=0, microsecond=0
    )
    if start < after:
        start += timedelta(days=7)
    end = start.replace(hour=end_hour, minute=end_minute)
    if end <= start:
        end += timedelta(days=1)
    return CalendarEvent(
        summary="Scheduled mowing",
        start=start,
        end=end,
        uid=_uid(item),
    )


class OcuMowScheduleCalendar(OcuMowEntity, CalendarEntity):
    """Expose and edit the mower's repeating weekly schedule."""

    _attr_translation_key = "schedule_calendar"
    _attr_icon = "mdi:calendar-clock"
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_schedule_calendar"

    @property
    def available(self) -> bool:
        return super().available and self.device.get("Schedule") is not None

    @property
    def event(self) -> CalendarEvent | None:
        events = [
            _occurrence(item, dt_util.now())
            for item in normalise_schedule(self.device.get("Schedule"))
            if item["enabled"]
        ]
        return min(events, key=lambda event: event.start) if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return each weekly occurrence in the requested range."""
        events: list[CalendarEvent] = []
        for item in normalise_schedule(self.device.get("Schedule")):
            if not item["enabled"]:
                continue
            occurrence = _occurrence(item, dt_util.as_local(start_date))
            while occurrence.start < end_date:
                if occurrence.end > start_date:
                    events.append(occurrence)
                occurrence = CalendarEvent(
                    summary=occurrence.summary,
                    start=occurrence.start + timedelta(days=7),
                    end=occurrence.end + timedelta(days=7),
                    uid=occurrence.uid,
                )
        return sorted(events, key=lambda event: event.start)

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a new weekly mowing period using the calendar editor."""
        start = kwargs.get("start")
        end = kwargs.get("end")
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise HomeAssistantError("A schedule requires start and end times")
        start = dt_util.as_local(start)
        end = dt_util.as_local(end)
        if end <= start or end - start > timedelta(days=1):
            raise HomeAssistantError(
                "A schedule must be between 1 minute and 24 hours"
            )

        schedules = _protocol_schedules(self.device.get("Schedule"))
        mower_weekday = 0 if start.weekday() == 6 else start.weekday() + 1
        if sum(item["week"] == mower_weekday for item in schedules) >= 2:
            raise HomeAssistantError(
                "The mower supports at most two schedules per day"
            )
        schedules.append(
            {
                "week": mower_weekday,
                "start_hour": start.hour,
                "start_minute": start.minute,
                "end_hour": end.hour,
                "end_minute": end.minute,
            }
        )
        try:
            await self.coordinator.api.async_set_schedule(schedules)
        except OcuMowError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete the complete weekly mowing period represented by an event."""
        items = normalise_schedule(self.device.get("Schedule"))
        remaining = [item for item in items if _uid(item) != uid]
        if len(remaining) == len(items):
            raise HomeAssistantError("The selected mower schedule no longer exists")
        try:
            await self.coordinator.api.async_set_schedule(
                _protocol_schedules_from_items(remaining)
            )
        except OcuMowError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()


def _protocol_schedules_from_items(
    items: list[dict[str, Any]],
) -> list[dict[str, int]]:
    """Convert already-normalised items without decoding them again."""
    schedules: list[dict[str, int]] = []
    for item in items:
        start_hour, start_minute = (int(part) for part in item["start"].split(":"))
        end_hour, end_minute = (int(part) for part in item["end"].split(":"))
        schedules.append(
            {
                "week": 0 if item["weekday"] == 6 else item["weekday"] + 1,
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute,
            }
        )
    return schedules
