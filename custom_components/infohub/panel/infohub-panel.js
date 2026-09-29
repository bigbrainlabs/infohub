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
 */

const ENTITY_GROUPS = [
  { value: "wetter", label: "Wetter" },
  { value: "strom", label: "Strom" },
  { value: "abfall", label: "Abfall" },
  { value: "raumklima", label: "Raumklima" },
];

// Mirrors custom_components/infohub/widgets.py's WIDGET_CATALOG.
const WIDGET_CATALOG = {
  clock: {
    label: "Uhr",
    default_size: [7, 3],
    options: {
      format: { type: "select", choices: ["24h", "12h"], default: "24h" },
      show_seconds: { type: "bool", default: false },
    },
  },
  weather_current: {
    label: "Wetter",
    default_size: [7, 8],
    options: { show_scene: { type: "bool", default: true } },
  },
  power_gauge: {
    label: "Strom",
    default_size: [8, 6],
    options: { max_value: { type: "number", default: 5000 } },
  },
  indoor_climate: {
    label: "Raumklima",
    default_size: [7, 5],
    options: {},
  },
  waste_next: {
    label: "Abfall",
    default_size: [8, 8],
    options: {},
  },
  calendar_month: {
    label: "Kalender",
    default_size: [9, 14],
    options: { months_shown: { type: "number", default: 2, min: 1, max: 2 } },
  },
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
    this._hass = hass;
    if (!this._subscribed) {
      this._subscribed = true;
      this._subscribe();
    }
  }

  get hass() {
    return this._hass;
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
    const name = window.prompt("Name des neuen Panels:");
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
    if (!window.confirm("Panel wirklich löschen?")) return;
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

  async _loadKnownDevices() {
    try {
      return await this._call("infohub/devices/list");
    } catch (err) {
      console.error("InfoHub: Geraeteliste laden fehlgeschlagen", err);
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

  // -- Widgets (layout editor) ---------------------------------------------

  async _saveWidgets(panelId, widgets) {
    try {
      const updated = await this._call("infohub/panel/update", { panel_id: panelId, widgets });
      this._panels[updated.id] = updated;
      return updated;
    } catch (err) {
      // Ohne das hier waere ein fehlgeschlagenes Speichern unsichtbar -
      // das Widget saehe dann so aus, als waere der Drag "zurueckgesprungen".
      console.error("InfoHub: Speichern der Widgets fehlgeschlagen", err);
      window.alert("Speichern fehlgeschlagen: " + (err && err.message ? err.message : err));
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
        .entity-add-row {
          display: grid;
          grid-template-columns: 2fr 1fr 1fr 1fr auto auto;
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
            <button class="add-panel-btn" id="add-panel">+ Panel anlegen</button>
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
          <span class="name">${_escape(p.name)} ${p.is_default ? '<span class="badge">Standard</span>' : ""}</span>
          <button class="icon-button" data-delete="${p.id}" title="Löschen">✕</button>
        </div>`
        )
        .join("") || '<div class="hint">Noch keine Panels.</div>';

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
    const editor = this.querySelector("#panel-editor");
    if (!panel) {
      editor.innerHTML = '<div class="hint">Panel links auswählen oder anlegen.</div>';
      return;
    }

    const entities = panel.entities || [];
    editor.innerHTML = `
      <div style="display:flex; align-items:center; gap:16px; margin-bottom:16px; flex-wrap: wrap;">
        <input type="text" id="edit-name" value="${_escapeAttr(panel.name)}" />
        <label class="hint">
          <input type="checkbox" id="edit-default" ${panel.is_default ? "checked" : ""} />
          Standard-Panel (Fallback für nicht zugeordnete Displays)
        </label>
        <label class="hint">
          Zugeordnetes Display
          <select id="edit-device"><option value="">Lädt…</option></select>
        </label>
      </div>

      <h3>Widgets</h3>
      <div class="widget-palette" id="widget-palette"></div>
      <div id="grid-wrap"></div>
      <div id="widget-options"></div>

      <h3>Entities</h3>
      <table class="entity-table">
        <thead>
          <tr><th>Entity</th><th>Gruppe</th><th>Label</th><th>Einheit</th><th>Wetter</th><th></th></tr>
        </thead>
        <tbody id="entity-rows">
          ${entities
            .map(
              (e, i) => `
            <tr>
              <td>${_escape(e.entity_id)}</td>
              <td>${_escape(e.group)}</td>
              <td>${_escape(e.label || "")}</td>
              <td>${_escape(e.unit || "")}</td>
              <td>${e.type === "weather" ? "✓" : ""}</td>
              <td><button class="icon-button" data-remove="${i}">✕</button></td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
      <div class="entity-add-row">
        <ha-entity-picker id="new-entity-picker"></ha-entity-picker>
        <select id="new-entity-group">
          ${ENTITY_GROUPS.map((g) => `<option value="${g.value}">${g.label}</option>`).join("")}
        </select>
        <input type="text" id="new-entity-label" placeholder="Label" />
        <input type="text" id="new-entity-unit" placeholder="Einheit" />
        <label class="hint"><input type="checkbox" id="new-entity-weather" /> Wetter</label>
        <button id="new-entity-add">+ Hinzufügen</button>
      </div>
    `;

    const picker = editor.querySelector("#new-entity-picker");
    picker.hass = this._hass;

    editor.querySelector("#edit-name").addEventListener("change", (ev) => {
      this._renamePanel(panel.id, ev.target.value);
    });
    editor.querySelector("#edit-default").addEventListener("change", (ev) => {
      if (ev.target.checked) this._setDefaultPanel(panel.id);
    });
    this._populateDeviceSelect(panel);
    editor.querySelectorAll("[data-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._removeEntity(panel.id, parseInt(btn.dataset.remove, 10));
      });
    });
    editor.querySelector("#new-entity-add").addEventListener("click", () => {
      const entityId = picker.value;
      if (!entityId) return;
      const group = editor.querySelector("#new-entity-group").value;
      const label = editor.querySelector("#new-entity-label").value || entityId;
      const unit = editor.querySelector("#new-entity-unit").value || null;
      const isWeather = editor.querySelector("#new-entity-weather").checked;
      this._addEntity(panel.id, { entity_id: entityId, group, label, unit, type: isWeather ? "weather" : null });
    });

    const palette = editor.querySelector("#widget-palette");
    palette.innerHTML = Object.entries(WIDGET_CATALOG)
      .map(([type, cat]) => `<button data-add="${type}">+ ${_escape(cat.label)}</button>`)
      .join("");
    palette.querySelectorAll("[data-add]").forEach((btn) => {
      btn.addEventListener("click", () => this._addWidget(panel.id, btn.dataset.add));
    });

    this._renderWidgetEditor(panel);
  }

  async _populateDeviceSelect(panel) {
    const devices = await this._loadKnownDevices();
    // Der Editor kann inzwischen neu gerendert oder ein anderes Panel
    // ausgewaehlt worden sein - dann gibt es das Element nicht mehr
    // oder es gehoert nicht mehr zu diesem Panel.
    const select = this.querySelector("#edit-device");
    if (!select) return;

    if (!devices.length) {
      select.innerHTML = '<option value="">Noch kein Display verbunden</option>';
      return;
    }

    const options = [
      `<option value="">— kein festes Gerät (Standard-Panel) —</option>`,
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

    const widgets = panel.widgets || [];
    wrap.innerHTML = `<div class="grid-canvas" id="grid-canvas"></div>`;
    const canvas = wrap.querySelector("#grid-canvas");

    for (const widget of widgets) {
      const catalog = WIDGET_CATALOG[widget.type] || { label: widget.type };
      const el = document.createElement("div");
      el.className = "widget-box" + (widget.id === this._selectedWidgetId ? " selected" : "");
      el.style.left = widget.pos.col * CELL_PX + "px";
      el.style.top = widget.pos.row * CELL_PX + "px";
      el.style.width = widget.pos.colspan * CELL_PX + "px";
      el.style.height = widget.pos.rowspan * CELL_PX + "px";
      el.textContent = catalog.label;
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
    const box = this.querySelector("#widget-options");
    if (!box) return;
    if (!widget) {
      box.innerHTML = '<div class="hint">Widget anklicken, um Optionen zu bearbeiten.</div>';
      return;
    }
    const schema = (WIDGET_CATALOG[widget.type] || {}).options || {};
    const entries = Object.entries(schema);
    if (!entries.length) {
      box.innerHTML = `<div class="hint">${_escape(WIDGET_CATALOG[widget.type]?.label || widget.type)} hat keine Optionen.</div>`;
      return;
    }

    box.innerHTML = `
      <div class="hint">Optionen: ${_escape(WIDGET_CATALOG[widget.type]?.label || widget.type)}</div>
      <div class="options-form">
        ${entries
          .map(([name, field]) => {
            const value = widget.options ? widget.options[name] : undefined;
            const current = value === undefined ? field.default : value;
            if (field.type === "bool") {
              return `<label>${_escape(name)}<input type="checkbox" data-opt="${name}" data-opt-type="bool" ${current ? "checked" : ""} /></label>`;
            }
            if (field.type === "select") {
              return `<label>${_escape(name)}<select data-opt="${name}" data-opt-type="select">${(field.choices || [])
                .map((c) => `<option value="${_escapeAttr(c)}" ${c === current ? "selected" : ""}>${_escape(c)}</option>`)
                .join("")}</select></label>`;
            }
            return `<label>${_escape(name)}<input type="number" data-opt="${name}" data-opt-type="number" value="${_escapeAttr(current)}" ${
              field.min !== undefined ? `min="${field.min}"` : ""
            } ${field.max !== undefined ? `max="${field.max}"` : ""} /></label>`;
          })
          .join("")}
      </div>
    `;

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
