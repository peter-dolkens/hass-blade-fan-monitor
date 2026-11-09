"""Fan speed and duty sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, REVOLUTIONS_PER_MINUTE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BladeFanConfigEntry
from .entity import BladeFanEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BladeFanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([BladeFanSpeed(coordinator, "speed"), BladeFanDuty(coordinator, "duty")])


class BladeFanSpeed(BladeFanEntity, SensorEntity):
    _attr_native_unit_of_measurement = REVOLUTIONS_PER_MINUTE
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return self.coordinator.data.rpm


class BladeFanDuty(BladeFanEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        return super().available and self._duty_known

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.duty

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"pwm": self.coordinator.data.pwm}
