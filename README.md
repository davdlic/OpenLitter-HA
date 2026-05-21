<!--
openlitter-ha - Home Assistant integration + Lovelace card for OpenLitter
Copyright (C) 2024 David Lopes (https://github.com/davdlic)
Licensed under the GNU General Public License v3.0 - see LICENSE
-->

# OpenLitter — Home Assistant integration

Custom integration and Lovelace card for [OpenLitter](https://github.com/davdlic/OpenLitter), the open source ESP32 firmware that replaces the original board of a Litter Robot 1 / 2 / 3.

> ⚠️ Pre-1.0. APIs and entity ids may change. Tracks the latest OpenLitter firmware release on `main`.

---

## What you get

- **Local-push integration** — talks REST + WebSocket to the device directly, no broker needed. If you happen to have MQTT configured, the integration uses it transparently for lower latency.
- **Auto-discovery** via mDNS — HA finds `openlitter.local` on your LAN without you typing an IP.
- **Rich entities**: state with friendly label and full history, weight, cycle count, HOME/DUMP/CAT raw sensor states, cat-present binary sensor, manual command buttons, firmware-update entity.
- **Native firmware updates** — HA shows "OpenLitter X.Y.Z available" and installs via the device's web update endpoint. No PC, no PlatformIO.
- **Lovelace card** with rotating-globe animation, controls, and recent-cycles list.

---

## Installation

### Via HACS (recommended)

1. In HA: **HACS → Integrations → ⋮ → Custom repositories**
2. URL: `https://github.com/davdlic/openlitter-ha`, Category: **Integration**
3. Install **OpenLitter**
4. Restart Home Assistant
5. **Settings → Devices & Services → Add Integration → OpenLitter** (or just accept the auto-discovery toast)

For the Lovelace card, see [Lovelace card](#lovelace-card) below.

### Manual

Copy `custom_components/openlitter/` into your HA config's `custom_components/` directory, restart HA, and add the integration.

---

## Configuration

The integration's config flow asks for:

| Field | Required | Notes |
|---|---|---|
| Host | yes | `openlitter.local` or `192.168.x.x`. Auto-filled when discovered via mDNS. |
| OTA password | no | Only needed to use the firmware-update entity. Default in OpenLitter is `openlitter`. |
| Use MQTT (if available) | no | If you already have HA's MQTT integration configured AND the device is publishing to a broker, ticking this enables MQTT subscription on top of REST/WS. |

---

## Entities

| Entity | Type | Notes |
|---|---|---|
| `sensor.openlitter_state` | sensor | Friendly label (`Ready`, `Cleaning`, `Dumping`…). Attributes: raw state, full history array. |
| `sensor.openlitter_weight` | sensor (kg) | Only present if weight sensor enabled on the device. |
| `sensor.openlitter_cycle_count` | sensor | Total cycles since last reset. |
| `sensor.openlitter_uptime` | sensor (s) | Device uptime. |
| `binary_sensor.openlitter_cat_present` | occupancy | True while a cat is detected. |
| `binary_sensor.openlitter_home_position` | sensor | Live state of the HOME magnet sensor. |
| `binary_sensor.openlitter_dump_position` | sensor | Live state of the DUMP magnet sensor. |
| `binary_sensor.openlitter_error` | problem | True while the device is in ERROR. |
| `button.openlitter_cycle` / `empty` / `reset` / `home` / `pause` / `resume` / `tare` | buttons | Same actions as the Web UI / MQTT commands. `home` parks the globe (skips DUMP, still runs the sand shake on arrival). |
| `update.openlitter_firmware` | update | Polls GitHub releases of the firmware repo; install button uses `/api/update`. |

---

## Lovelace card

The card is **bundled with the integration** — no manual Lovelace Resource entry needed. When you complete the config flow, the integration registers `/openlitter-frontend/openlitter-card.js` with HA's frontend, and any dashboard can immediately use:

```yaml
type: custom:openlitter-card
entity: sensor.openlitter_state
```

The card reads weight, buttons, sensor pills, and history automatically from the device's other entities (it picks them up by the shared name prefix).

If HA shows *Custom element doesn't exist: openlitter-card* right after install, hard-refresh the browser (Ctrl+F5) — the JS module is cached aggressively. The integration adds a `?v=` query string on updates so subsequent versions auto-refetch.

---

## Roadmap

- [x] Repository skeleton + HACS metadata
- [x] REST + WebSocket API client
- [x] DataUpdateCoordinator
- [x] Config flow (zeroconf + manual)
- [x] Sensor / binary_sensor / button platforms
- [x] Update entity (GitHub releases → `/api/update`)
- [x] Lovelace card bundled with the integration (no manual Resource entry)
- [x] hassfest + HACS validation CI
- [ ] MQTT bridge (auto-detect HA's MQTT integration) — currently REST/WS only
- [ ] Brand assets (icon/logo on HACS) — PR to home-assistant/brands pending
- [ ] Config-flow reauth on connection failure
- [ ] First HACS release tag

---

## License

GPL v3 — see [LICENSE](LICENSE). Same license as OpenLitter itself.
