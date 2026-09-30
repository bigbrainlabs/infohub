"""InfoHub - Home Assistant integration.

Hosts the layout protocol (layout.py), starts the display-client
WebSocket server, and runs the data coordinator (coordinator.py) that
reads hass.states and pushes live updates to connected clients.

Panels (panels.py + panel/infohub-panel.js) are managed via a sidebar
config panel, each with its own widget layout and optionally an
`assigned_device_id` - a connecting display client identifies itself
(`{"type": "hello", "device_id": ...}`) and InfoHubWebSocketServer
resolves that to a specific panel's layout (panels.resolve_panel_id()),
falling back to the default panel for unidentified/unassigned devices.
All panels still share one coordinator/data stream (see panels.py's
union_panel_entities() and the implementation plan's "Nicht enthalten"
section for why). Changing a panel takes effect live - no HA reload -
via InfoHubCoordinator.async_apply_entities() (data) and
InfoHubWebSocketServer.refresh_layouts() (layout).

Still open: Medikamente wurden komplett verworfen, kein Ersatz vorgesehen.
"""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection

from .const import (
    CONF_CALENDAR_ENTITY_ID,
    CONF_CALENDAR_POLL_INTERVAL,
    CONF_GTS_COUNTRY,
    CONF_GTS_PLZ,
    CONF_GTS_POLL_INTERVAL,
    CONF_WS_PORT,
    DEFAULT_CALENDAR_POLL_INTERVAL,
    DEFAULT_GTS_COUNTRY,
    DEFAULT_GTS_PLZ,
    DEFAULT_GTS_POLL_INTERVAL,
    DEFAULT_WS_PORT,
    DOMAIN,
    GROUP_AKTOREN,
)
from .coordinator import InfoHubCoordinator
from .entities import build_entity_groups
from .layout import layout_from_panel
from .panels import (
    CREATE_FIELDS,
    UPDATE_FIELDS,
    WS_API_PREFIX,
    WS_MODEL_NAME,
    async_setup_panel_collection,
    get_default_panel,
    resolve_panel_id,
    union_panel_entities,
)
from .websocket_server import InfoHubWebSocketServer

logger = logging.getLogger(__name__)

PANEL_URL_PATH = "infohub"
PANEL_JS_URL = "/api/infohub/panel.js"
PANEL_JS_FILE = Path(__file__).parent / "panel" / "infohub-panel.js"


def _build_layouts(panels: list[dict]) -> dict[str, object]:
    return {panel["id"]: layout_from_panel(panel) for panel in panels}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up InfoHub from a config entry."""
    port = entry.options.get(CONF_WS_PORT, entry.data.get(CONF_WS_PORT, DEFAULT_WS_PORT))

    panel_collection = await async_setup_panel_collection(hass, entry.options)
    panels = panel_collection.async_items()
    default_panel = get_default_panel(panels)
    default_panel_id = default_panel["id"] if default_panel else None
    entity_groups = build_entity_groups(union_panel_entities(panels))

    def _resolve_panel(device_id: str | None) -> str | None:
        # Frisch aus der Collection lesen statt eine Kopie einzufangen,
        # damit spaeter angelegte/geaenderte Zuordnungen sofort gelten.
        return resolve_panel_id(panel_collection.async_items(), device_id)

    async def _resolve_action(entity_id: str, command: str) -> None:
        # Allowlist: nur Entities, die jemand explizit zur "aktoren"-
        # Gruppe eines Panels hinzugefuegt hat, sind ueberhaupt schaltbar -
        # der WS-Server selbst hat keine Auth, das begrenzt zumindest den
        # Schaden (kein beliebiger Service-Call auf x-beliebige Entities).
        allowed_ids = {
            e["entity_id"]
            for e in union_panel_entities(panel_collection.async_items())
            if e.get("group") == GROUP_AKTOREN
        }
        if entity_id not in allowed_ids:
            logger.warning("Action fuer nicht freigegebene Entity ignoriert: %s", entity_id)
            return
        if command != "toggle":
            logger.warning("Unbekanntes Action-Kommando ignoriert: %s", command)
            return
        await hass.services.async_call(
            "homeassistant", "toggle", {"entity_id": entity_id}, blocking=False
        )

    server = InfoHubWebSocketServer(host="0.0.0.0", port=port)
    server.configure_panels(_build_layouts(panels), default_panel_id, _resolve_panel)
    server.configure_action_handler(_resolve_action)
    await server.start()

    coordinator = InfoHubCoordinator(
        hass,
        server,
        entity_groups=entity_groups,
        gts_plz=entry.options.get(CONF_GTS_PLZ, DEFAULT_GTS_PLZ),
        gts_country=entry.options.get(CONF_GTS_COUNTRY, DEFAULT_GTS_COUNTRY),
        gts_poll_interval=entry.options.get(CONF_GTS_POLL_INTERVAL, DEFAULT_GTS_POLL_INTERVAL),
        calendar_entity_id=entry.options.get(CONF_CALENDAR_ENTITY_ID) or None,
        calendar_poll_interval=entry.options.get(
            CONF_CALENDAR_POLL_INTERVAL, DEFAULT_CALENDAR_POLL_INTERVAL
        ),
    )
    await coordinator.async_start()

    async def _on_panels_changed(change_type: str, item_id: str, item: dict) -> None:
        """Re-applies layouts/entities for all panels, live.

        collection.notify_changes() awaits every registered listener via
        asyncio.gather() - it must be a coroutine function, not a plain
        @callback (that crashed with "An asyncio.Future, a coroutine or
        an awaitable is required" the moment a panel was actually edited).
        """
        current_panels = panel_collection.async_items()
        current_default = get_default_panel(current_panels)
        await server.refresh_layouts(
            _build_layouts(current_panels),
            current_default["id"] if current_default else None,
            _resolve_panel,
        )
        await coordinator.async_apply_entities(
            build_entity_groups(union_panel_entities(current_panels))
        )

    unsub_panels = panel_collection.async_add_listener(_on_panels_changed)

    collection.DictStorageCollectionWebsocket(
        panel_collection, WS_API_PREFIX, WS_MODEL_NAME, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    @websocket_api.websocket_command({vol.Required("type"): "infohub/devices/list"})
    @callback
    def _ws_list_devices(hass: HomeAssistant, connection, msg: dict) -> None:
        """Known device_ids (have sent a hello at least once) - for the panel's device dropdown."""
        connection.send_result(msg["id"], server.get_known_devices())

    websocket_api.async_register_command(hass, _ws_list_devices)

    # cache_headers=False, solange das Panel aktiv weiterentwickelt wird -
    # mit True setzt HA hier Cache-Control: max-age=31 Tage, dann sieht
    # der Browser Aenderungen erst nach explizitem Cache-Leeren.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(PANEL_JS_URL, str(PANEL_JS_FILE), False)]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name="infohub-panel",
        sidebar_title="InfoHub",
        sidebar_icon="mdi:monitor-dashboard",
        module_url=PANEL_JS_URL,
        require_admin=True,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "server": server,
        "coordinator": coordinator,
        "panel_collection": panel_collection,
        "unsub_panels": unsub_panels,
    }

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an InfoHub config entry."""
    entry_data = hass.data[DOMAIN].pop(entry.entry_id)
    entry_data["unsub_panels"]()
    entry_data["coordinator"].async_stop()
    await entry_data["server"].stop()
    async_remove_panel(hass, PANEL_URL_PATH)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reloads the entry so a changed WS-Port/GTS/Kalender-Einstellung greift.

    Panel-Aenderungen (Entities/Widgets/Geraete-Zuordnung) brauchen das
    nicht - die gehen live ueber async_apply_entities()/refresh_layouts().
    """
    await hass.config_entries.async_reload(entry.entry_id)
