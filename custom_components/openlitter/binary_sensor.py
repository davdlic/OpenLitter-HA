"""OpenLitter binary sensor platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CAT_PRESENT,
    ATTR_DUMP_POSITION,
    ATTR_ERROR,
    ATTR_HOME_POSITION,
    ATTR_STATE,
    DOMAIN,
)
from .coordinator import OpenLitterCoordinator
from .entity import OpenLitterEntity

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="cat_present",
        translation_key="cat_present",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="home_position",
        translation_key="home_position",
        icon="mdi:home-circle",
    ),
    BinarySensorEntityDescription(
        key="dump_position",
        translation_key="dump_position",
        icon="mdi:delete-empty",
    ),
    BinarySensorEntityDescription(
        key="error",
        translation_key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OpenLitterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [OpenLitterBinarySensor(coordinator, desc) for desc in BINARY_SENSORS]
    )


class OpenLitterBinarySensor(OpenLitterEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: OpenLitterCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data: dict[str, Any] = self._data
        key = self.entity_description.key
        if key == "cat_present":
            return bool(data.get(ATTR_CAT_PRESENT, False))
        if key == "home_position":
            return bool(data.get(ATTR_HOME_POSITION, False))
        if key == "dump_position":
            return bool(data.get(ATTR_DUMP_POSITION, False))
        if key == "error":
            return data.get(ATTR_STATE) == "ERROR"
        return None
