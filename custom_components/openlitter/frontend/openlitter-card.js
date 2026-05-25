/*
 * openlitter-card.js — Lovelace card for the OpenLitter integration
 * Copyright (C) 2024 David Lopes (https://github.com/davdlic)
 * Licensed under the GNU General Public License v3.0 — see LICENSE
 *
 * Standalone ES module. Reads from the state sensor entity created by
 * the OpenLitter HA integration (e.g. sensor.openlitter_state). All
 * other entities (buttons, weight, sensor pills) are pulled
 * automatically from the same device by name prefix.
 */

const MOTION_STATES = new Set([
  'CYCLING_CCW', 'CYCLING_DUMP_PAUSE', 'CYCLING_CW',
  'CYCLING_LEVEL_OVERSHOOT', 'CYCLING_LEVEL_RETURN',
  'CYCLING_LEVEL_BACK_OVERSHOOT', 'CYCLING_LEVEL_BACK_RETURN',
  'EMPTYING', 'EMPTYING_DUMP_PAUSE', 'RESETTING',
]);

const LABELS = {
  IDLE: 'Ready', CAT_INSIDE: 'Cat inside', WAITING: 'Waiting',
  CYCLING_CCW: 'Cleaning', CYCLING_DUMP_PAUSE: 'Dumping',
  CYCLING_CW: 'Returning',
  CYCLING_LEVEL_OVERSHOOT: 'Leveling', CYCLING_LEVEL_RETURN: 'Leveling',
  CYCLING_LEVEL_BACK_OVERSHOOT: 'Leveling', CYCLING_LEVEL_BACK_RETURN: 'Leveling',
  EMPTYING: 'Emptying', EMPTYING_DUMP_PAUSE: 'Dumping',
  RESETTING: 'Returning', PAUSED: 'Paused', ERROR: 'Error',
};

function fmtRelative(secEpoch) {
  if (!secEpoch) return '—';
  const ms = secEpoch * 1000;
  const d = new Date(ms);
  if (isNaN(d.getTime()) || d.getFullYear() < 2000) return '—';
  const diffSec = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (diffSec < 60)      return 'just now';
  if (diffSec < 3600)    return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400)   return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 604800)  return `${Math.floor(diffSec / 86400)}d ago`;
  return d.toLocaleDateString();
}

class OpenLitterCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error('openlitter-card: `entity` is required (e.g. sensor.openlitter_state)');
    }
    this._config = config;
    if (!this._root) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._root) this._update();
  }

  getCardSize() { return 7; }

  static getStubConfig() {
    return { entity: 'sensor.openlitter_state' };
  }

  _render() {
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 1rem; display: flex; flex-direction: column; gap: 0.85rem; }

        /* Hero: globe + state badge */
        .hero { display: flex; align-items: center; gap: 1rem; }
        .globe { width: 84px; height: 84px; border-radius: 50%;
                 border: 4px dashed var(--primary-color, #7ac9f5);
                 display: flex; align-items: center; justify-content: center;
                 transition: border-color 0.3s; flex-shrink: 0; }
        .globe-inner { width: 60%; height: 60%; border-radius: 50%;
                       border: 4px solid var(--accent-color, #4eea7e);
                       transition: border-color 0.3s; }
        .globe.spinning { animation: ol-spin 4s linear infinite; }
        .globe.error    { border-color: var(--error-color, #f44336); }
        .globe.error .globe-inner { border-color: var(--error-color, #f44336); }
        @keyframes ol-spin { to { transform: rotate(360deg); } }

        .info { display: flex; flex-direction: column; min-width: 0; }
        .badge { font-weight: 700; letter-spacing: 0.05em;
                 padding: 0.3rem 0.75rem; border-radius: 999px;
                 background: var(--primary-color, #7ac9f5); color: #0a0b18;
                 display: inline-block; width: max-content;
                 font-size: 0.9rem; }
        .badge.error { background: var(--error-color, #f44336); color: #fff; }
        .detail { color: var(--secondary-text-color); font-size: 0.85rem;
                  margin-top: 0.3rem; }

        /* Stats grid (cycles + last + optional weight) */
        .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }
        .stats.has-weight { grid-template-columns: 1fr 1fr 1fr; }
        .pill { background: var(--secondary-background-color);
                padding: 0.5rem 0.7rem; border-radius: 8px;
                font-size: 0.82rem; display: flex; flex-direction: column;
                min-width: 0; }
        .pill .label { color: var(--secondary-text-color);
                       text-transform: uppercase; letter-spacing: 0.04em;
                       font-size: 0.7rem; }
        .pill .v { font-weight: 600; font-size: 0.95rem; margin-top: 0.15rem;
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .pill[hidden] { display: none; }

        /* Sensor pills (HOME / DUMP / CAT) */
        .sensors { display: flex; gap: 0.4rem; flex-wrap: wrap; }
        .sensor-pill { display: inline-flex; align-items: center; gap: 0.4rem;
                       padding: 0.35rem 0.65rem;
                       background: var(--secondary-background-color);
                       border: 1px solid var(--divider-color);
                       border-radius: 999px;
                       font-size: 0.78rem; letter-spacing: 0.04em;
                       color: var(--secondary-text-color);
                       transition: background 0.15s, color 0.15s, border-color 0.15s; }
        .sensor-pill .sdot { width: 0.55rem; height: 0.55rem;
                             border-radius: 50%;
                             background: var(--divider-color);
                             transition: background 0.15s, box-shadow 0.15s; }
        .sensor-pill.active {
          color: var(--primary-text-color);
          border-color: rgba(78, 234, 126, 0.6);
          background: rgba(78, 234, 126, 0.12);
        }
        .sensor-pill.active .sdot {
          background: #4eea7e;
          box-shadow: 0 0 6px rgba(78, 234, 126, 0.7);
        }

        /* Controls — 3 columns, wraps to 2 rows for 6 buttons */
        .buttons { display: grid; grid-template-columns: repeat(3, 1fr);
                   gap: 0.5rem; }
        button { padding: 0.55rem 0.5rem; border-radius: 8px;
                 border: 1px solid var(--divider-color);
                 background: var(--card-background-color);
                 color: var(--primary-text-color); cursor: pointer;
                 font-size: 0.86rem; font-weight: 500; }
        button:hover { background: var(--secondary-background-color); }
        button.primary { background: var(--primary-color, #7ac9f5);
                         color: #0a0b18; border-color: transparent;
                         font-weight: 600; }
        button:disabled { opacity: 0.4; cursor: not-allowed; }

        @media (max-width: 380px) {
          .buttons { grid-template-columns: repeat(2, 1fr); }
        }
      </style>
      <ha-card>
        <div class="hero">
          <div class="globe" id="globe"><div class="globe-inner"></div></div>
          <div class="info">
            <span class="badge" id="badge">—</span>
            <span class="detail" id="detail"></span>
          </div>
        </div>

        <div class="stats" id="stats">
          <div class="pill">
            <span class="label">Cycles</span>
            <span class="v" id="cycles">—</span>
          </div>
          <div class="pill">
            <span class="label">Last cycle</span>
            <span class="v" id="last">—</span>
          </div>
          <div class="pill" id="weight-pill" hidden>
            <span class="label">Weight</span>
            <span class="v" id="weight">—</span>
          </div>
        </div>

        <div class="sensors">
          <div class="sensor-pill" id="sp-home"><span class="sdot"></span>HOME</div>
          <div class="sensor-pill" id="sp-dump"><span class="sdot"></span>DUMP</div>
          <div class="sensor-pill" id="sp-cat"><span class="sdot"></span>CAT</div>
        </div>

        <div class="buttons">
          <button class="primary" data-cmd="cycle">Cycle</button>
          <button data-cmd="empty">Empty</button>
          <button data-cmd="reset">Reset</button>
          <button data-cmd="home">Home</button>
          <button data-cmd="pause">Pause</button>
          <button data-cmd="resume">Resume</button>
        </div>
      </ha-card>
    `;
    this._root = this.shadowRoot;
    this._root.querySelectorAll('[data-cmd]').forEach(btn => {
      btn.addEventListener('click', () => this._press(btn.dataset.cmd));
    });
  }

  _update() {
    const hass = this._hass;
    if (!hass) return;
    const stateEntity = hass.states[this._config.entity];
    if (!stateEntity) return;

    const raw = stateEntity.attributes.raw_state || stateEntity.state;
    const badge = this._root.getElementById('badge');
    const detail = this._root.getElementById('detail');
    const globe = this._root.getElementById('globe');

    badge.textContent = (LABELS[raw] || raw || '').toUpperCase();
    badge.classList.toggle('error', raw === 'ERROR');
    detail.textContent = stateEntity.state;
    globe.classList.toggle('spinning', MOTION_STATES.has(raw));
    globe.classList.toggle('error', raw === 'ERROR');

    // Resolve sibling entities from the state entity's name prefix.
    // Be fuzzy: HA's entity_id slugifier turns "Home position sensor"
    // into `home_position_sensor`, so a strict suffix match would miss
    // entities whose friendly name added extra words. Match on
    // *contains the keyword* among entities sharing the base prefix.
    const base = this._config.entity.split('.')[1].replace('_state', '');
    const findFirst = (domain, keyword) => {
      const prefix = `${domain}.${base}_`;
      for (const eid in hass.states) {
        if (eid.startsWith(prefix) && eid.indexOf(keyword) !== -1) {
          return hass.states[eid];
        }
      }
      // Fallback to the strict suffix form too, just in case HA gave
      // the entity an entirely different prefix (renamed by the user).
      return hass.states[`${domain}.${base}_${keyword}`];
    };
    const pick    = (keyword) => findFirst('sensor', keyword);
    const pickBin = (keyword) => findFirst('binary_sensor', keyword);

    // Cycles + last
    const cycles = pick('cycle_count');
    this._root.getElementById('cycles').textContent =
      cycles && cycles.state !== 'unavailable' && cycles.state !== 'unknown'
        ? cycles.state : '—';
    this._root.getElementById('last').textContent =
      fmtRelative(stateEntity.attributes.last_cycle);

    // Weight — hide the pill entirely if the firmware reports the sensor disabled.
    const weight = pick('weight');
    const weightPill = this._root.getElementById('weight-pill');
    const weightAvailable = weight &&
      weight.state !== 'unavailable' && weight.state !== 'unknown';
    if (weightAvailable) {
      weightPill.hidden = false;
      this._root.getElementById('weight').textContent =
        `${(+weight.state).toFixed(2)} kg`;
      this._root.getElementById('stats').classList.add('has-weight');
    } else {
      weightPill.hidden = true;
      this._root.getElementById('stats').classList.remove('has-weight');
    }

    // Sensor pills
    const setSensor = (id, ent) => {
      const on = ent && ent.state === 'on';
      this._root.getElementById(id).classList.toggle('active', !!on);
    };
    setSensor('sp-home', pickBin('home_position'));
    setSensor('sp-dump', pickBin('dump_position'));
    setSensor('sp-cat',  pickBin('cat_present'));

    // Disable buttons that the device wouldn't accept right now (best-effort UX).
    const idle = raw === 'IDLE';
    const motion = MOTION_STATES.has(raw);
    const paused = raw === 'PAUSED';
    const error = raw === 'ERROR';
    this._setBtn('cycle',  idle);
    this._setBtn('empty',  idle);
    this._setBtn('reset',  motion || paused || error);
    this._setBtn('home',   motion || paused || error);
    this._setBtn('pause',  motion);
    this._setBtn('resume', paused);
  }

  _setBtn(cmd, enabled) {
    const btn = this._root.querySelector(`button[data-cmd="${cmd}"]`);
    if (btn) btn.disabled = !enabled;
  }

  _press(cmd) {
    const hass = this._hass;
    if (!hass) return;
    const base = this._config.entity.split('.')[1].replace('_state', '');
    // Same fuzzy lookup as the sensors above — find the first
    // button.{base}_* that contains the command keyword. Lets the
    // existing button.openlitter_tare_weight entity_id work even after
    // we renamed the friendly name to just "Tare".
    const prefix = `button.${base}_`;
    let target = null;
    for (const eid in hass.states) {
      if (eid.startsWith(prefix) && eid.indexOf(cmd) !== -1) {
        target = eid;
        break;
      }
    }
    if (!target) target = `${prefix}${cmd}`;
    if (!hass.states[target]) return;
    hass.callService('button', 'press', { entity_id: target });
  }
}

if (!customElements.get('openlitter-card')) {
  customElements.define('openlitter-card', OpenLitterCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'openlitter-card',
  name: 'OpenLitter Card',
  description: 'Status, controls, sensor pills and recent activity for an OpenLitter device',
});
