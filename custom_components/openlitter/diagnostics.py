"""Diagnostics dump for the OpenLitter integration.

Triggered by the "Download diagnostics" button on the device page
(Settings -> Devices & Services -> OpenLitter -> ... -> Download diagnostics).
Bundles the config entry, the latest coordinator snapshot, the recent
history array, and the on-device log buffer into a single JSON file so
users can attach it to a bug report without having to copy/paste from
multiple places.

Sensitive fields are redacted before download — OTA password, host (since
it may be a public DDNS), and any network MAC/IP details."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import OpenLitterApiError
from .const import (
    ATTR_NETWORK,
    CONF_HOST,
    CONF_OTA_PASSWORD,
    DOMAIN,
)
from .coordinator import OpenLitterCoordinator

# Fields to redact from the entry's data + the live status snapshot.
TO_REDACT_ENTRY = {CONF_HOST, CONF_OTA_PASSWORD}
TO_REDACT_STATUS = {ATTR_NETWORK}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: OpenLitterCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Best-effort fetch of the on-device log buffer. We don't fail the
    # whole diagnostics export if the device is unreachable — the rest of
    # the snapshot is still useful for debugging exactly that case.
    logs: str | None = None
    try:
        logs = await coordinator.api.get_logs()
    except OpenLitterApiError as err:
        logs = f"[unavailable: {err}]"

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT_ENTRY),
        },
        "status": async_redact_data(dict(coordinator.data or {}), TO_REDACT_STATUS),
        "history": list(coordinator.history),
        "consecutive_failures": coordinator._consecutive_failures,
        "logs": logs,
    }
