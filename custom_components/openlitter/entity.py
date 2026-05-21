"""Base entity class for OpenLitter — provides device info + coordinator hookup."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_VERSION, DOMAIN, MANUFACTURER, MODEL
from .coordinator import OpenLitterCoordinator


class OpenLitterEntity(CoordinatorEntity[OpenLitterCoordinator]):
    """Shared base — all platforms inherit this for unified device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OpenLitterCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._key = key

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data or {}
        network = data.get("network", {}) if isinstance(data, dict) else {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.coordinator.entry.title,
            sw_version=data.get(ATTR_VERSION) if isinstance(data, dict) else None,
            configuration_url=f"http://{self.coordinator.api._host}",
            hw_version=network.get("hostname"),
        )

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}
