"""Shared OcuMow entity base."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OcuMowDevice
from .const import DOMAIN
from .coordinator import OcuMowCoordinator


class OcuMowEntity(CoordinatorEntity[OcuMowCoordinator]):
    """Base class for entities belonging to an OcuMow device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OcuMowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.device_id)},
            manufacturer="CLEVA",
            name=coordinator.data.name,
            model="OcuMow",
        )

    @property
    def device(self) -> OcuMowDevice:
        return self.coordinator.data
