"""OpenLitter firmware-update entity.

Polls the firmware repo's GitHub releases for the latest tag, compares
against the device's reported version, and uses /api/update to flash
when the user clicks Install — no PC, no PlatformIO."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .api import OpenLitterApiError
from .const import (
    ATTR_VERSION,
    DOMAIN,
    FIRMWARE_ASSET_PREFIX,
    FIRMWARE_ASSET_SUFFIX,
    GITHUB_RELEASES_URL,
)
from .coordinator import OpenLitterCoordinator
from .entity import OpenLitterEntity

_LOGGER = logging.getLogger(__name__)

# Poll GitHub at most once an hour. 60 requests/hour fits comfortably
# inside the unauthenticated 60/hour rate limit for the API.
GITHUB_POLL_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OpenLitterCoordinator = hass.data[DOMAIN][entry.entry_id]
    entity = OpenLitterUpdate(coordinator)
    async_add_entities([entity])
    # First poll right away; refresh periodically thereafter.
    await entity.async_refresh_latest()
    entry.async_on_unload(
        async_track_time_interval(
            hass, lambda _now: hass.async_create_task(entity.async_refresh_latest()),
            GITHUB_POLL_INTERVAL,
        )
    )


class OpenLitterUpdate(OpenLitterEntity, UpdateEntity):
    """Update entity backed by GitHub releases + /api/update."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_translation_key = "firmware"

    def __init__(self, coordinator: OpenLitterCoordinator) -> None:
        super().__init__(coordinator, "firmware_update")
        self._latest_version: str | None = None
        self._release_url: str | None = None
        self._release_summary: str | None = None
        self._asset_url: str | None = None
        self._installing = False
        self._in_progress_pct: int | None = None

    # --- UpdateEntity required props ---------------------------------

    @property
    def installed_version(self) -> str | None:
        v = self._data.get(ATTR_VERSION)
        return v if isinstance(v, str) else None

    @property
    def latest_version(self) -> str | None:
        return self._latest_version

    @property
    def release_url(self) -> str | None:
        return self._release_url

    @property
    def release_summary(self) -> str | None:
        return self._release_summary

    @property
    def in_progress(self) -> bool | int | None:
        if not self._installing:
            return False
        return self._in_progress_pct if self._in_progress_pct is not None else True

    # --- Install -----------------------------------------------------

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Download the firmware.bin asset from the GitHub release and
        POST it to /api/update. The device reboots itself on success."""
        if not self._asset_url:
            _LOGGER.warning("No firmware asset URL known; refusing to install")
            return
        session = aiohttp_client.async_get_clientsession(self.hass)
        self._installing = True
        self._in_progress_pct = 0
        self.async_write_ha_state()
        try:
            firmware = await self._download(session, self._asset_url)
            self._in_progress_pct = 50
            self.async_write_ha_state()
            await self.coordinator.api.upload_update(
                firmware, kind="firmware",
                progress_cb=self._on_upload_progress,
            )
            # Device reboots on success — give it time to come back, then
            # the coordinator's next poll will pick up the new version.
            await asyncio.sleep(10)
        except (OpenLitterApiError, aiohttp.ClientError) as err:
            _LOGGER.error("Firmware install failed: %s", err)
        finally:
            self._installing = False
            self._in_progress_pct = None
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    # --- GitHub release polling --------------------------------------

    async def async_refresh_latest(self) -> None:
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            async with session.get(GITHUB_RELEASES_URL, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "GitHub releases endpoint returned %s", resp.status
                    )
                    return
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("GitHub releases fetch failed: %s", err)
            return

        tag = data.get("tag_name") or ""
        version = tag.lstrip("v") or None
        asset_url = None
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.startswith(FIRMWARE_ASSET_PREFIX) and name.endswith(
                FIRMWARE_ASSET_SUFFIX
            ):
                asset_url = asset.get("browser_download_url")
                break

        self._latest_version = version
        self._release_url = data.get("html_url")
        self._release_summary = (data.get("body") or "").strip() or None
        self._asset_url = asset_url
        self.async_write_ha_state()

    # --- helpers -----------------------------------------------------

    async def _download(self, session: aiohttp.ClientSession, url: str) -> bytes:
        async with session.get(url, timeout=120) as resp:
            resp.raise_for_status()
            return await resp.read()

    def _on_upload_progress(self, pct: int) -> None:
        self._in_progress_pct = pct
        self.async_write_ha_state()
