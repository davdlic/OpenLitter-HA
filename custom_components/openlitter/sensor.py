"""OpenLitter sensor platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CYCLE_COUNT,
    ATTR_HISTORY,
    ATTR_LAST_CYCLE,
    ATTR_RESET_IN_PROGRESS,
    ATTR_STATE,
    ATTR_UPTIME_SEC,
    ATTR_WEIGHT_ENABLED,
    ATTR_WEIGHT_KG,
    DOMAIN,
    STATE_LABELS,
)
from .coordinator import OpenLitterCoordinator
from .entity import OpenLitterEntity

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="state",
        translation_key="state",
        icon="mdi:state-machine",
    ),
    SensorEntityDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="cycle_count",
        translation_key="cycle_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
    ),
    SensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-outline",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OpenLitterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OpenLitterSensor(coordinator, desc) for desc in SENSORS])


class OpenLitterSensor(OpenLitterEntity, SensorEntity):
    """Generic sensor reading one key off the coordinator snapshot."""

    def __init__(
        self,
        coordinator: OpenLitterCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.key == "weight":
            return bool(self._data.get(ATTR_WEIGHT_ENABLED, False))
        return super().available

    @property
    def native_value(self) -> Any:
        data = self._data
        key = self.entity_description.key
        if key == "state":
            raw = data.get(ATTR_STATE)
            return STATE_LABELS.get(raw, raw)
        if key == "weight":
            return data.get(ATTR_WEIGHT_KG)
        if key == "cycle_count":
            return data.get(ATTR_CYCLE_COUNT)
        if key == "uptime":
            return data.get(ATTR_UPTIME_SEC)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "state":
            return None
        data = self._data
        return {
            "raw_state": data.get(ATTR_STATE),
            "last_cycle": data.get(ATTR_LAST_CYCLE),
            "reset_in_progress": data.get(ATTR_RESET_IN_PROGRESS, False),
            "history": self.coordinator.history,
        }
