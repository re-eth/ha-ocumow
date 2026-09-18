"""Diagnostics support for OcuMow."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import OcuMowConfigEntry
from .const import SENSITIVE_KEYS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OcuMowConfigEntry
) -> dict[str, Any]:
    """Return redacted integration diagnostics."""
    device = entry.runtime_data.coordinator.data
    return {
        "config_entry": async_redact_data(dict(entry.data), SENSITIVE_KEYS),
        "device_id": device.device_id,
        "name": device.name,
        "properties": async_redact_data(device.properties, SENSITIVE_KEYS),
        "raw": async_redact_data(device.raw, SENSITIVE_KEYS),
    }
