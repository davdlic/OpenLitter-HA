"""Optional MQTT bridge for the OpenLitter integration.

Subscribes to the topics the firmware publishes (when its MQTT
integration is enabled and the user has the Home Assistant MQTT
integration configured) and feeds the values into the same coordinator
that REST + WebSocket already populate. Last-write-wins, so whichever
transport delivers the freshest value updates the entities.

The bridge is best-effort: it tolerates a missing HA MQTT integration,
malformed payloads, and partial topic coverage. If MQTT isn't there
the integration keeps working over REST + WS exactly as before.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)


# Map firmware MQTT topics (relative to topic_base) to the status keys
# the coordinator already understands. Keys must match what
# StateMachine::serializeStatus() produces on the firmware side.
TOPIC_FIELDS: dict[str, str] = {
    "state":          "state",
    "cat_present":    "cat_present",
    "weight":         "weight_kg",
    "cycle_count":    "cycle_count",
    "last_cycle":     "last_cycle",
    "error":          "error",
    "availability":   "_availability",  # not in status payload but useful
}


class OpenLitterMqttBridge:
    """Subscribe to the firmware's MQTT topics and forward into the coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,  # avoid circular type import
        topic_base: str,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._topic_base = topic_base.rstrip("/")
        self._unsubs: list[Callable[[], None]] = []

    async def async_start(self) -> bool:
        """Subscribe to all known topics. Returns False if HA MQTT isn't
        available (integration not configured, or import fails)."""
        try:
            # Newer HA versions expose mqtt.async_wait_for_mqtt_client; older
            # ones don't. We just try async_subscribe — if MQTT isn't set
            # up, it raises and we bail.
            for suffix, field in TOPIC_FIELDS.items():
                topic = f"{self._topic_base}/{suffix}"
                unsub = await mqtt.async_subscribe(
                    self._hass,
                    topic,
                    self._make_handler(field, suffix),
                    qos=0,
                )
                self._unsubs.append(unsub)
        except Exception as err:  # noqa: BLE001
            _LOGGER.info(
                "MQTT bridge disabled (HA MQTT integration not available?): %s",
                err,
            )
            await self.async_stop()
            return False
        _LOGGER.info(
            "MQTT bridge listening on %s/* (%d topics)",
            self._topic_base,
            len(self._unsubs),
        )
        return True

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                pass
        self._unsubs = []

    def _make_handler(self, field: str, suffix: str):
        @callback
        def handler(msg) -> None:
            raw = msg.payload
            payload = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
            value = self._parse(field, payload)
            if value is None:
                return
            self._coordinator.handle_mqtt_update({field: value})

        return handler

    @staticmethod
    def _parse(field: str, payload: str) -> Optional[Any]:
        payload = payload.strip()
        if not payload:
            return None
        # Boolean fields (HA discovery uses "true"/"false" lower-case strings)
        if field in ("cat_present",):
            if payload.lower() in ("true", "on", "1"):
                return True
            if payload.lower() in ("false", "off", "0"):
                return False
            return None
        # Numeric fields
        if field in ("weight_kg",):
            try:
                return float(payload)
            except ValueError:
                return None
        if field in ("cycle_count", "last_cycle"):
            try:
                return int(payload)
            except ValueError:
                return None
        # _availability is special — we don't store it in status, just log
        if field == "_availability":
            _LOGGER.debug("MQTT availability: %s", payload)
            return None
        # String fields (state, error)
        return payload
