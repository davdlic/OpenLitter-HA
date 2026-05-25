# OpenLitter

Home Assistant integration for OpenLitter — open source ESP32 firmware that
replaces the original board of a Litter Robot 1 / 2 / 3.

- Local-push: REST + WebSocket directly to the device (no broker needed).
- Optional MQTT bridge — if HA's MQTT integration is configured, the
  integration also subscribes to the firmware's MQTT topics; last-write-wins
  across all three transports.
- Auto-discovery via mDNS.
- Rich entities: state, weight, cycle count, HOME / DUMP / CAT live sensors,
  buttons for cycle / empty / reset / home / pause / resume / tare, and an
  Update entity that flashes both firmware AND Web UI from a GitHub release
  without any PC tools.
- Ships with a Lovelace card (auto-registered, no manual Resource entry).

See the README for full setup, entity list, and roadmap.
