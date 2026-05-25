<!--
OpenLitter-HA - Home Assistant integration + Lovelace card for OpenLitter
Copyright (C) 2024 David Lopes (https://github.com/davdlic)
Licensed under the GNU General Public License v3.0 - see LICENSE
-->

# OpenLitter — Home Assistant integration

[![Validate](https://github.com/davdlic/OpenLitter-HA/actions/workflows/validate.yml/badge.svg)](https://github.com/davdlic/OpenLitter-HA/actions/workflows/validate.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/HA-2024.4%2B-blue.svg)](https://www.home-assistant.io/)

Custom integration and Lovelace card for [OpenLitter](https://github.com/davdlic/OpenLitter), the open source ESP32 firmware that replaces the original board of a Litter Robot 1 / 2 / 3.

> ⚠️ **Pre-1.0.** Entity ids, attributes and the Lovelace card's structure may still change between minor versions. Tracks firmware releases on [davdlic/OpenLitter](https://github.com/davdlic/OpenLitter); the latest tested combination is documented in [Compatibility](#compatibility).

---

## What you get

- **Local push, no broker needed** — talks REST + WebSocket to the device directly. Status updates land in HA within ~500 ms. If you also tick **Use MQTT** in the config flow, the integration subscribes to the firmware's MQTT topics on top, so HA gets updates over whichever transport is freshest.
- **Auto-discovery via mDNS** — HA finds `openlitter.local` on your LAN without you typing an IP. Just accept the discovery toast.
- **Rich entities** — state with a friendly label and the full history array as an attribute, weight, cycle count, raw HOME / DUMP / CAT sensor states, error binary sensor, six command buttons, and an Update entity.
- **One-click firmware updates from HA** — the `update.openlitter_firmware` entity polls the firmware repo's GitHub releases, downloads both `firmware.bin` and `littlefs.bin`, and flashes them in sequence via the device's web update endpoint. No PC, no PlatformIO, no losing the Web UI.
- **Bundled Lovelace card** — `custom:openlitter-card` is auto-registered when the integration loads; no manual Resource entry. Rotating globe SVG, state badge, three live sensor pills, recent-cycle stats, and the six command buttons in one card.

---

## Compatibility

| OpenLitter-HA | Firmware  | Home Assistant Core | Notes |
|---------------|-----------|---------------------|-------|
| 0.2.x         | ≥ v0.4.1  | ≥ 2024.4            | MQTT bridge, brand assets bundled (HA 2026.3+ proxies them) |
| 0.1.x         | ≥ v0.4.0  | ≥ 2024.4            | REST + WS only, brand placeholder |

Older firmware (v0.3.x or earlier) may work but is untested. The `update.openlitter_firmware` install button only ships full updates from v0.4.0 onwards (separate `/api/update?type=fs` endpoint).

---

## Installation

### Via HACS (recommended)

1. In HA: **HACS → ⋮ → Custom repositories**
2. Repository URL: `https://github.com/davdlic/OpenLitter-HA`, Category: **Integration**
3. Click **Add**, find **OpenLitter** in the list and **Download** it.
4. Restart Home Assistant.
5. Accept the auto-discovery toast, or go to **Settings → Devices & Services → Add Integration → OpenLitter** and enter the host.

The Lovelace card is included — see [Lovelace card](#lovelace-card) below for usage.

### Manual

```bash
# From the HA config directory:
cd custom_components
git clone https://github.com/davdlic/OpenLitter-HA.git openlitter-ha
ln -s openlitter-ha/custom_components/openlitter openlitter
```

Restart HA, then add the integration as above. (Or just copy `custom_components/openlitter/` from this repo into your `custom_components/` directory.)

---

## Configuration

The config flow asks for:

| Field        | Required | Notes |
|--------------|----------|-------|
| Host         | yes      | `openlitter.local` or `192.168.x.x`. Auto-filled when discovered via mDNS. |
| Port         | yes      | Defaults to 80; only change if you reconfigured the firmware. |
| OTA password | no       | Only used by the firmware-update entity to authenticate the install POST. Default in OpenLitter is `openlitter`. |
| Use MQTT     | no       | Tick if HA's MQTT integration is configured and the firmware is publishing to a broker. The integration then also subscribes to `{topic_base}/*` and the coordinator merges MQTT updates with the REST + WS feed (last-write-wins). Pure bonus path; everything still works with this off. |
| MQTT topic base | no    | Defaults to `openlitter`. Match whatever you set in the firmware Settings → MQTT page. |

Nothing else to set up. The integration polls `/api/status` every 5 s as a safety net, but the primary update path is the WebSocket `/ws` push from the device, which lands in HA within ~500 ms of any state change on the firmware side.

---

## Entities

| Entity                                                      | Type                | Notes |
|-------------------------------------------------------------|---------------------|-------|
| `sensor.openlitter_state`                                   | sensor              | Friendly label (`Ready`, `Cleaning`, `Dumping`, `Leveling`, …). Attributes: `raw_state` (the internal enum name), `last_cycle` (Unix ts), `reset_in_progress`, full `history` array. |
| `sensor.openlitter_weight`                                  | sensor (kg)         | Only published when the firmware reports the weight sensor enabled. |
| `sensor.openlitter_cycle_count`                             | sensor              | Total completed cleaning cycles since the last counter reset. |
| `sensor.openlitter_uptime`                                  | sensor (s)          | Device uptime in seconds. Disabled by default — enable in the entity registry if you want to chart it. |
| `binary_sensor.openlitter_cat_present`                      | occupancy           | True while the cat is being detected (any of the configured sensors). |
| `binary_sensor.openlitter_home_position`                    | sensor              | Live state of the HOME magnet sensor. Useful to verify wiring without USB serial. |
| `binary_sensor.openlitter_dump_position`                    | sensor              | Live state of the DUMP magnet sensor. |
| `binary_sensor.openlitter_error`                            | problem             | True while the device is in the ERROR state. |
| `button.openlitter_cycle` / `empty` / `reset` / `home` / `pause` / `resume` / `tare` | buttons | Mirror the Web UI / MQTT command list. `home` parks the globe (skips the DUMP phase, still runs the sand shake on arrival). `tare` only appears if the weight sensor is enabled. |
| `update.openlitter_firmware`                                | update              | Polls GitHub releases of [davdlic/OpenLitter](https://github.com/davdlic/OpenLitter); the Install button downloads and flashes both `firmware.bin` and `littlefs.bin` in sequence. |

---

## Lovelace card

The card is **bundled with the integration** — no manual Lovelace Resource entry needed. When the config flow finishes, the integration registers `/openlitter-frontend/openlitter-card.js` with HA's frontend, and any dashboard can immediately use:

```yaml
type: custom:openlitter-card
entity: sensor.openlitter_state
```

The card resolves weight, buttons, sensor pills and `last_cycle` from the device's other entities automatically by name prefix — no extra options needed.

What's on the card:

- **Rotating globe SVG** with state badge and a one-line description, mirroring the device's Web UI.
- **Stats row** — total cycles, last cycle (as a relative time like `5m ago`), weight (only shown when the sensor is enabled).
- **Sensor pills** — `HOME`, `DUMP`, `CAT` light green when active. Rotate the globe by hand and watch the pills update in real time; this is the fastest way to validate wiring.
- **Six command buttons** in a 3 × 2 grid (drops to 2 × 3 on mobile). Each button is disabled when the current device state wouldn't accept it.

**Troubleshooting**: if HA shows *Custom element doesn't exist: openlitter-card* right after install, hard-refresh the browser (`Ctrl + F5`). The JS module is cached aggressively. The integration appends a `?v=…` query on updates so subsequent versions auto-refetch.

---

## Roadmap

- [x] Repository skeleton + HACS metadata
- [x] REST + WebSocket API client (`api.py`)
- [x] DataUpdateCoordinator with WS push + 5 s REST poll fallback
- [x] Config flow: zeroconf discovery + manual entry
- [x] Sensor / binary_sensor / button / update platforms
- [x] Update entity flashes **both** `firmware.bin` and `littlefs.bin` from each release
- [x] Lovelace card bundled — no manual Resource registration step
- [x] hassfest + HACS validation CI
- [x] First HACS release tag
- [x] MQTT bridge — subscribes to firmware topics when HA's MQTT integration is configured
- [x] Brand assets bundled in `custom_components/openlitter/brand/` (HA 2026.3+ serves these via its proxy; no upstream PR needed)
- [ ] Config-flow reauth on connection failure
- [ ] Translations beyond English

---

## License

GPL v3 — see [LICENSE](LICENSE). Same license as the OpenLitter firmware.
