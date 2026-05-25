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
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenLitterApi, OpenLitterApiError
from .const import (
    ATTR_CAT_PRESENT,
    ATTR_CYCLE_COUNT,
    ATTR_ERROR,
    ATTR_STATE,
    ATTR_WEIGHT_KG,
    CYCLING_STATES,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    EVENT_CAT_DETECTED,
    EVENT_CAT_LEFT,
    EVENT_CYCLE_COMPLETED,
    EVENT_CYCLE_STARTED,
    EVENT_ERROR,
)

# Number of consecutive REST poll failures before we ask HA to surface a
# Reauthenticate notification. Each poll is DEFAULT_POLL_INTERVAL_SECONDS
# apart, so 12 ticks at 5 s = 1 min of consistent failure.
REAUTH_AFTER_CONSECUTIVE_FAILURES = 12

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
        self._consecutive_failures = 0
        # Track the "interesting" subset of the last snapshot so we can
        # emit HA events on transitions (cat detected, cycle started, ...).
        self._prev_state: str | None = None
        self._prev_cat_present: bool | None = None
        self._prev_cycle_count: int | None = None
        self._prev_error: bool | None = None
        self._cat_detected_at: float | None = None

    @property
    def history(self) -> list[dict[str, Any]]:
        return self._history

    # --- DataUpdateCoordinator hook ----------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Polled fetch — runs on the configured interval."""
        try:
            status = await self.api.get_status()
        except OpenLitterApiError as err:
            self._consecutive_failures += 1
            # After ~1 minute of consistent failures (REAUTH_AFTER_CONSECUTIVE_FAILURES
            # ticks), surface a Reauthenticate notification so the user can
            # update the host without having to remove + re-add the
            # integration. Common cause: device IP changed (DHCP lease).
            if self._consecutive_failures >= REAUTH_AFTER_CONSECUTIVE_FAILURES:
                raise ConfigEntryAuthFailed(
                    f"Device unreachable after {self._consecutive_failures} attempts: {err}"
                ) from err
            raise UpdateFailed(str(err)) from err
        # Reset the failure counter as soon as we get a successful poll.
        self._consecutive_failures = 0
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

    @callback
    def handle_mqtt_update(self, partial: dict[str, Any]) -> None:
        """Called by the MQTT bridge for each individual topic update.

        Merges the partial payload into the cached status and emits a
        coordinator update so entities re-render. Last-write-wins across
        REST/WS/MQTT, so whichever transport is freshest sets the value."""
        if not partial:
            return
        self._merge(partial)
        self.async_set_updated_data(self._latest)

    # --- lifecycle ---------------------------------------------------

    async def async_start_ws(self) -> None:
        """Start the WS task. Called from async_setup_entry."""
        self.api.start_ws(self.handle_ws_message)

    async def async_stop(self) -> None:
        await self.api.stop_ws()

    # --- internals ---------------------------------------------------

    def _merge(self, fresh: dict[str, Any]) -> None:
        """Last-write-wins merge into _latest, then fire transition events.

        Detecting transitions on every merge (REST / WS / MQTT) gives us a
        single choke point — entities react to coordinator updates the same
        way regardless of which transport produced them."""
        # Keep history separate so it doesn't bloat _latest if also
        # passed through MQTT.
        for k, v in fresh.items():
            if k == "history":
                continue
            self._latest[k] = v
        self._fire_transition_events()

    def _fire_transition_events(self) -> None:
        """Emit `openlitter_*` HA events whenever a meaningful field flips.

        First call after a config-entry reload primes the prev_* fields and
        emits nothing; subsequent calls compare new vs prev and fire."""
        state = self._latest.get(ATTR_STATE)
        cat = bool(self._latest.get(ATTR_CAT_PRESENT, False))
        cycle_count = self._latest.get(ATTR_CYCLE_COUNT)
        error = bool(self._latest.get(ATTR_ERROR, False))
        weight = self._latest.get(ATTR_WEIGHT_KG)
        now = time.time()

        first_run = self._prev_state is None
        # Prime on first run — without this, the integration would fire
        # phantom "cycle started" / "cat detected" right after a HA reload
        # if the device happens to be mid-cycle at the moment we connect.
        if first_run:
            self._prev_state = state
            self._prev_cat_present = cat
            self._prev_cycle_count = cycle_count if isinstance(cycle_count, int) else None
            self._prev_error = error
            return

        bus = self.hass.bus
        device_data = {"device_id": self.entry.entry_id, "name": self.entry.title}

        # --- Cycle started: any non-cycling state -> a CYCLING_* state.
        if (
            state in CYCLING_STATES
            and self._prev_state not in CYCLING_STATES
        ):
            bus.async_fire(
                EVENT_CYCLE_STARTED,
                {**device_data, "trigger_state": state, "previous_state": self._prev_state},
            )

        # --- Cycle completed: cycle_count incremented. Most reliable
        # signal — the firmware only bumps it after a real cleaning cycle
        # (skips RESETTING + EMPTYING). Includes the last history entry
        # so automations can grab the duration without a second call.
        if (
            isinstance(cycle_count, int)
            and isinstance(self._prev_cycle_count, int)
            and cycle_count > self._prev_cycle_count
        ):
            last_entry = self._history[-1] if self._history else None
            bus.async_fire(
                EVENT_CYCLE_COMPLETED,
                {
                    **device_data,
                    "cycle_count": cycle_count,
                    "last_cycle": last_entry,
                },
            )

        # --- Cat detected / left.
        if cat and not self._prev_cat_present:
            self._cat_detected_at = now
            bus.async_fire(
                EVENT_CAT_DETECTED,
                {**device_data, "weight_kg": weight},
            )
        elif not cat and self._prev_cat_present:
            duration = (
                int(now - self._cat_detected_at)
                if self._cat_detected_at is not None
                else None
            )
            bus.async_fire(
                EVENT_CAT_LEFT,
                {**device_data, "duration_sec": duration},
            )
            self._cat_detected_at = None

        # --- Error transition (only on the leading edge).
        if error and not self._prev_error:
            bus.async_fire(
                EVENT_ERROR,
                {**device_data, "state": state},
            )

        self._prev_state = state
        self._prev_cat_present = cat
        if isinstance(cycle_count, int):
            self._prev_cycle_count = cycle_count
        self._prev_error = error


async def async_wait_for_first_refresh(coordinator: OpenLitterCoordinator) -> None:
    """Run the first poll and raise if it fails, so config_flow can validate."""
    await coordinator.async_config_entry_first_refresh()
    # Best-effort: kick the WS off, no need to wait for it to deliver.
    asyncio.create_task(coordinator.async_start_ws())
