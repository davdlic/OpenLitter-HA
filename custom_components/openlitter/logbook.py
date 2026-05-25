"""Describe OpenLitter events for the HA Logbook UI.

The coordinator fires `openlitter_*` events on cycle starts/completions, cat
visits, and error transitions. This module turns those bus events into
human-readable lines like:

    OpenLitter — Cat entered the litter robot

so users get a per-device timeline in Settings -> Logbook without having to
build a custom template sensor or automation."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    DOMAIN,
    EVENT_CAT_DETECTED,
    EVENT_CAT_LEFT,
    EVENT_CYCLE_COMPLETED,
    EVENT_CYCLE_STARTED,
    EVENT_ERROR,
)


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None],
) -> None:
    """Register a describer for every OpenLitter event."""

    def _name(event: Event) -> str:
        return event.data.get("name") or "OpenLitter"

    @callback
    def _cycle_started(event: Event) -> dict[str, Any]:
        return {
            LOGBOOK_ENTRY_NAME: _name(event),
            LOGBOOK_ENTRY_MESSAGE: "started a cleaning cycle",
        }

    @callback
    def _cycle_completed(event: Event) -> dict[str, Any]:
        last = event.data.get("last_cycle") or {}
        duration = last.get("dur") or last.get("duration_sec")
        msg = "completed a cleaning cycle"
        if isinstance(duration, int) and duration > 0:
            msg = f"{msg} ({duration}s)"
        return {LOGBOOK_ENTRY_NAME: _name(event), LOGBOOK_ENTRY_MESSAGE: msg}

    @callback
    def _cat_detected(event: Event) -> dict[str, Any]:
        weight = event.data.get("weight_kg")
        msg = "detected a cat"
        if isinstance(weight, (int, float)) and weight > 0:
            msg = f"{msg} ({weight:.2f} kg)"
        return {LOGBOOK_ENTRY_NAME: _name(event), LOGBOOK_ENTRY_MESSAGE: msg}

    @callback
    def _cat_left(event: Event) -> dict[str, Any]:
        dur = event.data.get("duration_sec")
        msg = "saw the cat leave"
        if isinstance(dur, int) and dur > 0:
            msg = f"{msg} (after {dur}s inside)"
        return {LOGBOOK_ENTRY_NAME: _name(event), LOGBOOK_ENTRY_MESSAGE: msg}

    @callback
    def _error(event: Event) -> dict[str, Any]:
        return {
            LOGBOOK_ENTRY_NAME: _name(event),
            LOGBOOK_ENTRY_MESSAGE: "reported an error",
        }

    async_describe_event(DOMAIN, EVENT_CYCLE_STARTED, _cycle_started)
    async_describe_event(DOMAIN, EVENT_CYCLE_COMPLETED, _cycle_completed)
    async_describe_event(DOMAIN, EVENT_CAT_DETECTED, _cat_detected)
    async_describe_event(DOMAIN, EVENT_CAT_LEFT, _cat_left)
    async_describe_event(DOMAIN, EVENT_ERROR, _error)
