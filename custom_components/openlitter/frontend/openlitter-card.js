/*
 * openlitter-card.js — Lovelace card for the OpenLitter integration
 * Copyright (C) 2024 David Lopes (https://github.com/davdlic)
 * Licensed under the GNU General Public License v3.0 — see LICENSE
 *
 * Standalone ES module. Reads from a state sensor entity created by
 * the OpenLitter HA integration (e.g. sensor.openlitter_state). All
 * other entities (buttons, weight, sensors) are pulled automatically
 * from the same device.
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

  getCardSize() { return 6; }

  static getStubConfig() {
    return { entity: 'sensor.openlitter_state' };
  }

  _render() {
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
        .hero { display: flex; align-items: center; gap: 1rem; }
        .globe { width: 84px; height: 84px; border-radius: 50%;
                 border: 4px dashed var(--primary-color, #7ac9f5);
                 display: flex; align-items: center; justify-content: center;
                 transition: border-color 0.3s; }
        .globe-inner { width: 60%; height: 60%; border-radius: 50%;
                       border: 4px solid var(--accent-color, #4eea7e);
                       transition: border-color 0.3s; }
        .globe.spinning { animation: ol-spin 4s linear infinite; }
        .globe.error    { border-color: var(--error-color, #f44336); }
        .globe.error .globe-inner { border-color: var(--error-color, #f44336); }
        @keyframes ol-spin { to { transform: rotate(360deg); } }
        .info { display: flex; flex-direction: column; }
        .badge { font-weight: 700; letter-spacing: 0.04em;
                 padding: 0.25rem 0.6rem; border-radius: 999px;
                 background: var(--primary-color, #7ac9f5); color: #0a0b18;
                 display: inline-block; width: max-content; }
        .badge.error { background: var(--error-color, #f44336); color: #fff; }
        .detail { color: var(--secondary-text-color); font-size: 0.85rem; margin-top: 0.25rem; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }
        .pill { background: var(--secondary-background-color); padding: 0.4rem 0.7rem;
                border-radius: 8px; font-size: 0.85rem; display: flex;
                justify-content: space-between; align-items: center; }
        .pill .v { font-weight: 600; }
        .buttons { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }
        button { padding: 0.5rem; border-radius: 8px; border: 1px solid var(--divider-color);
                 background: var(--card-background-color); color: var(--primary-text-color);
                 cursor: pointer; font-size: 0.88rem; }
        button:hover { background: var(--secondary-background-color); }
        button.primary { background: var(--primary-color, #7ac9f5); color: #0a0b18; border-color: transparent; }
      </style>
      <ha-card>
        <div class="hero">
          <div class="globe" id="globe"><div class="globe-inner"></div></div>
          <div class="info">
            <span class="badge" id="badge">—</span>
            <span class="detail" id="detail"></span>
          </div>
        </div>
        <div class="grid">
          <div class="pill"><span>Cat</span><span class="v" id="cat">—</span></div>
          <div class="pill"><span>Weight</span><span class="v" id="weight">—</span></div>
          <div class="pill"><span>Cycles</span><span class="v" id="cycles">—</span></div>
          <div class="pill"><span>Last</span><span class="v" id="last">—</span></div>
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

    const base = this._config.entity.split('.')[1].replace('_state', '');
    const pick = (suffix) => hass.states[`sensor.${base}_${suffix}`];
    const pickBin = (suffix) => hass.states[`binary_sensor.${base}_${suffix}`];

    const cat = pickBin('cat_present');
    this._root.getElementById('cat').textContent = cat ? (cat.state === 'on' ? 'Yes' : 'No') : '—';
    const weight = pick('weight');
    this._root.getElementById('weight').textContent = weight && weight.state !== 'unavailable'
      ? `${(+weight.state).toFixed(2)} kg` : 'off';
    const cycles = pick('cycle_count');
    this._root.getElementById('cycles').textContent = cycles ? cycles.state : '—';
    const last = stateEntity.attributes.last_cycle;
    this._root.getElementById('last').textContent = last
      ? new Date(last * 1000).toLocaleString() : '—';
  }

  _press(cmd) {
    const base = this._config.entity.split('.')[1].replace('_state', '');
    const target = `button.${base}_${cmd}`;
    if (!this._hass.states[target]) return;
    this._hass.callService('button', 'press', { entity_id: target });
  }
}

if (!customElements.get('openlitter-card')) {
  customElements.define('openlitter-card', OpenLitterCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'openlitter-card',
  name: 'OpenLitter Card',
  description: 'Status, controls, and recent cycles for an OpenLitter device',
});
