/**
 * InfoHub sidebar config panel.
 *
 * Plain vanilla-JS custom element - deliberately no Lit/build step (no
 * Node bundler or browser was available to test one from where this was
 * written). Reuses Home Assistant's own globally-registered elements
 * (<ha-card>) where that's straightforward. Entity selection uses a
 * plain <select> over hass.states rather than HA's <ha-entity-picker> -
 * that component lives in a JS chunk the frontend only lazy-loads once
 * something else (e.g. a Lovelace card editor) has already triggered
 * it, which navigating straight to this panel never does; it silently
 * renders as an inert, empty tag otherwise (see git history for the
 * bug this caused). Talks to the backend exclusively through the websocket
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
    aliasLabel: "Anzeigename (überschreibt den Standardtitel)",
    colEntity: "Entity",
    colLabel: "Label",
    colUnit: "Einheit",
    colWeather: "Wetter",
    colControl: "Steuerung",
    colMin: "Min",
    colMax: "Max",
    controlToggle: "Schalter",
    controlCover: "Rollladen (Auf/Stop/Zu)",
    controlSlider: "Slider",
    selectEntityPlaceholder: "— Entity wählen —",
    placeholderLabel: "Label",
    placeholderUnit: "Einheit",
    placeholderMin: "Min",
    placeholderMax: "Max",
    weatherCheckbox: "Wetter",
    addEntity: "+ Entity hinzufügen",
    done: "Fertig",
    cancel: "Abbrechen",
    noEntitiesYet: "Noch keine Entities hinzugefügt.",
    editEntityTitle: "Bearbeiten",
    removeEntityTitle: "Entfernen",
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
    aliasLabel: "Display name (overrides the default title)",
    colEntity: "Entity",
    colLabel: "Label",
    colUnit: "Unit",
    colWeather: "Weather",
    colControl: "Control",
    colMin: "Min",
    colMax: "Max",
    controlToggle: "Switch",
    controlCover: "Cover (Open/Stop/Close)",
    controlSlider: "Slider",
    selectEntityPlaceholder: "— Select entity —",
    placeholderLabel: "Label",
    placeholderUnit: "Unit",
    placeholderMin: "Min",
    placeholderMax: "Max",
    weatherCheckbox: "Weather",
    addEntity: "+ Add entity",
    done: "Done",
    cancel: "Cancel",
    noEntitiesYet: "No entities added yet.",
    editEntityTitle: "Edit",
    removeEntityTitle: "Remove",
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
  value_tile: "custom",
  switch_tile: "aktoren",
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
  // Generic widget: shows every entity in the panel's "custom" group
  // (see WIDGET_GROUPS), one per row - no per-instance selection needed,
  // the entity table below (scoped to this same group) is what controls
  // which entities show up here. Lets the widget gallery grow to "any
  // entity" without a new hardcoded type/renderer per kind of info.
  value_tile: {
    label: { de: "Info-Kachel", en: "Info Tile" },
    default_size: [7, 6],
    options: {},
  },
  // Same one-row-per-entity idea as value_tile, for the "aktoren" group -
  // but each row is a tappable toggle switch on the physical display
  // (rendering/tap-handling lives in main_mp.py, nothing to configure
  // here beyond which entities are in the group).
  switch_tile: {
    label: { de: "Schalter", en: "Switches" },
    default_size: [7, 6],
    options: {},
  },
};

// Per-row actuator control choices for the "aktoren" group's entity
// table - mirrors EntityConfig.type's meaning for that group (see
// entities.py). "" (stored as null/None) is the default on/off toggle.
const AKTOR_CONTROL_CHOICES = [
  { value: "", labelKey: "controlToggle" },
  { value: "cover", labelKey: "controlCover" },
  { value: "slider", labelKey: "controlSlider" },
];

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
    // UI-only state for the entity list's expand-to-edit rows (see
    // _renderEntityList()) - never persisted, reset whenever the
    // selected widget changes so a stale index can't leak across widgets.
    this._entityEditIndex = null;
    this._addingEntity = false;
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

  async _updateWidgetAlias(panelId, widgetId, alias) {
    const panel = this._panels[panelId];
    const widgets = (panel.widgets || []).map((w) => (w.id === widgetId ? { ...w, alias } : w));
    const updated = await this._saveWidgets(panelId, widgets);
    // Canvas box text shows the alias too (see _renderWidgetEditor) - a
    // full editor rerender isn't needed, just the canvas.
    this._renderWidgetEditor(updated);
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
        /* Entity list: a compact, collapsed card per entity that expands
           inline into an edit form on tap - see _entityItemHtml() /
           _entityAddFormHtml(). Chosen over the old fixed-column table
           once "aktoren" needed three extra columns (control/min/max) and
           rows got too wide for the sidebar panel; the edit form's own
           grid reflows itself (auto-fit) instead of needing a different
           fixed column count per data group. */
        .entity-list { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
        .entity-item {
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          background: var(--card-background-color, #fff);
          overflow: hidden;
        }
        .entity-item-row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 12px;
          cursor: pointer;
        }
        .entity-item-row:hover { background: var(--secondary-background-color, rgba(0, 0, 0, 0.04)); }
        .entity-item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
        .entity-item-label {
          font-size: 14px; font-weight: 500;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .entity-item-id {
          font-size: 11px; color: var(--secondary-text-color); font-family: monospace;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .entity-item-pill {
          flex-shrink: 0;
          font-size: 10px; padding: 3px 8px; border-radius: 10px;
          background: var(--secondary-background-color, #eee);
          color: var(--secondary-text-color);
          white-space: nowrap;
        }
        .entity-item-pill.pill-cover { background: rgba(245, 158, 11, 0.18); color: #f59e0b; }
        .entity-item-pill.pill-slider { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.18); color: var(--primary-color); }
        .entity-item-pill.pill-weather { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.18); color: var(--primary-color); }
        .entity-item-chevron {
          flex-shrink: 0;
          color: var(--secondary-text-color);
          transition: transform 0.15s ease;
        }
        .entity-item.expanded .entity-item-chevron { transform: rotate(90deg); }
        .entity-item.expanded .entity-item-row { border-bottom: 1px solid var(--divider-color); }
        .entity-item-edit {
          padding: 12px;
          background: var(--secondary-background-color, rgba(0, 0, 0, 0.02));
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 10px;
        }
        .entity-item-edit label {
          display: flex; flex-direction: column; gap: 4px;
          font-size: 11px; color: var(--secondary-text-color);
        }
        .entity-item-edit label.full { grid-column: 1 / -1; }
        .entity-item-edit label.checkbox-label { flex-direction: row; align-items: center; gap: 6px; }
        .entity-item-edit-actions {
          grid-column: 1 / -1;
          display: flex; justify-content: flex-end; gap: 8px;
          margin-top: 2px;
        }
        .entity-item-edit-actions button, .entity-add-trigger {
          padding: 7px 14px;
          border-radius: 8px;
          border: 1px solid var(--divider-color);
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color);
          cursor: pointer;
          font-size: 13px;
        }
        .entity-done-btn, .entity-add-confirm {
          background: var(--primary-color);
          border-color: var(--primary-color);
          color: var(--text-primary-color, #fff);
        }
        .entity-add-trigger {
          width: 100%;
          margin-top: 8px;
          border-style: dashed;
          color: var(--primary-color);
        }
        .entity-empty {
          padding: 16px;
          text-align: center;
          color: var(--secondary-text-color);
          font-size: 13px;
          border: 1px dashed var(--divider-color);
          border-radius: 10px;
        }
        input[type="text"], input[type="number"], select {
          padding: 6px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color);
        }
        .hint { color: var(--secondary-text-color); font-size: 13px; }
        .widget-palette { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px; }
        .widget-palette-btn {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          width: 92px;
          padding: 6px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color);
          cursor: pointer;
          font-size: 11px;
        }
        /* Rough CSS mockups, not pixel-accurate renders - just enough to
           recognize a widget type before adding it. Plain text/emoji only,
           no HA-only elements (ha-icon etc. are lazily loaded and would
           render blank the same way ha-entity-picker did - see git log). */
        .widget-preview {
          width: 80px;
          height: 52px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          font-size: 10px;
          overflow: hidden;
          background: #1a1a3a;
        }
        .widget-preview-clock .mock-text { font-family: monospace; font-size: 15px; letter-spacing: 1px; }
        .widget-preview-weather_current { background: linear-gradient(180deg, #4a90d9, #1a1a3a); font-size: 18px; }
        .widget-preview-power_gauge .mock-arc {
          width: 34px; height: 34px; border-radius: 50%;
          background: conic-gradient(#22c55e 0deg 250deg, #2d2d44 250deg 360deg);
          display: flex; align-items: center; justify-content: center; font-size: 14px;
        }
        .widget-preview-calendar_month .mock-grid { display: grid; grid-template-columns: repeat(5, 7px); gap: 2px; }
        .widget-preview-calendar_month .mock-grid span { width: 7px; height: 7px; background: #4a4a6a; border-radius: 1px; }
        .widget-preview-value_tile { border: 1px dashed #4a4a6a; font-size: 20px; }
        .widget-preview-switch_tile .mock-switch {
          width: 34px; height: 18px; border-radius: 10px;
          background: #22c55e; position: relative;
        }
        .widget-preview-switch_tile .mock-switch::after {
          content: ""; position: absolute; top: 2px; right: 2px;
          width: 14px; height: 14px; border-radius: 50%; background: #fff;
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
        this._entityEditIndex = null;
        this._addingEntity = false;
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
      .map(
        ([type, cat]) => `
      <button class="widget-palette-btn" data-add="${type}">
        <div class="widget-preview widget-preview-${type}">${_widgetPreviewContent(type)}</div>
        <span>${_escape(cat.label[this._lang()])}</span>
      </button>`
      )
      .join("");
    palette.querySelectorAll("[data-add]").forEach((btn) => {
      btn.addEventListener("click", () => this._addWidget(panel.id, btn.dataset.add));
    });

    this._renderWidgetEditor(panel);
  }

  // Plain <select> of all known entity_ids, instead of <ha-entity-picker>:
  // that component lives in a lazily-loaded HA frontend chunk that's only
  // fetched once something else (e.g. a Lovelace card editor) triggers it
  // first - navigating straight to this sidebar panel never does, leaving
  // the tag undefined/blank. hass.states is always available though, and
  // a native <select> is exactly the dropdown that was asked for anyway.
  _entitySelectOptions(selectedValue) {
    const ids = Object.keys((this._hass && this._hass.states) || {}).sort();
    return ids
      .map(
        (id) =>
          `<option value="${_escapeAttr(id)}" ${id === selectedValue ? "selected" : ""}>${_escape(id)}</option>`
      )
      .join("");
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
      el.textContent = widget.alias || catalog.label[lang];
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
        this._entityEditIndex = null;
        this._addingEntity = false;
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
    const aliasHtml = `
      <div class="options-form" style="max-width:320px;">
        <label>${t.aliasLabel}<input type="text" id="widget-alias-input" value="${_escapeAttr(widget.alias || "")}" placeholder="${_escapeAttr(widgetLabel)}" /></label>
      </div>
    `;
    const schema = (WIDGET_CATALOG[widget.type] || {}).options || {};
    const entries = Object.entries(schema);
    // Widget's own data group (see WIDGET_GROUPS) - both for the entity
    // list below and for scoping an "entity"-type option field (e.g.
    // value_tile's entity_id) to entities actually available to it.
    const group = WIDGET_GROUPS[widget.type];

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

    let entitiesHtml;
    if (!group) {
      entitiesHtml = `<div class="hint" style="margin-top:16px;">${t.noEntitiesForWidget}</div>`;
    } else if (group === "kalender") {
      entitiesHtml = `<div class="hint" style="margin-top:16px;">${t.calendarEntityHint}</div>`;
    } else {
      const indexed = (panel.entities || [])
        .map((e, i) => ({ e, i }))
        .filter(({ e }) => e.group === group);
      entitiesHtml = `
        <div class="hint" style="margin-top:16px;">${_escape(t.entitiesFor(widgetLabel))}</div>
        <div class="entity-list">
          ${
            indexed.length
              ? indexed.map(({ e, i }) => this._entityItemHtml(t, group, e, i)).join("")
              : this._addingEntity
                ? ""
                : `<div class="entity-empty">${t.noEntitiesYet}</div>`
          }
          ${this._addingEntity ? this._entityAddFormHtml(t, group) : ""}
        </div>
        ${this._addingEntity ? "" : `<button class="entity-add-trigger" id="entity-add-trigger">${t.addEntity}</button>`}
      `;
    }

    box.innerHTML = aliasHtml + optionsHtml + entitiesHtml;

    box.querySelector("#widget-alias-input").addEventListener("change", (ev) => {
      this._updateWidgetAlias(panel.id, widget.id, ev.target.value.trim() || null);
    });

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
      this._wireEntityList(box, panel, widget, group);
    }
  }

  // -- Entity list (expand-to-edit cards) ------------------------------------
  //
  // Each tracked entity renders as a compact one-line card; tapping it
  // expands an inline edit form below it (entity/label/unit plus
  // group-specific fields - weather checkbox, or aktoren's control
  // type + min/max). Only one card (or the "add entity" form) is ever
  // expanded at a time - purely local UI state (this._entityEditIndex /
  // this._addingEntity, reset whenever the selected widget changes), not
  // persisted. Replaces the old always-expanded, fixed-column table,
  // which had grown too wide once aktoren needed three extra columns.

  _entityPillHtml(t, group, e) {
    if (group === "aktoren") {
      const choice = AKTOR_CONTROL_CHOICES.find((c) => c.value === (e.type || "")) || AKTOR_CONTROL_CHOICES[0];
      const cls = e.type === "cover" ? " pill-cover" : e.type === "slider" ? " pill-slider" : "";
      return `<span class="entity-item-pill${cls}">${_escape(t[choice.labelKey])}</span>`;
    }
    if (group === "wetter" && e.type === "weather") {
      return `<span class="entity-item-pill pill-weather">★ ${_escape(t.colWeather)}</span>`;
    }
    if (e.unit) {
      return `<span class="entity-item-pill">${_escape(e.unit)}</span>`;
    }
    return "";
  }

  _entityFieldsHtml(t, group, e, index) {
    const isSlider = (e.type || "") === "slider";
    const entityOptions = this._entitySelectOptions(e.entity_id || null);
    let fields = `
      <label class="full">${t.colEntity}
        <select class="entity-field" data-field="entity_id" data-index="${index}">
          ${index === "new" ? `<option value="">${t.selectEntityPlaceholder}</option>` : ""}${entityOptions}
        </select>
      </label>
      <label>${t.colLabel}
        <input type="text" class="entity-field" data-field="label" data-index="${index}" value="${_escapeAttr(e.label || "")}" placeholder="${t.placeholderLabel}" />
      </label>
      <label>${t.colUnit}
        <input type="text" class="entity-field" data-field="unit" data-index="${index}" value="${_escapeAttr(e.unit || "")}" placeholder="${t.placeholderUnit}" />
      </label>
    `;
    if (group === "wetter") {
      fields += `
        <label class="full checkbox-label">
          <input type="checkbox" class="entity-field" data-field="weather" data-index="${index}" ${e.type === "weather" ? "checked" : ""} />
          ${t.weatherCheckbox}
        </label>
      `;
    } else if (group === "aktoren") {
      fields += `
        <label>${t.colControl}
          <select class="entity-field entity-control-select" data-field="control" data-index="${index}">
            ${AKTOR_CONTROL_CHOICES.map((c) => `<option value="${c.value}" ${c.value === (e.type || "") ? "selected" : ""}>${_escape(t[c.labelKey])}</option>`).join("")}
          </select>
        </label>
        <label>${t.colMin}
          <input type="number" class="entity-field entity-min-input" data-field="min" data-index="${index}" value="${e.min_value ?? ""}" ${isSlider ? "" : "disabled"} />
        </label>
        <label>${t.colMax}
          <input type="number" class="entity-field entity-max-input" data-field="max" data-index="${index}" value="${e.max_value ?? ""}" ${isSlider ? "" : "disabled"} />
        </label>
      `;
    }
    return fields;
  }

  _entityItemHtml(t, group, e, i) {
    const expanded = this._entityEditIndex === i;
    return `
      <div class="entity-item${expanded ? " expanded" : ""}">
        <div class="entity-item-row" data-toggle-edit="${i}">
          <div class="entity-item-main">
            <span class="entity-item-label">${_escape(e.label || e.entity_id)}</span>
            <span class="entity-item-id">${_escape(e.entity_id)}</span>
          </div>
          ${this._entityPillHtml(t, group, e)}
          <span class="entity-item-chevron">›</span>
          <button class="icon-button" data-remove-entity="${i}" title="${t.removeEntityTitle}">✕</button>
        </div>
        ${
          expanded
            ? `<div class="entity-item-edit">
                 ${this._entityFieldsHtml(t, group, e, i)}
                 <div class="entity-item-edit-actions">
                   <button class="entity-done-btn" data-index="${i}">${t.done}</button>
                 </div>
               </div>`
            : ""
        }
      </div>
    `;
  }

  _entityAddFormHtml(t, group) {
    return `
      <div class="entity-item expanded entity-item-add">
        <div class="entity-item-edit">
          ${this._entityFieldsHtml(t, group, {}, "new")}
          <div class="entity-item-edit-actions">
            <button class="entity-add-cancel">${t.cancel}</button>
            <button class="entity-add-confirm">${t.addEntity}</button>
          </div>
        </div>
      </div>
    `;
  }

  _wireEntityList(box, panel, widget, group) {
    box.querySelectorAll("[data-toggle-edit]").forEach((row) => {
      row.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-remove-entity]")) return;
        const index = parseInt(row.dataset.toggleEdit, 10);
        this._entityEditIndex = this._entityEditIndex === index ? null : index;
        this._addingEntity = false;
        this._renderWidgetOptions(panel, widget);
      });
    });
    box.querySelectorAll(".entity-done-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._entityEditIndex = null;
        this._renderWidgetOptions(panel, widget);
      });
    });
    box.querySelectorAll("[data-remove-entity]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._entityEditIndex = null;
        this._removeEntity(panel.id, parseInt(btn.dataset.removeEntity, 10));
      });
    });

    box.querySelectorAll(".entity-field[data-index]").forEach((field) => {
      const index = field.dataset.index;
      if (index === "new") return; // handled by the add-form's confirm button instead
      const i = parseInt(index, 10);
      field.addEventListener("change", () => {
        const fieldName = field.dataset.field;
        if (fieldName === "entity_id") {
          const current = (panel.entities || [])[i];
          if (!field.value || (current && field.value === current.entity_id)) return;
          this._updateEntity(panel.id, i, { entity_id: field.value });
        } else if (fieldName === "label") {
          this._updateEntity(panel.id, i, { label: field.value });
        } else if (fieldName === "unit") {
          this._updateEntity(panel.id, i, { unit: field.value || null });
        } else if (fieldName === "weather") {
          this._updateEntity(panel.id, i, { type: field.checked ? "weather" : null });
        } else if (fieldName === "control") {
          this._updateEntity(panel.id, i, { type: field.value || null });
        } else if (fieldName === "min") {
          this._updateEntity(panel.id, i, { min_value: field.value === "" ? null : Number(field.value) });
        } else if (fieldName === "max") {
          this._updateEntity(panel.id, i, { max_value: field.value === "" ? null : Number(field.value) });
        }
      });
    });

    const addTrigger = box.querySelector("#entity-add-trigger");
    if (addTrigger) {
      addTrigger.addEventListener("click", () => {
        this._addingEntity = true;
        this._entityEditIndex = null;
        this._renderWidgetOptions(panel, widget);
      });
    }
    const addCancel = box.querySelector(".entity-add-cancel");
    if (addCancel) {
      addCancel.addEventListener("click", () => {
        this._addingEntity = false;
        this._renderWidgetOptions(panel, widget);
      });
    }
    const addControlSelect = box.querySelector('.entity-field[data-index="new"].entity-control-select');
    if (addControlSelect) {
      // Live-toggle, unlike existing rows: there's no saved entity yet to
      // trigger a re-render off of, so the min/max disabled state has to
      // be flipped directly here instead.
      addControlSelect.addEventListener("change", () => {
        const isSlider = addControlSelect.value === "slider";
        box.querySelector('.entity-min-input[data-index="new"]').disabled = !isSlider;
        box.querySelector('.entity-max-input[data-index="new"]').disabled = !isSlider;
      });
    }
    const addConfirm = box.querySelector(".entity-add-confirm");
    if (addConfirm) {
      addConfirm.addEventListener("click", () => {
        const field = (name) => box.querySelector(`.entity-field[data-index="new"][data-field="${name}"]`);
        const entityId = field("entity_id").value;
        if (!entityId) return;
        const label = field("label").value || entityId;
        const unit = field("unit").value || null;
        const entity = { entity_id: entityId, group, label, unit, type: null };
        if (group === "wetter") {
          entity.type = field("weather").checked ? "weather" : null;
        } else if (group === "aktoren") {
          entity.type = field("control").value || null;
          entity.min_value = field("min").value === "" ? null : Number(field("min").value);
          entity.max_value = field("max").value === "" ? null : Number(field("max").value);
        }
        this._addingEntity = false;
        this._addEntity(panel.id, entity);
      });
    }
  }
}

function _widgetPreviewContent(type) {
  switch (type) {
    case "clock":
      return '<span class="mock-text">88:88</span>';
    case "weather_current":
      return "☀️";
    case "power_gauge":
      return '<div class="mock-arc">⚡</div>';
    case "indoor_climate":
      return "🌡️ 💧";
    case "waste_next":
      return "🗑️";
    case "calendar_month":
      return '<div class="mock-grid">' + "<span></span>".repeat(10) + "</div>";
    case "value_tile":
      return "⚙️";
    case "switch_tile":
      return '<div class="mock-switch"></div>';
    default:
      return "";
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
