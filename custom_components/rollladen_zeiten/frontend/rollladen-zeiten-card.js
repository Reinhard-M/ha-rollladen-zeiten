/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant. */
/*
 * Rollladen Zeiten - Lovelace card
 * Loaded automatically by the integration (no manual resource entry needed).
 *
 * Card type:  custom:rollladen-zeiten-card
 *
 * Example:
 *   type: custom:rollladen-zeiten-card
 *   title: Rollladen
 *   devices:            # device IDs, order = row order
 *     - 0123456789abcdef0123456789abcdef
 *   columns: [morning, evening, is_day, free_day]
 *   show_seconds: true
 *   editable: true
 *   device_type: shutter   # shutter | awning: only changes the labels of the time limits
 */

const CARD_TYPE = "rollladen-zeiten-card";
const EDITOR_TYPE = "rollladen-zeiten-card-editor";
const PLATFORM = "rollladen_zeiten";
// Documentation shown by the "?" icon (German README for German UI, English README otherwise)
const DOCS = {
  de: "https://github.com/Reinhard-M/ha-rollladen-zeiten#readme",
  en: "https://github.com/Reinhard-M/ha-rollladen-zeiten/blob/main/README.en.md",
};

// Order = column order in the table
const COLUMNS = [
  { key: "morning", entity: "morning", kind: "sensor_time" },
  { key: "evening", entity: "evening", kind: "sensor_time" },
  { key: "is_day", entity: "is_day", kind: "bool" },
  { key: "free_day", entity: "free_day", kind: "bool" },
  { key: "morning_preset", entity: "morning_preset", kind: "select" },
  { key: "morning_offset", entity: "morning_offset", kind: "number" },
  { key: "earliest_morning", entity: "earliest_morning", kind: "time" },
  { key: "earliest_morning_free", entity: "earliest_morning_free", kind: "time" },
  { key: "evening_preset", entity: "evening_preset", kind: "select" },
  { key: "evening_offset", entity: "evening_offset", kind: "number" },
  { key: "latest_evening", entity: "latest_evening", kind: "time" },
];
const DEFAULT_COLUMNS = ["morning", "evening", "is_day", "free_day"];

const TEXTS = {
  de: {
    device: "Name",
    cols: {
      morning: "Fahrzeit morgens",
      evening: "Fahrzeit abends",
      is_day: "Tag",
      free_day: "Freier Tag",
      morning_preset: "Sonnenaufgang",
      morning_offset: "Sonnenaufgang-Offset",
      earliest_morning: "Zeit fr\u00fchestens hoch",
      earliest_morning_free: "Zeit fr\u00fchestens hoch WE/FT",
      evening_preset: "Sonnenuntergang",
      evening_offset: "Sonnenuntergang-Offset",
      latest_evening: "Zeit sp\u00e4testens runter",
    },
    awning: {
      earliest_morning: "Zeit fr\u00fchestens Automatik",
      earliest_morning_free: "Zeit fr\u00fchestens Automatik WE/FT",
      latest_evening: "Zeit sp\u00e4testens einfahren",
    },
    colHints: { earliest_morning_free: "WE = Wochenende, FT = Freie Tage" },
    yes: "Ja",
    no: "Nein",
    limited: "Zeitgrenze greift \u2013 Sonnenstand",
    empty: "Noch keine Ger\u00e4te ausgew\u00e4hlt. W\u00e4hle im Karteneditor die Rollladen-Zeiten-Ger\u00e4te aus.",
    notFound: "nicht gefunden",
    help: "Hilfe / Dokumentation",
    editor: {
      show_help: "Hilfe-Symbol (?) anzeigen",
      title: "Titel",
      devices: "Ger\u00e4te (Reihenfolge = Zeilenreihenfolge)",
      columns: "Spalten",
      device_type: "Art der Ger\u00e4te (Beschriftung der Zeitgrenzen)",
      shutter: "Rollos / Jalousien",
      awning: "Markisen",
      show_seconds: "Sekunden anzeigen",
      editable: "Einstellungen in der Karte \u00e4nderbar",
    },
  },
  en: {
    device: "Name",
    cols: {
      morning: "Morning time",
      evening: "Evening time",
      is_day: "Day",
      free_day: "Day off",
      morning_preset: "Sunrise",
      morning_offset: "Sunrise offset",
      earliest_morning: "Earliest time up",
      earliest_morning_free: "Earliest time up WE/DO",
      evening_preset: "Sunset",
      evening_offset: "Sunset offset",
      latest_evening: "Latest time down",
    },
    awning: {
      earliest_morning: "Earliest time automation",
      earliest_morning_free: "Earliest time automation WE/DO",
      latest_evening: "Latest time retract",
    },
    colHints: { earliest_morning_free: "WE = weekend, DO = days off" },
    yes: "Yes",
    no: "No",
    limited: "Time limit applies \u2013 sun position",
    empty: "No devices selected yet. Pick the Rollladen Zeiten devices in the card editor.",
    notFound: "not found",
    help: "Help / documentation",
    editor: {
      show_help: "Show help icon (?)",
      title: "Title",
      devices: "Devices (order = row order)",
      columns: "Columns",
      device_type: "Kind of devices (labels of the time limits)",
      shutter: "Shutters / blinds",
      awning: "Awnings",
      show_seconds: "Show seconds",
      editable: "Allow changing settings in the card",
    },
  },
};

const langOf = (hass) =>
  String(hass?.locale?.language || hass?.language || "en").toLowerCase().startsWith("de")
    ? "de"
    : "en";

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

const isUnusable = (st) => !st || st.state === "unavailable" || st.state === "unknown";

class RollladenZeitenCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._sig = "";
    this._pending = false;
    this._mapSource = undefined;
    this._map = {};

    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("change", (ev) => this._onChange(ev));
    this.shadowRoot.addEventListener("focusout", () => {
      setTimeout(() => {
        if (this._pending && !this._hasFocus()) {
          this._pending = false;
          this._maybeRender();
        }
      }, 0);
    });
  }

  // ---------- Home Assistant interface ----------
  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    const ids = new Set();
    try {
      for (const e of Object.values(hass?.entities || {})) {
        if (e.platform === PLATFORM && e.device_id) ids.add(e.device_id);
      }
    } catch (_) { /* the stub stays empty */ }
    return { type: `custom:${CARD_TYPE}`, devices: [...ids] };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    const columns = Array.isArray(config.columns) && config.columns.length ? config.columns : DEFAULT_COLUMNS;
    this._config = {
      title: "",
      show_seconds: true,
      editable: true,
      show_help: true,
      device_type: "shutter",
      ...config,
      devices: Array.isArray(config.devices) ? config.devices : [],
      columns,
    };
    this._sig = "";
    this._maybeRender();
  }

  set hass(hass) {
    this._hass = hass;
    this._maybeRender();
  }

  getCardSize() {
    return 1 + Math.max(1, this._config?.devices?.length || 1);
  }

  // ---------- Helpers ----------
  _hasFocus() {
    const a = this.shadowRoot.activeElement;
    return !!a && (a.tagName === "INPUT" || a.tagName === "SELECT");
  }

  _columns() {
    return COLUMNS.filter((c) => this._config.columns.includes(c.key));
  }

  _entityMap() {
    const ents = this._hass?.entities;
    if (this._map && this._mapSource === ents) return this._map;
    const map = {};
    for (const e of Object.values(ents || {})) {
      if (e.platform !== PLATFORM || !e.device_id || !e.translation_key) continue;
      (map[e.device_id] ||= {})[e.translation_key.replace(/_awning$/, "")] = e.entity_id;
    }
    this._mapSource = ents;
    this._map = map;
    return map;
  }

  _deviceName(id) {
    const d = this._hass?.devices?.[id];
    return d ? d.name_by_user || d.name || id : null;
  }

  _signature() {
    const h = this._hass;
    const c = this._config;
    const map = this._entityMap();
    const parts = [langOf(h), c.show_seconds, c.editable, c.device_type, c.show_help, c.title, c.columns.join(",")];
    for (const id of c.devices) {
      parts.push(this._deviceName(id) ?? "?");
      for (const col of this._columns()) {
        const eid = map[id]?.[col.entity];
        const st = eid ? h.states[eid] : null;
        parts.push(
          st ? `${st.state}|${st.attributes?.overridden ?? ""}|${st.attributes?.sun_time ?? ""}` : "-"
        );
      }
    }
    return parts.join("\u00a6");
  }

  _maybeRender() {
    if (!this._config || !this._hass) return;
    const sig = this._signature();
    if (sig === this._sig) return;
    if (this._hasFocus()) {
      this._pending = true; // do not re-render in the middle of an input
      return;
    }
    this._sig = sig;
    this._render();
  }

  // ---------- Rendering ----------
  _cell(col, eid, t) {
    const h = this._hass;
    const cfg = this._config;
    const st = eid ? h.states[eid] : null;
    if (!st) return `<td class="na">\u2013</td>`;
    const editable = cfg.editable && !isUnusable(st);

    switch (col.kind) {
      case "sensor_time": {
        let txt = st.state;
        if (!/^\d\d:\d\d(:\d\d)?$/.test(txt)) txt = "\u2013";
        else if (!cfg.show_seconds) txt = txt.slice(0, 5);
        const limited = st.attributes?.overridden === true;
        const sun = String(st.attributes?.sun_time || "");
        const sunTxt = sun.length >= 19 ? sun.slice(11, 19) : "";
        const title = limited ? `${t.limited}${sunTxt ? `: ${sunTxt}` : ""}` : "";
        return `<td class="time${limited ? " limited" : ""}"${title ? ` title="${esc(title)}"` : ""}>${esc(txt)}</td>`;
      }
      case "bool": {
        if (isUnusable(st)) return `<td class="na">\u2013</td>`;
        const on = st.state === "on";
        const label = h.formatEntityState ? h.formatEntityState(st) : on ? t.yes : t.no;
        return `<td><span class="chip ${on ? "on" : "off"}">${esc(label)}</span></td>`;
      }
      case "select": {
        const label = (o) => (h.formatEntityState ? h.formatEntityState(st, o) : o);
        if (!editable) return `<td>${esc(isUnusable(st) ? "\u2013" : label(st.state))}</td>`;
        const opts = st.attributes?.options || [];
        const options = opts
          .map((o) => `<option value="${esc(o)}"${o === st.state ? " selected" : ""}>${esc(label(o))}</option>`)
          .join("");
        return `<td><select data-entity="${esc(eid)}" data-kind="select">${options}</select></td>`;
      }
      case "number": {
        const a = st.attributes || {};
        const unit = a.unit_of_measurement ? ` ${esc(a.unit_of_measurement)}` : "";
        if (!editable) return `<td>${isUnusable(st) ? "\u2013" : esc(st.state) + unit}</td>`;
        return (
          `<td><input type="number" data-entity="${esc(eid)}" data-kind="number" value="${esc(st.state)}"` +
          ` min="${esc(a.min ?? -30)}" max="${esc(a.max ?? 30)}" step="${esc(a.step ?? 0.1)}">${unit}</td>`
        );
      }
      case "time": {
        const v = /^\d\d:\d\d/.test(st.state) ? st.state.slice(0, 5) : "";
        if (!editable) return `<td class="time">${esc(v || "\u2013")}</td>`;
        return `<td><input type="time" step="60" data-entity="${esc(eid)}" data-kind="time" value="${esc(v)}"></td>`;
      }
      default:
        return `<td>${esc(st.state)}</td>`;
    }
  }

  _render() {
    const h = this._hass;
    const cfg = this._config;
    const t = TEXTS[langOf(h)];
    const map = this._entityMap();
    const cols = this._columns();

    const head = cols
      .map((c) => {
        const hint = t.colHints[c.key];
        const label = (cfg.device_type === "awning" && t.awning[c.key]) || t.cols[c.key];
        return `<th${hint ? ` title="${esc(hint)}"` : ""}>${esc(label)}</th>`;
      })
      .join("");

    const rows = cfg.devices
      .map((id) => {
        const name = this._deviceName(id);
        const nameCell = name
          ? `<a class="dev" href="/config/devices/device/${esc(id)}" data-device="${esc(id)}">${esc(name)}</a>`
          : `<span class="missing">${esc(id)} (${esc(t.notFound)})</span>`;
        const cells = cols.map((c) => this._cell(c, map[id]?.[c.entity], t)).join("");
        return `<tr><th scope="row">${nameCell}</th>${cells}</tr>`;
      })
      .join("");

    const body = cfg.devices.length
      ? `<div class="wrap"><table><thead><tr><th>${esc(t.device)}</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>`
      : `<div class="empty">${esc(t.empty)}</div>`;

    // "?" help icon, right-aligned above the table, linking to the README
    const help = cfg.show_help !== false
      ? `<div class="helprow"><a class="help" href="${DOCS[langOf(h)]}" target="_blank" rel="noopener noreferrer" title="${esc(t.help)}" aria-label="${esc(t.help)}">?</a></div>`
      : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .wrap { overflow-x: auto; padding: 0 4px 8px; }
        table { width: 100%; border-collapse: collapse; white-space: nowrap; }
        tr:nth-child(odd) { background: color-mix(in srgb, var(--primary-text-color, #000) 4%, transparent); }
        th, td { padding: 4px 8px; vertical-align: middle; text-align: center; }
        tbody th { text-align: left; font-weight: 500; }
        td, thead th + th { border-left: 1px solid var(--divider-color, #ddd); }
        thead th { font-size: 0.78em; font-weight: 400; color: var(--secondary-text-color);
          padding: 2px 8px; border-bottom: 1px solid var(--divider-color, #ddd); }
        thead th:first-child { text-align: left; }
        a.dev { color: var(--primary-color); text-decoration: none; cursor: pointer; }
        a.dev:hover { text-decoration: underline; }
        .missing { color: var(--error-color, #db4437); font-weight: normal; }
        td.time { font-variant-numeric: tabular-nums; }
        td.limited { text-decoration: underline dotted; text-underline-offset: 3px; cursor: help; }
        td.na { color: var(--secondary-text-color); }
        .chip { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.85em; }
        .chip.on { background: rgba(67, 160, 71, 0.18); color: var(--success-color, #43a047); }
        .chip.off { background: var(--secondary-background-color, #f2f2f2); color: var(--secondary-text-color); }
        select, input {
          font: inherit; color: var(--primary-text-color);
          background: var(--card-background-color, #fff);
          border: 1px solid var(--divider-color, #ccc); border-radius: 6px; padding: 4px 6px;
        }
        input[type="number"] { width: 5em; }
        .helprow { display: flex; justify-content: flex-end; padding: 8px 12px 0; }
        a.help { width: 20px; height: 20px; box-sizing: border-box; border-radius: 50%;
          border: 1.5px solid var(--secondary-text-color); color: var(--secondary-text-color);
          display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600;
          text-decoration: none; line-height: 1; }
        a.help:hover { color: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4); }
        .empty { padding: 16px; color: var(--secondary-text-color); }
      </style>
      <ha-card${cfg.title ? ` header="${esc(cfg.title)}"` : ""}>${help}${body}</ha-card>`;
  }

  // ---------- Interaction ----------
  _onClick(ev) {
    const a = ev.target?.closest?.("a[data-device]");
    if (!a) return;
    if (ev.button !== 0 || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return; // browser default
    ev.preventDefault();
    history.pushState(null, "", a.getAttribute("href"));
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  }

  _onChange(ev) {
    const el = ev.target;
    const entity_id = el?.dataset?.entity;
    if (!entity_id || !this._hass) return;
    let call = null;
    switch (el.dataset.kind) {
      case "select":
        call = ["select", "select_option", { entity_id, option: el.value }];
        break;
      case "number": {
        const value = parseFloat(el.value);
        if (Number.isNaN(value)) return;
        call = ["number", "set_value", { entity_id, value }];
        break;
      }
      case "time":
        if (!el.value) return;
        call = ["time", "set_value", { entity_id, time: el.value.length === 5 ? `${el.value}:00` : el.value }];
        break;
      default:
        return;
    }
    Promise.resolve(this._hass.callService(...call)).finally(() => {
      this._sig = ""; // reset/refresh the display to the real state
      this._maybeRender();
    });
  }
}

// ---------- Card editor ----------
class RollladenZeitenCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  _update() {
    if (!this._config || !this._hass) return;
    const t = TEXTS[langOf(this._hass)];
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        const config = { ...this._config, ...ev.detail.value, type: `custom:${CARD_TYPE}` };
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = {
      title: "",
      devices: [],
      columns: DEFAULT_COLUMNS,
      device_type: "shutter",
      show_seconds: true,
      editable: true,
      show_help: true,
      ...this._config,
    };
    this._form.schema = [
      { name: "title", selector: { text: {} } },
      { name: "devices", selector: { device: { integration: PLATFORM, multiple: true } } },
      {
        name: "columns",
        selector: {
          select: {
            multiple: true,
            mode: "list",
            options: COLUMNS.map((c) => ({ value: c.key, label: (this._config?.device_type === "awning" && t.awning[c.key]) || t.cols[c.key] })),
          },
        },
      },
      {
        name: "device_type",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "shutter", label: t.editor.shutter },
              { value: "awning", label: t.editor.awning },
            ],
          },
        },
      },
      { name: "show_seconds", selector: { boolean: {} } },
      { name: "editable", selector: { boolean: {} } },
      { name: "show_help", selector: { boolean: {} } },
    ];
    this._form.computeLabel = (schema) => t.editor[schema.name] || schema.name;
  }
}

if (!customElements.get(CARD_TYPE)) customElements.define(CARD_TYPE, RollladenZeitenCard);
if (!customElements.get(EDITOR_TYPE)) customElements.define(EDITOR_TYPE, RollladenZeitenCardEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "Rollladen Zeiten",
    description: "Tabelle der Rollladen-Zeiten-Ger\u00e4te: Fahrzeiten, Tag/Nacht, Freier Tag und optional die Einstellungen.",
    preview: false,
  });
}
