"""Button platform for OcuMow."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OcuMowConfigEntry
from .entity import OcuMowEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OcuMowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OcuMow reset button."""
    async_add_entities([OcuMowResetBladeTimeButton(entry.runtime_data.coordinator)])


class OcuMowResetBladeTimeButton(OcuMowEntity, ButtonEntity):
    """Reset the mower's blade-time counter."""

    _attr_translation_key = "reset_blade_time"
    _attr_icon = "mdi:restore"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.device_id}_reset_blade_time"
        self._reset_result: str | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the cloud response so a reset can be diagnosed in HA."""
        return {
            "reset_result": self._reset_result,
            "last_command_message_id": self.coordinator.api.last_command_message_id,
            "last_command_result": self.coordinator.api.last_command_result,
        }

    async def async_press(self) -> None:
        """Reset the counter using the command sent by the OcuMow app."""
        previous_value = self.device.get("RunningTime")
        self._reset_result = "Sending"
        self.async_write_ha_state()

        try:
            await self.coordinator.api.async_reset_blade_time()

            # The statistics endpoint can lag behind the successful WebSocket
            # acknowledgement. Give the cloud a short window to publish the
            # reset value instead of immediately showing the cached counter.
            for attempt in range(3):
                if attempt:
                    await asyncio.sleep(5)
                await self.coordinator.async_request_refresh()
                current_value = self.device.get("RunningTime")
                if current_value != previous_value:
                    self._reset_result = "Blade time reset"
                    break
            else:
                self._reset_result = (
                    "Cloud acknowledged reset; blade time has not changed yet"
                )
        except Exception:
            self._reset_result = self.coordinator.api.last_command_result or "Failed"
            raise
        finally:
            self.async_write_ha_state()
