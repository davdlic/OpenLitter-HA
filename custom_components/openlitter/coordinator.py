"""DataUpdateCoordinator fan-in for OpenLitter.

Three input sources, last-write-wins:

  1. WebSocket subscription on /ws — primary low-latency source.
  2. REST poll every DEFAULT_POLL_INTERVAL_SECONDS — keeps us honest if
     the WS hiccups and lets us fetch /api/history alongside.
  3. MQTT (optional) — if the user has HA's MQTT integration configured
     and ticks Use MQTT in the config flow, we subscribe to
     {topic_base}/state and friends as well.

The coordinator stores the latest status dict (with the same keys the
firmware emits) plus the most recent history array.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenLitterApi, OpenLitterApiError
from .const import DEFAULT_POLL_INTERVAL_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OpenLitterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that aggregates REST/WS/MQTT updates into one snapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: OpenLitterApi,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL_SECONDS),
        )
        self.entry = entry
        self.api = api
        self._history: list[dict[str, Any]] = []
        self._latest: dict[str, Any] = {}

    @property
    def history(self) -> list[dict[str, Any]]:
        return self._history

    # --- DataUpdateCoordinator hook ----------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Polled fetch — runs on the configured interval."""
        try:
            status = await self.api.get_status()
        except OpenLitterApiError as err:
            raise UpdateFailed(str(err)) from err
        # History is part of the broadcast payload, but if not, fetch
        # separately. Cheap on the device.
        if "history" in status:
            self._history = status.get("history", [])
        else:
            try:
                self._history = await self.api.get_history()
            except OpenLitterApiError:
                # Status is enough; history can wait for the next tick.
                pass
        self._merge(status)
        return self._latest

    # --- WS / MQTT push paths ----------------------------------------

    @callback
    def handle_ws_message(self, payload: dict[str, Any]) -> None:
        """Called by OpenLitterApi for every /ws frame.

        Status frames update state, log frames are ignored at this layer
        (a future log entity could subscribe to them via the same callback)."""
        msg_type = payload.get("type")
        if msg_type == "status":
            if "history" in payload:
                self._history = payload.get("history", [])
            self._merge(payload)
            self.async_set_updated_data(self._latest)
        # Log messages: leave for later (could feed into HA logbook).

    @callback
    def handle_mqtt_status(self, status: dict[str, Any]) -> None:
        """Called by the MQTT bridge when it gathers a full status."""
        self._merge(status)
        self.async_set_updated_data(self._latest)

    # --- lifecycle ---------------------------------------------------

    async def async_start_ws(self) -> None:
        """Start the WS task. Called from async_setup_entry."""
        self.api.start_ws(self.handle_ws_message)

    async def async_stop(self) -> None:
        await self.api.stop_ws()

    # --- internals ---------------------------------------------------

    def _merge(self, fresh: dict[str, Any]) -> None:
        """Last-write-wins merge into _latest."""
        # Keep history separate so it doesn't bloat _latest if also
        # passed through MQTT.
        for k, v in fresh.items():
            if k == "history":
                continue
            self._latest[k] = v


async def async_wait_for_first_refresh(coordinator: OpenLitterCoordinator) -> None:
    """Run the first poll and raise if it fails, so config_flow can validate."""
    await coordinator.async_config_entry_first_refresh()
    # Best-effort: kick the WS off, no need to wait for it to deliver.
    asyncio.create_task(coordinator.async_start_ws())
