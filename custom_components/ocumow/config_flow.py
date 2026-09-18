"""Config flow for OcuMow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OcuMowApi, OcuMowAuthError, OcuMowConnectionError, OcuMowError
from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME, DOMAIN


class OcuMowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an OcuMow setup flow."""

    VERSION = 1
    _reauth_entry = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = f"{user_input[CONF_EMAIL].strip().casefold()}:{user_input[CONF_DEVICE_ID]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            try:
                api = OcuMowApi(
                    async_get_clientsession(self.hass),
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
                await api.async_login()
                device = await api.async_get_device(
                    user_input[CONF_DEVICE_ID], user_input[CONF_DEVICE_NAME]
                )
            except OcuMowAuthError:
                errors["base"] = "invalid_auth"
            except OcuMowConnectionError:
                errors["base"] = "cannot_connect"
            except OcuMowError:
                errors["base"] = "invalid_device"
            else:
                return self.async_create_entry(title=device.name, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Begin reauthentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a new password."""
        errors: dict[str, str] = {}
        if user_input is not None and self._reauth_entry is not None:
            try:
                api = OcuMowApi(
                    async_get_clientsession(self.hass),
                    self._reauth_entry.data[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
                await api.async_login()
            except OcuMowAuthError:
                errors["base"] = "invalid_auth"
            except OcuMowError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
