"""Fan stall problem sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
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
    async_add_entities([BladeFanStall(entry.runtime_data, "stall")])


class BladeFanStall(BladeFanEntity, BinarySensorEntity):
    """On when the fan is commanded to spin but reports no tach pulses."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def available(self) -> bool:
        # Without the pwm-fan duty there is no "should be spinning" to compare to.
        return super().available and self._duty_known

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.stalled
