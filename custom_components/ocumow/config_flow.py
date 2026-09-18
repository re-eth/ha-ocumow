"""Config flow for OcuMow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OcuMowApi, OcuMowAuthError, OcuMowConnectionError, OcuMowError
from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DOMAIN


class OcuMowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an OcuMow setup flow."""

    VERSION = 1
    _reauth_entry = None
    _email: str | None = None
    _password: str | None = None
    _devices: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                api = OcuMowApi(
                    async_get_clientsession(self.hass),
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
                await api.async_login()
                devices = await api.async_get_devices()
            except OcuMowAuthError:
                errors["base"] = "invalid_auth"
            except OcuMowConnectionError:
                errors["base"] = "cannot_connect"
            except OcuMowError:
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    self._email = user_input[CONF_EMAIL]
                    self._password = user_input[CONF_PASSWORD]
                    self._devices = {
                        device.device_id: device.name for device in devices
                    }
                    if len(self._devices) == 1:
                        return await self._create_device_entry(next(iter(self._devices)))
                    return await self.async_step_device()

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose among discovered mowers."""
        if not self._devices or self._email is None or self._password is None:
            return self.async_abort(reason="discovery_expired")

        if user_input is not None:
            return await self._create_device_entry(user_input[CONF_DEVICE_ID])

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE_ID): vol.In(self._devices)}
            ),
        )

    async def _create_device_entry(self, device_id: str) -> ConfigFlowResult:
        """Create an entry for a discovered mower."""
        assert self._email is not None
        assert self._password is not None
        await self.async_set_unique_id(
            f"{self._email.strip().casefold()}:{device_id}"
        )
        self._abort_if_unique_id_configured()
        name = self._devices[device_id]
        return self.async_create_entry(
            title=name,
            data={
                CONF_EMAIL: self._email,
                CONF_PASSWORD: self._password,
                CONF_DEVICE_ID: device_id,
                CONF_DEVICE_NAME: name,
            },
        )

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
