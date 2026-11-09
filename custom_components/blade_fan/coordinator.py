"""Samples the tach counter and pwm-fan duty on a fixed interval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CHIP_LABEL,
    CONF_INTERVAL_SECONDS,
    CONF_PULSES_PER_REV,
    CONF_STALL_SECONDS,
    CONF_TACH_GPIO,
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_PULSES_PER_REV,
    DEFAULT_STALL_SECONDS,
    DOMAIN,
    PWM_FAN_HWMON,
)
from .hardware import ChipNotFound, TachCounter, find_chip, find_hwmon, read_int

_LOGGER = logging.getLogger(__name__)

type BladeFanConfigEntry = ConfigEntry[BladeFanCoordinator]


@dataclass(frozen=True)
class FanState:
    rpm: int
    # None when no pwm-fan hwmon device exists (overlay not loaded).
    pwm: int | None
    duty: int | None
    stalled: bool


class BladeFanCoordinator(DataUpdateCoordinator[FanState]):
    """Owns the tach counter thread; restarts it if it dies."""

    config_entry: BladeFanConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BladeFanConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_INTERVAL_SECONDS, DEFAULT_INTERVAL_SECONDS)
            ),
        )
        self._label: str = entry.data[CONF_CHIP_LABEL]
        self._gpio: int = entry.data[CONF_TACH_GPIO]
        self._pulses_per_rev: int = entry.options.get(CONF_PULSES_PER_REV, DEFAULT_PULSES_PER_REV)
        self._stall_seconds: int = entry.options.get(CONF_STALL_SECONDS, DEFAULT_STALL_SECONDS)
        self._tach: TachCounter | None = None
        self._hwmon: str | None = None
        self._last_sample = 0.0
        self._last_ok = 0.0

    def start(self) -> None:
        """Claim the tach line and start counting (blocking)."""
        self._tach = TachCounter(find_chip(self._label), self._gpio)
        self._tach.start()
        self._last_sample = self._last_ok = time.monotonic()

    def stop(self) -> None:
        """Stop counting and release the line (blocking)."""
        if self._tach is not None:
            self._tach.stop()
            self._tach = None

    async def _async_update_data(self) -> FanState:
        return await self.hass.async_add_executor_job(self._sample)

    def _sample(self) -> FanState:
        if self._tach is None or not self._tach.is_alive():
            _LOGGER.warning("Tach counter not running; restarting it")
            self.stop()
            try:
                self.start()
            except (ChipNotFound, OSError) as err:
                raise UpdateFailed(f"Cannot claim tach GPIO {self._gpio}: {err}") from err

        now = time.monotonic()
        pulses = self._tach.drain()
        elapsed = now - self._last_sample
        self._last_sample = now
        rpm = round(pulses / self._pulses_per_rev / elapsed * 60) if elapsed > 0 else 0

        # Re-find the hwmon device if it vanishes (numbering is per boot).
        if self._hwmon is None:
            self._hwmon = find_hwmon(PWM_FAN_HWMON)
        pwm = read_int(f"{self._hwmon}/pwm1") if self._hwmon else None
        if pwm is None:
            self._hwmon = None
        duty = None if pwm is None else round(pwm * 100 / 255)

        # A stall is commanded duty with no tach for stall_seconds. Duty 0 (fan
        # deliberately stopped) or unknown duty never counts against it.
        if pulses > 0 or not duty:
            self._last_ok = now
        stalled = duty is not None and now - self._last_ok >= self._stall_seconds
        if stalled and (self.data is None or not self.data.stalled):
            _LOGGER.error("Fan stalled: duty %s%% but no tach pulses for %ss", duty, self._stall_seconds)

        return FanState(rpm=rpm, pwm=pwm, duty=duty, stalled=stalled)
