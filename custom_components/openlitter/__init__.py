"""OpenLitter HA integration entry point."""
from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .api import OpenLitterApi
from .const import DEFAULT_PORT, DOMAIN
from .coordinator import OpenLitterCoordinator, async_wait_for_first_refresh

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.UPDATE,
]

FRONTEND_URL_BASE = f"/{DOMAIN}-frontend"
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
CARD_FILENAME = "openlitter-card.js"
CARD_VERSION = "0.1.4"  # bump on Lovelace card updates to bust browser cache
_FRONTEND_FLAG = f"{DOMAIN}_frontend_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenLitter from a config entry."""
    await _async_register_frontend(hass)

    session = aiohttp_client.async_get_clientsession(hass)
    api = OpenLitterApi(
        session,
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    coordinator = OpenLitterCoordinator(hass, entry, api)
    await async_wait_for_first_refresh(coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and tell HA's frontend to load it.

    Done once at the first config entry setup. The user therefore doesn't
    need to add a Lovelace resource by hand — opening any dashboard
    automatically picks up `custom:openlitter-card`."""
    if hass.data.get(_FRONTEND_FLAG):
        return
    # Prefer the modern async_register_static_paths + StaticPathConfig
    # (HA Core 2024.7+). Fall back to the legacy sync register_static_path
    # so the integration loads on older supported versions too.
    try:
        from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, FRONTEND_DIR, cache_headers=False)]
        )
    except ImportError:
        hass.http.register_static_path(
            FRONTEND_URL_BASE, FRONTEND_DIR, cache_headers=False
        )
    add_extra_js_url(
        hass, f"{FRONTEND_URL_BASE}/{CARD_FILENAME}?v={CARD_VERSION}"
    )
    hass.data[_FRONTEND_FLAG] = True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: OpenLitterCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload on options/data change."""
    await hass.config_entries.async_reload(entry.entry_id)
