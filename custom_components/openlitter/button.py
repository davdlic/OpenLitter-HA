"""OpenLitter button platform — one button per command."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import OpenLitterApiError
from .const import ATTR_WEIGHT_ENABLED, DOMAIN
from .coordinator import OpenLitterCoordinator
from .entity import OpenLitterEntity

_LOGGER = logging.getLogger(__name__)

BUTTONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(key="cycle",  translation_key="cycle",  icon="mdi:play"),
    ButtonEntityDescription(key="empty",  translation_key="empty",  icon="mdi:delete"),
    ButtonEntityDescription(key="reset",  translation_key="reset",  icon="mdi:restart"),
    ButtonEntityDescription(key="home",   translation_key="home",   icon="mdi:home-circle"),
    ButtonEntityDescription(key="pause",  translation_key="pause",  icon="mdi:pause"),
    ButtonEntityDescription(key="resume", translation_key="resume", icon="mdi:play-pause"),
    ButtonEntityDescription(key="tare",   translation_key="tare",   icon="mdi:scale-balance"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OpenLitterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OpenLitterButton(coordinator, desc) for desc in BUTTONS])


class OpenLitterButton(OpenLitterEntity, ButtonEntity):
    def __init__(
        self,
        coordinator: OpenLitterCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        # Hide the Tare button if the weight sensor isn't enabled on the device.
        if self.entity_description.key == "tare":
            return bool(self._data.get(ATTR_WEIGHT_ENABLED, False))
        return super().available

    async def async_press(self) -> None:
        try:
            await self.coordinator.api.send_command(self.entity_description.key)
        except OpenLitterApiError as err:
            _LOGGER.warning("Command %s failed: %s", self.entity_description.key, err)
            return
        # Fast feedback — request a refresh without waiting for the next tick.
        await self.coordinator.async_request_refresh()
