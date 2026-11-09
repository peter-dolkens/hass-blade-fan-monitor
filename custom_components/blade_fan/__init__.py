"""Compute Blade Fan: tach speed, pwm-fan duty and stall detection.

The kernel pwm-fan driver (dtoverlay=pwm-fan in config.txt) drives the fan from
a CPU-temperature curve but never reads its tach. This integration only
observes: it counts tach edges on a GPIO and reads the duty the driver applied.
It never drives the fan, so it can't affect cooling.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ISSUE_PWM_FAN_MISSING
from .coordinator import BladeFanConfigEntry, BladeFanCoordinator
from .hardware import ChipNotFound

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

DOCS_URL = "https://github.com/peter-dolkens/hass-blade-fan-monitor#fan-control"


async def async_setup_entry(hass: HomeAssistant, entry: BladeFanConfigEntry) -> bool:
    coordinator = BladeFanCoordinator(hass, entry)
    try:
        await hass.async_add_executor_job(coordinator.start)
    except (ChipNotFound, OSError) as err:
        raise ConfigEntryNotReady(f"Cannot claim tach GPIO: {err}") from err

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await hass.async_add_executor_job(coordinator.stop)
        raise

    entry.runtime_data = coordinator

    @callback
    def _update_issue() -> None:
        # No pwm-fan hwmon = the overlay isn't loaded: nothing is controlling the
        # fan, which is worth surfacing in Repairs, not just a missing sensor.
        if coordinator.data is not None and coordinator.data.pwm is None:
            ir.async_create_issue(
                hass,
                DOMAIN,
                ISSUE_PWM_FAN_MISSING,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_PWM_FAN_MISSING,
                learn_more_url=DOCS_URL,
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, ISSUE_PWM_FAN_MISSING)

    _update_issue()
    entry.async_on_unload(coordinator.async_add_listener(_update_issue))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BladeFanConfigEntry) -> bool:
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.async_add_executor_job(entry.runtime_data.stop)
        ir.async_delete_issue(hass, DOMAIN, ISSUE_PWM_FAN_MISSING)
    return unloaded
