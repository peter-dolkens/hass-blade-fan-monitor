"""Shared base for Compute Blade Fan entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BladeFanCoordinator


class BladeFanEntity(CoordinatorEntity[BladeFanCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: BladeFanCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name="Blade Fan",
            manufacturer="Uptime Lab",
            model="Compute Blade Fan Unit",
        )

    @property
    def _duty_known(self) -> bool:
        return self.coordinator.data is not None and self.coordinator.data.duty is not None
