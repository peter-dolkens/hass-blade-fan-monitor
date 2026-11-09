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
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

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

def _int_box(minimum: int, maximum: int, unit: str | None = None) -> vol.All:
    """Integer typed into a box. A bare vol.Range renders as a slider, which is
    awkward for picking a GPIO number or a number of seconds."""
    config = NumberSelectorConfig(min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return vol.All(NumberSelector(config), vol.Coerce(int))


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PULSES_PER_REV, default=DEFAULT_PULSES_PER_REV): _int_box(1, 8),
        vol.Required(CONF_STALL_SECONDS, default=DEFAULT_STALL_SECONDS): _int_box(5, 600, "s"),
        vol.Required(CONF_INTERVAL_SECONDS, default=DEFAULT_INTERVAL_SECONDS): _int_box(2, 300, "s"),
    }
)

OPTION_KEYS = (CONF_PULSES_PER_REV, CONF_STALL_SECONDS, CONF_INTERVAL_SECONDS)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TACH_GPIO, default=DEFAULT_TACH_GPIO): _int_box(0, 63),
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
                    # Plain string keys: iterating OPTIONS_SCHEMA.schema yields
                    # Required markers, which can't be stored (0.3.0-0.4.1 bug).
                    options={k: user_input[k] for k in OPTION_KEYS},
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
