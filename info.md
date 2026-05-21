# OpenLitter

Home Assistant integration for OpenLitter — open source ESP32 firmware that
replaces the original board of a Litter Robot 1 / 2 / 3.

- Local-push: REST + WebSocket directly to the device (no broker needed).
- Auto-discovery via mDNS.
- Rich entities: state, weight, cycle count, HOME / DUMP / CAT live sensors,
  buttons for cycle / empty / reset / pause / resume, and an Update entity
  that flashes the device from a GitHub release without any PC tools.
- Ships with a Lovelace card.

See the README for full setup, entity list, and roadmap.
