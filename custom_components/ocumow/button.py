"""Button platform for OcuMow."""

from __future__ import annotations

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

    async def async_press(self) -> None:
        """Reset the counter using the command sent by the OcuMow app."""
        await self.coordinator.api.async_reset_blade_time()
        await self.coordinator.async_request_refresh()
