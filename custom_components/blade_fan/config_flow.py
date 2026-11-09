"""Config and options flows for Compute Blade Fan."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback

from .const import (
    CONF_CHIP_LABEL,
    CONF_INTERVAL_SECONDS,
    CONF_PULSES_PER_REV,
    CONF_STALL_SECONDS,
    CONF_TACH_GPIO,
    DEFAULT_CHIP_LABEL,
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_PULSES_PER_REV,
    DEFAULT_STALL_SECONDS,
    DEFAULT_TACH_GPIO,
    DOMAIN,
)
from .hardware import probe

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PULSES_PER_REV, default=DEFAULT_PULSES_PER_REV): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=8)
        ),
        vol.Required(CONF_STALL_SECONDS, default=DEFAULT_STALL_SECONDS): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=600)
        ),
        vol.Required(CONF_INTERVAL_SECONDS, default=DEFAULT_INTERVAL_SECONDS): vol.All(
            vol.Coerce(int), vol.Range(min=2, max=300)
        ),
    }
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TACH_GPIO, default=DEFAULT_TACH_GPIO): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=63)
        ),
        vol.Required(CONF_CHIP_LABEL, default=DEFAULT_CHIP_LABEL): str,
    }
).extend(OPTIONS_SCHEMA.schema)


class BladeFanConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            label = user_input[CONF_CHIP_LABEL]
            gpio = user_input[CONF_TACH_GPIO]
            await self.async_set_unique_id(f"{label}-{gpio}")
            self._abort_if_unique_id_configured()
            if error := await self.hass.async_add_executor_job(probe, label, gpio):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Blade Fan",
                    data={CONF_CHIP_LABEL: label, CONF_TACH_GPIO: gpio},
                    options={k: user_input[k] for k in OPTIONS_SCHEMA.schema},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BladeFanOptionsFlow:
        return BladeFanOptionsFlow()


class BladeFanOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
