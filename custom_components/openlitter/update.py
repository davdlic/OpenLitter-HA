"""OpenLitter firmware-update entity.

Polls the firmware repo's GitHub releases for the latest tag, compares
against the device's reported version, and uses /api/update to flash
when the user clicks Install — no PC, no PlatformIO.

Installs **both** the firmware.bin and the littlefs.bin assets of the
release, sequentially. The firmware partition holds the ESP32 program;
the LittleFS partition holds the Web UI. Most releases change both, so
installing only one would leave the Web UI on an old version (missing
new buttons, etc.). Installing both, waiting for the device to come
back between flashes, keeps the install button truly "one-click"."""
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
    LITTLEFS_ASSET_SUFFIX,
)
from .coordinator import OpenLitterCoordinator
from .entity import OpenLitterEntity

_LOGGER = logging.getLogger(__name__)

# Poll GitHub at most once an hour. 60 requests/hour fits comfortably
# inside the unauthenticated 60/hour rate limit for the API.
GITHUB_POLL_INTERVAL = timedelta(hours=1)

# Maximum time to wait for the device to come back online after a
# reboot, in seconds. Real reboots happen in ~5-10 s; this is the
# safety net before we give up and surface an error.
REBOOT_WAIT_TIMEOUT = 90


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
        self._firmware_url: str | None = None
        self._littlefs_url: str | None = None
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
        """Install firmware.bin first, then littlefs.bin. Waits for the
        device to come back online between flashes."""
        if not self._firmware_url:
            _LOGGER.warning("No firmware asset URL known; refusing to install")
            return
        session = aiohttp_client.async_get_clientsession(self.hass)
        self._installing = True
        self._set_progress(0)
        try:
            # --- Stage 1/2: firmware (ESP32 program) ---
            self._set_progress(5)
            firmware = await self._download(session, self._firmware_url)
            self._set_progress(25)
            await self.coordinator.api.upload_update(firmware, kind="firmware")
            self._set_progress(40)
            await self._wait_for_device_online()
            self._set_progress(50)

            # --- Stage 2/2: filesystem (Web UI) ---
            if self._littlefs_url:
                littlefs = await self._download(session, self._littlefs_url)
                self._set_progress(70)
                await self.coordinator.api.upload_update(littlefs, kind="fs")
                self._set_progress(90)
                await self._wait_for_device_online()
            else:
                _LOGGER.info(
                    "Release has no littlefs.bin asset; firmware-only update."
                )
            self._set_progress(100)
        except (OpenLitterApiError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Update failed: %s", err)
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
        firmware_url: str | None = None
        littlefs_url: str | None = None
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if not name.startswith(FIRMWARE_ASSET_PREFIX):
                continue
            url = asset.get("browser_download_url")
            if name.endswith(FIRMWARE_ASSET_SUFFIX):
                firmware_url = url
            elif name.endswith(LITTLEFS_ASSET_SUFFIX):
                littlefs_url = url

        self._latest_version = version
        self._release_url = data.get("html_url")
        self._release_summary = (data.get("body") or "").strip() or None
        self._firmware_url = firmware_url
        self._littlefs_url = littlefs_url
        self.async_write_ha_state()

    # --- helpers -----------------------------------------------------

    async def _download(self, session: aiohttp.ClientSession, url: str) -> bytes:
        async with session.get(url, timeout=120) as resp:
            resp.raise_for_status()
            return await resp.read()

    def _set_progress(self, pct: int) -> None:
        self._in_progress_pct = pct
        self.async_write_ha_state()

    async def _wait_for_device_online(self) -> None:
        """Poll /api/status until the device answers again (or timeout).

        The device sends its HTTP response *before* rebooting, so right
        after a successful upload it'll start refusing connections for
        a few seconds. We wait, then poll until we get a valid status
        payload back."""
        # Initial cooldown — device finishes writing flash and reboots.
        await asyncio.sleep(3)
        deadline = asyncio.get_event_loop().time() + REBOOT_WAIT_TIMEOUT
        while asyncio.get_event_loop().time() < deadline:
            try:
                await self.coordinator.api.get_status(timeout=1.5)
                return
            except OpenLitterApiError:
                await asyncio.sleep(1)
        raise OpenLitterApiError(
            f"Device did not come back online within {REBOOT_WAIT_TIMEOUT}s"
        )
