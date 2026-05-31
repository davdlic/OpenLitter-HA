# Changelog

All notable changes to this project will be documented here. The format
loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.1] — 2026-06-01

### Added
- `BOOT_RECOVERY` mapped to the friendly label **Recovering** in the state
  sensor and Lovelace card. Tracks the matching firmware v1.0.1, which
  introduces a safe two-leg boot recovery to avoid re-dumping clean litter
  after a mains glitch during a cycle.

## [1.0.0] — 2026-05-26

First stable release. Entity ids, attributes, bus event names and the
Lovelace card's options are now considered public contract — breaking
changes will require a 2.0.

### Notes
- Companion firmware ([davdlic/OpenLitter](https://github.com/davdlic/OpenLitter))
  cuts v1.0.0 in parallel. Older firmware (≥ v0.4.1) remains supported.

## [0.3.0] — 2026-05-25

### Added
- Bus events on transitions (`openlitter_cycle_started`, `_completed`,
  `_cat_detected`, `_cat_left`, `_error`) detected centrally in the
  coordinator's `_merge`, so they work the same over REST / WS / MQTT.
  First merge after a HA reload is suppressed to avoid phantom replays.
- Logbook describer (`logbook.py`) turns each event into a human-readable
  line under Settings → Logbook (e.g. "OpenLitter completed a cleaning
  cycle (47s)").
- Diagnostics download (`diagnostics.py`) — config entry data (host +
  OTA password redacted), live status, recent history, and the on-device
  log buffer, all in one JSON for bug reports.
- README sections: Screenshots, Events & automations with YAML examples,
  Diagnostics, Troubleshooting. Pre-1.0 callout, My Home Assistant
  deep-link buttons, FAQ, Known limitations, Acknowledgments.

### Changed
- `after_dependencies` now includes `logbook` so HA loads it before the
  describer registers.

## [0.2.2] — 2026-05-25

### Added
- Config-flow **reconfigure** — Settings → Devices & Services → OpenLitter
  → Configure. Lets users update host / port / OTA password / MQTT
  settings without removing and re-adding the integration.
- Config-flow **reauth** — coordinator raises `ConfigEntryAuthFailed`
  after 12 consecutive REST failures (~1 min at the 5 s poll interval),
  surfacing the standard HA Reauthenticate notification. Common case:
  the device picked up a new DHCP lease.

## [0.2.1] — 2026-05-25

### Changed
- Documentation refresh for the v0.2.x line: Compatibility table now
  mentions the MQTT bridge and bundled brand assets.

## [0.2.0] — 2026-05-25

### Added
- MQTT bridge (`mqtt_bridge.py`) — when HA's MQTT integration is
  configured and Use MQTT is ticked, the integration subscribes to the
  firmware's `{topic_base}/*` topics and merges them with the REST + WS
  feed (last-write-wins).
- Brand assets bundled in `custom_components/openlitter/brand/`. HA
  2026.3+ serves these via its proxy — no home-assistant/brands PR
  needed.

## [0.1.9] — 2026-05-25

### Fixed
- Lovelace card: extended fuzzy entity resolution to button presses, so
  command buttons keep working after HA renames an entity_id.

## [0.1.8] — 2026-05-25

### Fixed
- Lovelace card: HOME / DUMP / CAT pills and weight stat now resolve
  entities by contains-match across `{domain}.{base}_*`, because HA's
  slugifier generates entity ids from the friendly NAME, not the key
  ("Home position" → `home_position`, not `home_position_sensor`).
- Hidden weight pill entirely when the firmware reports the weight
  sensor disabled (used to render "off").

## [0.1.7] — 2026-05-25

Initial public HACS release. REST + WebSocket client, DataUpdateCoordinator
with WS push + 5 s REST poll fallback, config flow (zeroconf + manual),
sensor / binary_sensor / button / update platforms, bundled Lovelace card,
Update entity that flashes both `firmware.bin` and `littlefs.bin` from
each GitHub release.

[1.0.1]: https://github.com/davdlic/OpenLitter-HA/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/davdlic/OpenLitter-HA/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/davdlic/OpenLitter-HA/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/davdlic/OpenLitter-HA/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/davdlic/OpenLitter-HA/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/davdlic/OpenLitter-HA/compare/v0.1.9...v0.2.0
[0.1.9]: https://github.com/davdlic/OpenLitter-HA/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/davdlic/OpenLitter-HA/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/davdlic/OpenLitter-HA/releases/tag/v0.1.7
