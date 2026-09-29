/**
 * InfoHub sidebar config panel.
 *
 * Plain vanilla-JS custom element - deliberately no Lit/build step (no
 * Node bundler or browser was available to test one from where this was
 * written). Reuses Home Assistant's own globally-registered elements
 * (<ha-card>, <ha-entity-picker>) instead of building pickers from
 * scratch. Talks to the backend exclusively through the websocket
 * commands that homeassistant.helpers.collection.DictStorageCollectionWebsocket
 * auto-generates for the "infohub/panel" collection (see panels.py):
 * infohub/panel/list, /subscribe, /create, /update ({panel_id, ...}),
 * /delete ({panel_id}).
 *
 * The widget layout editor (grid canvas, drag/resize) mirrors
 * widgets.py's WIDGET_CATALOG/GRID_COLS/GRID_ROWS - kept in sync by
 * hand since there's no build step to share it directly with Python.
 *
 * i18n: this admin UI (palette/labels/hints) follows Home Assistant's
 * own configured language (hass.language) automatically, same as any
 * native HA panel - see _lang()/_t(). That's a *separate* axis from
 * each panel's own `language` field (edit-language select below),
 * which controls what's rendered on the physical display that panel
 * is assigned to - the person configuring InfoHub and the audience
 * standing in front of a given display aren't necessarily the same,
 * so a display's language is an explicit per-panel choice, not
 * inherited from the admin's browser.
 */

const STRINGS = {
  de: {
    addPanel: "+ Panel anlegen",
    noPanels: "Noch keine Panels.",
    delete: "Löschen",
    standard: "Standard",
    selectOrCreatePanel: "Panel links auswählen oder anlegen.",
    newPanelPrompt: "Name des neuen Panels:",
    confirmDeletePanel: "Panel wirklich löschen?",
    defaultPanelLabel: "Standard-Panel (Fallback für nicht zugeordnete Displays)",
    assignedDevice: "Zugeordnetes Display",
    displayLanguage: "Display-Sprache",
    loading: "Lädt…",
    noDeviceConnected: "Noch kein Display verbunden",
    noFixedDevice: "— kein festes Gerät (Standard-Panel) —",
    widgetsHeading: "Widgets",
    colEntity: "Entity",
    colLabel: "Label",
    colUnit: "Einheit",
    colWeather: "Wetter",
    placeholderLabel: "Label",
    placeholderUnit: "Einheit",
    weatherCheckbox: "Wetter",
    addEntity: "+ Hinzufügen",
    clickWidgetHint: "Widget anklicken, um Optionen zu bearbeiten.",
    noOptions: (label) => `${label} hat keine Optionen.`,
    optionsFor: (label) => `Optionen: ${label}`,
    entitiesFor: (label) => `Entities: ${label}`,
    noEntitiesForWidget: "Dieses Widget zeigt keine Entities an.",
    calendarEntityHint: "Die Kalenderquelle wird in den Integrations-Einstellungen konfiguriert (Konfigurieren → Google-Kalender-Entity).",
    saveFailedPrefix: "Speichern fehlgeschlagen: ",
    saveWidgetsError: "InfoHub: Speichern der Widgets fehlgeschlagen",
    loadDevicesError: "InfoHub: Geräteliste laden fehlgeschlagen",
  },
  en: {
    addPanel: "+ Add panel",
    noPanels: "No panels yet.",
    delete: "Delete",
    standard: "Default",
    selectOrCreatePanel: "Select a panel on the left, or create one.",
    newPanelPrompt: "Name of the new panel:",
    confirmDeletePanel: "Really delete this panel?",
    defaultPanelLabel: "Default panel (fallback for unassigned displays)",
    assignedDevice: "Assigned display",
    displayLanguage: "Display language",
    loading: "Loading…",
    noDeviceConnected: "No display connected yet",
    noFixedDevice: "— no fixed device (default panel) —",
    widgetsHeading: "Widgets",
    colEntity: "Entity",
    colLabel: "Label",
    colUnit: "Unit",
    colWeather: "Weather",
    placeholderLabel: "Label",
    placeholderUnit: "Unit",
    weatherCheckbox: "Weather",
    addEntity: "+ Add",
    clickWidgetHint: "Click a widget to edit its options.",
    noOptions: (label) => `${label} has no options.`,
    optionsFor: (label) => `Options: ${label}`,
    entitiesFor: (label) => `Entities: ${label}`,
    noEntitiesForWidget: "This widget doesn't display any entities.",
    calendarEntityHint: "The calendar source is configured in the integration's settings (Configure → Google Calendar entity).",
    saveFailedPrefix: "Save failed: ",
    saveWidgetsError: "InfoHub: failed to save widgets",
    loadDevicesError: "InfoHub: failed to load device list",
  },
};

// Mirrors custom_components/infohub/layout.py's _TYPE_TO_GROUP - which
// data group (and thus which of a panel's entities) a widget type reads
// from. "clock" has none - it renders local time, not HA state.
// "calendar_month" has one ("kalender") but entities for it aren't
// managed here - see the calendarEntityHint string.
const WIDGET_GROUPS = {
  weather_current: "wetter",
  power_gauge: "strom",
  waste_next: "abfall",
  indoor_climate: "raumklima",
  calendar_month: "kalender",
};

// Mirrors custom_components/infohub/widgets.py's WIDGET_CATALOG. Option
// field names here are the wire/schema keys (must match widgets.py);
// OPTION_LABELS below gives them a friendly, bilingual display name.
const WIDGET_CATALOG = {
  clock: {
    label: { de: "Uhr", en: "Clock" },
    default_size: [7, 3],
    options: {
      format: { type: "select", choices: ["24h", "12h"], default: "24h" },
      show_seconds: { type: "bool", default: false },
    },
  },
  weather_current: {
    label: { de: "Wetter", en: "Weather" },
    default_size: [7, 8],
    options: { show_scene: { type: "bool", default: true } },
  },
  power_gauge: {
    label: { de: "Strom", en: "Power" },
    default_size: [8, 6],
    options: { max_value: { type: "number", default: 5000 } },
  },
  indoor_climate: {
    label: { de: "Raumklima", en: "Indoor climate" },
    default_size: [7, 5],
    options: {},
  },
  waste_next: {
    label: { de: "Abfall", en: "Waste" },
    default_size: [8, 8],
    options: {},
  },
  calendar_month: {
    label: { de: "Kalender", en: "Calendar" },
    default_size: [9, 14],
    options: { months_shown: { type: "number", default: 2, min: 1, max: 2 } },
  },
};

const OPTION_LABELS = {
  format: { de: "Format", en: "Format" },
  show_seconds: { de: "Sekunden anzeigen", en: "Show seconds" },
  show_scene: { de: "Himmelsszene anzeigen", en: "Show sky scene" },
  max_value: { de: "Maximalwert", en: "Max value" },
  months_shown: { de: "Angezeigte Monate", en: "Months shown" },
};

const GRID_COLS = 24;
const GRID_ROWS = 14;
const CELL_PX = 40; // Editor-Canvas-Zellengroesse (Realitaet auf dem Display: 80px)

class InfohubPanel extends HTMLElement {
  constructor() {
    super();
    this._panels = {};
    this._selectedId = null;
    this._selectedWidgetId = null;
    this._unsubPromise = null;
    this._subscribed = false;
  }

  set hass(hass) {
    const prevLang = this._lang();
    this._hass = hass;
    if (!this._subscribed) {
      this._subscribed = true;
      this._subscribe();
    } else if (this._lang() !== prevLang) {
      // HA-Sprache kann sich zur Laufzeit aendern (z.B. Benutzerwechsel) -
      // dann muss die Admin-UI selbst (nicht die Panel-Sprache!) neu
      // gerendert werden, um die neue Sprache zu zeigen.
      this._render();
    }
  }

  get hass() {
    return this._hass;
  }

  _lang() {
    const l = (this._hass && this._hass.language) || "en";
    return l.toLowerCase().startsWith("de") ? "de" : "en";
  }

  _t(key, ...args) {
    const entry = STRINGS[this._lang()][key];
    return typeof entry === "function" ? entry(...args) : entry;
  }

  connectedCallback() {
    this._render();
  }

  disconnectedCallback() {
    if (this._unsubPromise) {
      this._unsubPromise.then((unsub) => unsub && unsub());
      this._unsubPromise = null;
    }
  }

  _subscribe() {
    this._unsubPromise = this._hass.connection.subscribeMessage(
      (updates) => this._handleUpdates(updates),
      { type: "infohub/panel/subscribe" }
    );
  }

  _handleUpdates(updates) {
    for (const change of updates) {
      if (change.change_type === "removed") {
        delete this._panels[change.panel_id];
        if (this._selectedId === change.panel_id) {
          this._selectedId = null;
        }
      } else {
        this._panels[change.panel_id] = change.item;
      }
    }
    if (this._selectedId === null) {
      const ids = Object.keys(this._panels);
      if (ids.length) {
        this._selectedId = ids[0];
      }
    }
    this._render();
  }

  _call(type, payload) {
    return this._hass.connection.sendMessagePromise({ type, ...(payload || {}) });
  }

  // -- Panels -------------------------------------------------------------

  async _createPanel() {
    const name = window.prompt(this._t("newPanelPrompt"));
    if (!name) return;
    const created = await this._call("infohub/panel/create", {
      name,
      is_default: Object.keys(this._panels).length === 0,
      entities: [],
      widgets: [],
    });
    this._panels[created.id] = created;
    this._selectedId = created.id;
    this._render();
  }

  async _deletePanel(panelId) {
    if (!window.confirm(this._t("confirmDeletePanel"))) return;
    await this._call("infohub/panel/delete", { panel_id: panelId });
    delete this._panels[panelId];
    if (this._selectedId === panelId) {
      this._selectedId = null;
    }
    this._render();
  }

  async _renamePanel(panelId, name) {
    const updated = await this._call("infohub/panel/update", { panel_id: panelId, name });
    this._panels[panelId] = updated;
    this._render();
  }

  async _setDefaultPanel(panelId) {
    const others = Object.values(this._panels).filter(
      (p) => p.id !== panelId && p.is_default
    );
    for (const other of others) {
      const updated = await this._call("infohub/panel/update", {
        panel_id: other.id,
        is_default: false,
      });
      this._panels[updated.id] = updated;
    }
    const updated = await this._call("infohub/panel/update", {
      panel_id: panelId,
      is_default: true,
    });
    this._panels[updated.id] = updated;
    this._render();
  }

  async _setAssignedDevice(panelId, deviceId) {
    const updated = await this._call("infohub/panel/update", {
      panel_id: panelId,
      assigned_device_id: deviceId || null,
    });
    this._panels[updated.id] = updated;
  }

  async _setLanguage(panelId, language) {
    const updated = await this._call("infohub/panel/update", {
      panel_id: panelId,
      language,
    });
    this._panels[updated.id] = updated;
  }

  async _loadKnownDevices() {
    try {
      return await this._call("infohub/devices/list");
    } catch (err) {
      console.error(this._t("loadDevicesError"), err);
      return [];
    }
  }

  // -- Entities -------------------------------------------------------------

  async _addEntity(panelId, entity) {
    const panel = this._panels[panelId];
    const entities = [...(panel.entities || []), entity];
    const updated = await this._call("infohub/panel/update", { panel_id: panelId, entities });
    this._panels[updated.id] = updated;
    this._render();
  }

  async _removeEntity(panelId, index) {
    const panel = this._panels[panelId];
    const entities = (panel.entities || []).filter((_, i) => i !== index);
    const updated = await this._call("infohub/panel/update", { panel_id: panelId, entities });
    this._panels[updated.id] = updated;
    this._render();
  }

  async _updateEntity(panelId, index, patch) {
    const panel = this._panels[panelId];
    const entities = (panel.entities || []).map((e, i) => (i === index ? { ...e, ...patch } : e));
    const updated = await this._call("infohub/panel/update", { panel_id: panelId, entities });
    this._panels[updated.id] = updated;
    this._render();
  }

  // -- Widgets (layout editor) ---------------------------------------------

  async _saveWidgets(panelId, widgets) {
    try {
      const updated = await this._call("infohub/panel/update", { panel_id: panelId, widgets });
      this._panels[updated.id] = updated;
      return updated;
    } catch (err) {
      // Ohne das hier waere ein fehlgeschlagenes Speichern unsichtbar -
      // das Widget saehe dann so aus, als waere der Drag "zurueckgesprungen".
      console.error(this._t("saveWidgetsError"), err);
      window.alert(this._t("saveFailedPrefix") + (err && err.message ? err.message : err));
      this._renderWidgetEditor(this._panels[panelId]);
      throw err;
    }
  }

  async _addWidget(panelId, type) {
    const panel = this._panels[panelId];
    const catalog = WIDGET_CATALOG[type];
    const options = {};
    for (const [name, field] of Object.entries(catalog.options || {})) {
      options[name] = field.default;
    }
    const widgets = [
      ...(panel.widgets || []),
      {
        id: type + "_" + Date.now(),
        type,
        pos: { col: 0, row: 0, colspan: catalog.default_size[0], rowspan: catalog.default_size[1] },
        options,
      },
    ];
    await this._saveWidgets(panelId, widgets);
    this._render();
  }

  async _removeWidget(panelId, widgetId) {
    const panel = this._panels[panelId];
    const widgets = (panel.widgets || []).filter((w) => w.id !== widgetId);
    await this._saveWidgets(panelId, widgets);
    if (this._selectedWidgetId === widgetId) this._selectedWidgetId = null;
    this._render();
  }

  async _updateWidgetPos(panelId, widgetId, pos) {
    const panel = this._panels[panelId];
    const widgets = (panel.widgets || []).map((w) => (w.id === widgetId ? { ...w, pos } : w));
    const updated = await this._saveWidgets(panelId, widgets);
    this._renderWidgetEditor(updated);
  }

  async _updateWidgetOptions(panelId, widgetId, newOptions) {
    const panel = this._panels[panelId];
    const widgets = (panel.widgets || []).map((w) =>
      w.id === widgetId ? { ...w, options: { ...w.options, ...newOptions } } : w
    );
    await this._saveWidgets(panelId, widgets);
  }

  // -- Rendering ------------------------------------------------------------

  _render() {
    const t = STRINGS[this._lang()];
    const panels = Object.values(this._panels).sort((a, b) => a.name.localeCompare(b.name));
    const selected = this._selectedId ? this._panels[this._selectedId] : null;

    this.innerHTML = `
      <style>
        infohub-panel, .infohub-root {
          display: block;
          padding: 16px;
          max-width: 1100px;
          margin: 0 auto;
          color: var(--primary-text-color);
        }
        .infohub-title {
          font-size: 24px;
          font-weight: 400;
          margin: 8px 0 16px;
        }
        .infohub-layout {
          display: grid;
          grid-template-columns: 260px 1fr;
          gap: 16px;
        }
        @media (max-width: 900px) {
          .infohub-layout { grid-template-columns: 1fr; }
        }
        .infohub-card { padding: 16px; }
        .panel-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px;
          border-radius: 8px;
          cursor: pointer;
        }
        .panel-row.selected { background: var(--secondary-background-color, #eee); }
        .panel-row .name { display: flex; align-items: center; gap: 6px; }
        .badge {
          font-size: 11px;
          padding: 2px 6px;
          border-radius: 10px;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
        }
        button.icon-button {
          background: none;
          border: none;
          color: var(--secondary-text-color);
          cursor: pointer;
          font-size: 16px;
        }
        .add-panel-btn { margin-top: 8px; width: 100%; }
        h3 { font-size: 15px; font-weight: 500; margin: 20px 0 8px; }
        table.entity-table { width: 100%; border-collapse: collapse; }
        table.entity-table td, table.entity-table th {
          padding: 6px 4px;
          border-bottom: 1px solid var(--divider-color);
          text-align: left;
          font-size: 14px;
        }
        table.entity-table ha-entity-picker { min-width: 220px; display: block; }
        .entity-add-row {
          display: grid;
          grid-template-columns: 2fr 1fr 1fr auto auto;
          gap: 6px;
          align-items: center;
          margin-top: 12px;
        }
        input[type="text"], input[type="number"], select {
          padding: 6px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color);
        }
        .hint { color: var(--secondary-text-color); font-size: 13px; }
        .widget-palette { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
        .widget-palette button {
          padding: 6px 10px;
          border: 1px solid var(--divider-color);
          border-radius: 6px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color);
          cursor: pointer;
        }
        .grid-canvas {
          position: relative;
          width: ${GRID_COLS * CELL_PX}px;
          height: ${GRID_ROWS * CELL_PX}px;
          background-image:
            linear-gradient(to right, var(--divider-color) 1px, transparent 1px),
            linear-gradient(to bottom, var(--divider-color) 1px, transparent 1px);
          background-size: ${CELL_PX}px ${CELL_PX}px;
          border: 1px solid var(--divider-color);
          overflow: hidden;
          touch-action: none;
        }
        .widget-box {
          position: absolute;
          box-sizing: border-box;
          border: 1px solid var(--primary-color);
          background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.15);
          border-radius: 6px;
          padding: 4px 6px;
          font-size: 12px;
          color: var(--primary-text-color);
          cursor: move;
          user-select: none;
        }
        .widget-box.selected { border-width: 2px; background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.3); }
        .widget-box .remove-widget {
          position: absolute; top: 2px; right: 2px;
          background: none; border: none; cursor: pointer;
          color: var(--secondary-text-color); font-size: 12px;
        }
        .resize-handle {
          position: absolute; right: 0; bottom: 0;
          width: 14px; height: 14px;
          cursor: nwse-resize;
          background: var(--primary-color);
          opacity: 0.6;
          border-radius: 2px 0 6px 0;
        }
        .options-form { margin-top: 12px; display: grid; gap: 8px; max-width: 320px; }
        .options-form label { font-size: 13px; display: flex; justify-content: space-between; gap: 8px; align-items: center; }
      </style>
      <div class="infohub-root">
        <div class="infohub-title">InfoHub</div>
        <div class="infohub-layout">
          <ha-card class="infohub-card">
            <div id="panel-list"></div>
            <button class="add-panel-btn" id="add-panel">${t.addPanel}</button>
          </ha-card>
          <ha-card class="infohub-card" id="panel-editor"></ha-card>
        </div>
      </div>
    `;

    const listEl = this.querySelector("#panel-list");
    listEl.innerHTML =
      panels
        .map(
          (p) => `
        <div class="panel-row ${p.id === this._selectedId ? "selected" : ""}" data-id="${p.id}">
          <span class="name">${_escape(p.name)} ${p.is_default ? `<span class="badge">${t.standard}</span>` : ""}</span>
          <button class="icon-button" data-delete="${p.id}" title="${t.delete}">✕</button>
        </div>`
        )
        .join("") || `<div class="hint">${t.noPanels}</div>`;

    listEl.querySelectorAll(".panel-row").forEach((row) => {
      row.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-delete]")) return;
        this._selectedId = row.dataset.id;
        this._selectedWidgetId = null;
        this._render();
      });
    });
    listEl.querySelectorAll("[data-delete]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._deletePanel(btn.dataset.delete);
      });
    });
    this.querySelector("#add-panel").addEventListener("click", () => this._createPanel());

    this._renderEditor(selected);
  }

  _renderEditor(panel) {
    const t = STRINGS[this._lang()];
    const editor = this.querySelector("#panel-editor");
    if (!panel) {
      editor.innerHTML = `<div class="hint">${t.selectOrCreatePanel}</div>`;
      return;
    }

    const language = panel.language || "en";
    editor.innerHTML = `
      <div style="display:flex; align-items:center; gap:16px; margin-bottom:16px; flex-wrap: wrap;">
        <input type="text" id="edit-name" value="${_escapeAttr(panel.name)}" />
        <label class="hint">
          <input type="checkbox" id="edit-default" ${panel.is_default ? "checked" : ""} />
          ${t.defaultPanelLabel}
        </label>
        <label class="hint">
          ${t.assignedDevice}
          <select id="edit-device"><option value="">${t.loading}</option></select>
        </label>
        <label class="hint">
          ${t.displayLanguage}
          <select id="edit-language">
            <option value="de" ${language === "de" ? "selected" : ""}>Deutsch</option>
            <option value="en" ${language === "en" ? "selected" : ""}>English</option>
          </select>
        </label>
      </div>

      <h3>${t.widgetsHeading}</h3>
      <div class="widget-palette" id="widget-palette"></div>
      <div id="grid-wrap"></div>
      <div id="widget-options"></div>
    `;

    editor.querySelector("#edit-name").addEventListener("change", (ev) => {
      this._renamePanel(panel.id, ev.target.value);
    });
    editor.querySelector("#edit-default").addEventListener("change", (ev) => {
      if (ev.target.checked) this._setDefaultPanel(panel.id);
    });
    editor.querySelector("#edit-language").addEventListener("change", (ev) => {
      this._setLanguage(panel.id, ev.target.value);
    });
    this._populateDeviceSelect(panel);

    const palette = editor.querySelector("#widget-palette");
    palette.innerHTML = Object.entries(WIDGET_CATALOG)
      .map(([type, cat]) => `<button data-add="${type}">+ ${_escape(cat.label[this._lang()])}</button>`)
      .join("");
    palette.querySelectorAll("[data-add]").forEach((btn) => {
      btn.addEventListener("click", () => this._addWidget(panel.id, btn.dataset.add));
    });

    this._renderWidgetEditor(panel);
  }

  async _populateDeviceSelect(panel) {
    const t = STRINGS[this._lang()];
    const devices = await this._loadKnownDevices();
    // Der Editor kann inzwischen neu gerendert oder ein anderes Panel
    // ausgewaehlt worden sein - dann gibt es das Element nicht mehr
    // oder es gehoert nicht mehr zu diesem Panel.
    const select = this.querySelector("#edit-device");
    if (!select) return;

    if (!devices.length) {
      select.innerHTML = `<option value="">${t.noDeviceConnected}</option>`;
      return;
    }

    const options = [
      `<option value="">${t.noFixedDevice}</option>`,
      ...devices.map(
        (d) =>
          `<option value="${_escapeAttr(d.device_id)}" ${
            d.device_id === panel.assigned_device_id ? "selected" : ""
          }>${_escape(d.device_id)}</option>`
      ),
    ];
    select.innerHTML = options.join("");
    select.addEventListener("change", (ev) => {
      this._setAssignedDevice(panel.id, ev.target.value);
    });
  }

  _renderWidgetEditor(panel) {
    const wrap = this.querySelector("#grid-wrap");
    if (!wrap) return;

    const lang = this._lang();
    const widgets = panel.widgets || [];
    wrap.innerHTML = `<div class="grid-canvas" id="grid-canvas"></div>`;
    const canvas = wrap.querySelector("#grid-canvas");

    for (const widget of widgets) {
      const catalog = WIDGET_CATALOG[widget.type] || { label: { de: widget.type, en: widget.type } };
      const el = document.createElement("div");
      el.className = "widget-box" + (widget.id === this._selectedWidgetId ? " selected" : "");
      el.style.left = widget.pos.col * CELL_PX + "px";
      el.style.top = widget.pos.row * CELL_PX + "px";
      el.style.width = widget.pos.colspan * CELL_PX + "px";
      el.style.height = widget.pos.rowspan * CELL_PX + "px";
      el.textContent = catalog.label[lang];
      el.dataset.id = widget.id;

      const removeBtn = document.createElement("button");
      removeBtn.className = "remove-widget";
      removeBtn.textContent = "✕";
      removeBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._removeWidget(panel.id, widget.id);
      });
      el.appendChild(removeBtn);

      const handle = document.createElement("div");
      handle.className = "resize-handle";
      el.appendChild(handle);

      el.addEventListener("click", (ev) => {
        if (ev.target === removeBtn || ev.target === handle) return;
        // Nur Auswahl togglen, kein Voll-Rebuild des Canvas: ein click
        // feuert auch nach einem Drag (pointerdown+up auf demselben
        // Element), und ein Rebuild hier wuerde mit dem beim Aufruf von
        // _renderWidgetEditor() eingefangenen (potenziell veralteten)
        // `panel`-Stand die gerade bestaetigte Drag-Position wieder
        // ueberschreiben.
        this._selectedWidgetId = widget.id;
        canvas.querySelectorAll(".widget-box").forEach((box) => box.classList.remove("selected"));
        el.classList.add("selected");
        const current = this._panels[panel.id] || panel;
        const currentWidget = (current.widgets || []).find((w) => w.id === widget.id) || widget;
        this._renderWidgetOptions(current, currentWidget);
      });

      this._attachDragHandlers(el, handle, widget, panel, canvas);
      canvas.appendChild(el);
    }

    const selectedWidget = widgets.find((w) => w.id === this._selectedWidgetId);
    this._renderWidgetOptions(panel, selectedWidget);
  }

  _attachDragHandlers(el, handle, widget, panel, canvas) {
    const maxLeft = (GRID_COLS - 2) * CELL_PX;
    const maxTop = (GRID_ROWS - 2) * CELL_PX;

    let dragging = false;
    let startX = 0;
    let startY = 0;
    let origLeft = 0;
    let origTop = 0;

    el.addEventListener("pointerdown", (ev) => {
      // Nicht nur den Resize-Griff ausschliessen, sondern jeden Steuer-
      // Button in der Box (z.B. den Entfernen-Button) - sonst kapert
      // setPointerCapture() unten den Pointer, bevor dessen eigener
      // click-Handler (Entfernen) ueberhaupt zum Zug kommt.
      if (ev.target.closest(".resize-handle, .remove-widget")) return;
      dragging = true;
      el.setPointerCapture(ev.pointerId);
      startX = ev.clientX;
      startY = ev.clientY;
      origLeft = parseFloat(el.style.left);
      origTop = parseFloat(el.style.top);
    });
    el.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      const left = Math.min(Math.max(0, origLeft + ev.clientX - startX), maxLeft);
      const top = Math.min(Math.max(0, origTop + ev.clientY - startY), maxTop);
      el.style.left = left + "px";
      el.style.top = top + "px";
    });
    el.addEventListener("pointerup", (ev) => {
      if (!dragging) return;
      dragging = false;
      el.releasePointerCapture(ev.pointerId);
      const col = Math.round(parseFloat(el.style.left) / CELL_PX);
      const row = Math.round(parseFloat(el.style.top) / CELL_PX);
      el.style.left = col * CELL_PX + "px";
      el.style.top = row * CELL_PX + "px";
      this._updateWidgetPos(panel.id, widget.id, {
        col, row, colspan: widget.pos.colspan, rowspan: widget.pos.rowspan,
      });
    });

    let resizing = false;
    let startW = 0;
    let startH = 0;

    handle.addEventListener("pointerdown", (ev) => {
      resizing = true;
      handle.setPointerCapture(ev.pointerId);
      startX = ev.clientX;
      startY = ev.clientY;
      startW = parseFloat(el.style.width);
      startH = parseFloat(el.style.height);
      ev.stopPropagation();
    });
    handle.addEventListener("pointermove", (ev) => {
      if (!resizing) return;
      const w = Math.max(2 * CELL_PX, startW + ev.clientX - startX);
      const h = Math.max(2 * CELL_PX, startH + ev.clientY - startY);
      el.style.width = w + "px";
      el.style.height = h + "px";
    });
    handle.addEventListener("pointerup", (ev) => {
      if (!resizing) return;
      resizing = false;
      handle.releasePointerCapture(ev.pointerId);
      const colspan = Math.max(2, Math.round(parseFloat(el.style.width) / CELL_PX));
      const rowspan = Math.max(2, Math.round(parseFloat(el.style.height) / CELL_PX));
      el.style.width = colspan * CELL_PX + "px";
      el.style.height = rowspan * CELL_PX + "px";
      const col = Math.round(parseFloat(el.style.left) / CELL_PX);
      const row = Math.round(parseFloat(el.style.top) / CELL_PX);
      this._updateWidgetPos(panel.id, widget.id, { col, row, colspan, rowspan });
      ev.stopPropagation();
    });
  }

  _renderWidgetOptions(panel, widget) {
    const t = STRINGS[this._lang()];
    const lang = this._lang();
    const box = this.querySelector("#widget-options");
    if (!box) return;
    if (!widget) {
      box.innerHTML = `<div class="hint">${t.clickWidgetHint}</div>`;
      return;
    }
    const widgetLabel = WIDGET_CATALOG[widget.type]?.label[lang] || widget.type;
    const schema = (WIDGET_CATALOG[widget.type] || {}).options || {};
    const entries = Object.entries(schema);

    const optionsHtml = entries.length
      ? `
        <div class="hint">${_escape(t.optionsFor(widgetLabel))}</div>
        <div class="options-form">
          ${entries
            .map(([name, field]) => {
              const optionLabel = (OPTION_LABELS[name] && OPTION_LABELS[name][lang]) || name;
              const value = widget.options ? widget.options[name] : undefined;
              const current = value === undefined ? field.default : value;
              if (field.type === "bool") {
                return `<label>${_escape(optionLabel)}<input type="checkbox" data-opt="${name}" data-opt-type="bool" ${current ? "checked" : ""} /></label>`;
              }
              if (field.type === "select") {
                return `<label>${_escape(optionLabel)}<select data-opt="${name}" data-opt-type="select">${(field.choices || [])
                  .map((c) => `<option value="${_escapeAttr(c)}" ${c === current ? "selected" : ""}>${_escape(c)}</option>`)
                  .join("")}</select></label>`;
              }
              return `<label>${_escape(optionLabel)}<input type="number" data-opt="${name}" data-opt-type="number" value="${_escapeAttr(current)}" ${
                field.min !== undefined ? `min="${field.min}"` : ""
              } ${field.max !== undefined ? `max="${field.max}"` : ""} /></label>`;
            })
            .join("")}
        </div>
      `
      : `<div class="hint">${_escape(t.noOptions(widgetLabel))}</div>`;

    // Entities are shown per-widget (only those feeding the group this
    // widget type reads from - see WIDGET_GROUPS), not as one flat list
    // of everything the panel happens to use.
    const group = WIDGET_GROUPS[widget.type];
    let entitiesHtml;
    if (!group) {
      entitiesHtml = `<div class="hint" style="margin-top:16px;">${t.noEntitiesForWidget}</div>`;
    } else if (group === "kalender") {
      entitiesHtml = `<div class="hint" style="margin-top:16px;">${t.calendarEntityHint}</div>`;
    } else {
      const showWeatherCol = group === "wetter";
      const indexed = (panel.entities || [])
        .map((e, i) => ({ e, i }))
        .filter(({ e }) => e.group === group);
      entitiesHtml = `
        <div class="hint" style="margin-top:16px;">${_escape(t.entitiesFor(widgetLabel))}</div>
        <table class="entity-table">
          <thead>
            <tr><th>${t.colEntity}</th><th>${t.colLabel}</th><th>${t.colUnit}</th>${showWeatherCol ? `<th>${t.colWeather}</th>` : ""}<th></th></tr>
          </thead>
          <tbody>
            ${indexed
              .map(
                ({ e, i }) => `
              <tr>
                <td><ha-entity-picker class="inline-entity-picker" data-index="${i}"></ha-entity-picker></td>
                <td>${_escape(e.label || "")}</td>
                <td>${_escape(e.unit || "")}</td>
                ${showWeatherCol ? `<td>${e.type === "weather" ? "✓" : ""}</td>` : ""}
                <td><button class="icon-button" data-remove-entity="${i}">✕</button></td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
        <div class="entity-add-row">
          <ha-entity-picker id="widget-entity-picker"></ha-entity-picker>
          <input type="text" id="widget-entity-label" placeholder="${t.placeholderLabel}" />
          <input type="text" id="widget-entity-unit" placeholder="${t.placeholderUnit}" />
          ${showWeatherCol ? `<label class="hint"><input type="checkbox" id="widget-entity-weather" /> ${t.weatherCheckbox}</label>` : "<span></span>"}
          <button id="widget-entity-add">${t.addEntity}</button>
        </div>
      `;
    }

    box.innerHTML = optionsHtml + entitiesHtml;

    box.querySelectorAll("[data-opt]").forEach((input) => {
      input.addEventListener("change", () => {
        const name = input.dataset.opt;
        let value;
        if (input.dataset.optType === "bool") value = input.checked;
        else if (input.dataset.optType === "number") value = Number(input.value);
        else value = input.value;
        this._updateWidgetOptions(panel.id, widget.id, { [name]: value });
      });
    });

    if (group && group !== "kalender") {
      box.querySelectorAll("[data-remove-entity]").forEach((btn) => {
        btn.addEventListener("click", () => {
          this._removeEntity(panel.id, parseInt(btn.dataset.removeEntity, 10));
        });
      });
      box.querySelectorAll(".inline-entity-picker").forEach((inlinePicker) => {
        const index = parseInt(inlinePicker.dataset.index, 10);
        const current = (panel.entities || [])[index];
        inlinePicker.hass = this._hass;
        if (current) inlinePicker.value = current.entity_id;
        inlinePicker.addEventListener("value-changed", (ev) => {
          const newEntityId = ev.detail.value;
          if (!newEntityId || (current && newEntityId === current.entity_id)) return;
          this._updateEntity(panel.id, index, { entity_id: newEntityId });
        });
      });
      const picker = box.querySelector("#widget-entity-picker");
      picker.hass = this._hass;
      box.querySelector("#widget-entity-add").addEventListener("click", () => {
        const entityId = picker.value;
        if (!entityId) return;
        const label = box.querySelector("#widget-entity-label").value || entityId;
        const unit = box.querySelector("#widget-entity-unit").value || null;
        const weatherCheckbox = box.querySelector("#widget-entity-weather");
        const isWeather = weatherCheckbox ? weatherCheckbox.checked : false;
        this._addEntity(panel.id, {
          entity_id: entityId,
          group,
          label,
          unit,
          type: isWeather ? "weather" : null,
        });
      });
    }
  }
}

function _escape(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function _escapeAttr(value) {
  return _escape(value).replace(/"/g, "&quot;");
}

customElements.define("infohub-panel", InfohubPanel);
