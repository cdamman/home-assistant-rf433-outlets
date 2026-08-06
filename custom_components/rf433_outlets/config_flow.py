"""Config flow for RF433 Outlets."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.util import slugify

from .const import (
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_POWER,
    CONF_PULSE_LENGTH,
    DEFAULT_POWER,
    DEFAULT_PULSE_LENGTH,
    DOMAIN,
)


class RF433OutletsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an RF433 outlet (one entry = one device)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single step: enter the outlet parameters."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # The unique id is derived from the name to prevent duplicates.
            await self.async_set_unique_id(slugify(user_input[CONF_NAME]))
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_ON_CODE: user_input[CONF_ON_CODE],
                    CONF_OFF_CODE: user_input[CONF_OFF_CODE],
                },
                # Parameters editable later through the options flow.
                options={
                    CONF_PULSE_LENGTH: user_input[CONF_PULSE_LENGTH],
                    CONF_POWER: user_input[CONF_POWER],
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_ON_CODE): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Required(CONF_OFF_CODE): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Required(
                    CONF_PULSE_LENGTH, default=DEFAULT_PULSE_LENGTH
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(CONF_POWER, default=DEFAULT_POWER): vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RF433OutletsOptionsFlow:
        """Return the options flow."""
        return RF433OutletsOptionsFlow()


class RF433OutletsOptionsFlow(OptionsFlow):
    """Edit the ON/OFF codes and the pulse length after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options
        data = self.config_entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ON_CODE,
                    default=current.get(CONF_ON_CODE, data[CONF_ON_CODE]),
                ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Required(
                    CONF_OFF_CODE,
                    default=current.get(CONF_OFF_CODE, data[CONF_OFF_CODE]),
                ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Required(
                    CONF_PULSE_LENGTH,
                    default=current.get(CONF_PULSE_LENGTH, DEFAULT_PULSE_LENGTH),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_POWER,
                    default=current.get(CONF_POWER, DEFAULT_POWER),
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
