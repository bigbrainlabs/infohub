"""Panel storage: user-managed "Panels" (per-display configs) for InfoHub.

A Panel bundles a name, which entities feed it, and its widget layout
(free-form grid position + per-widget options) - the per-display
configuration that used to live flat in the config entry's options.
Stored via Home Assistant's own collection helper
(homeassistant.helpers.collection.DictStorageCollection), the same
mechanism HA itself uses for "Helpers" (input_button, input_boolean,
...) and multiple Lovelace dashboards - not hand-rolled, and it comes
with websocket list/create/update/delete/subscribe commands for free via
DictStorageCollectionWebsocket (wired up in __init__.py).

Today every connecting display client is simply served the *default*
panel (get_default_panel()) - matching which physical display gets which
panel is deliberately not part of this step (see the implementation
plan's "Nicht enthalten" section).
"""

from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection
from homeassistant.helpers.storage import Store

from .const import CONF_ENTITIES, DOMAIN
from .entities import DEFAULT_ENTITY_GROUPS, entity_groups_as_list
from .widgets import DEFAULT_WIDGETS

logger = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}_panels"
STORAGE_VERSION = 1
WS_API_PREFIX = f"{DOMAIN}/panel"
WS_MODEL_NAME = "panel"

# Plain dicts (not vol.Schema) so they can be **-spread when
# DictStorageCollectionWebsocket builds the websocket-command schemas
# (see __init__.py) - matches how HA core's own collection-backed
# integrations (e.g. input_button) declare these.
#
# CREATE_FIELDS: missing optional fields get a sensible default, so a
# freshly created panel is always well-formed.
CREATE_FIELDS: dict = {
    vol.Required("name"): str,
    vol.Optional("is_default", default=False): bool,
    vol.Optional("entities", default=list): list,
    vol.Optional("widgets", default=list): list,
    vol.Optional("assigned_device_id", default=None): vol.Any(None, str),
}

# UPDATE_FIELDS: no defaults, so a field the frontend didn't send stays
# absent from the validated dict - _update_data() then merges only the
# fields that were actually sent, instead of clobbering the rest of the
# panel with defaults.
UPDATE_FIELDS: dict = {
    vol.Optional("name"): str,
    vol.Optional("is_default"): bool,
    vol.Optional("entities"): list,
    vol.Optional("widgets"): list,
    vol.Optional("assigned_device_id"): vol.Any(None, str),
}


class InfoHubPanelStorageCollection(collection.DictStorageCollection):
    """Storage collection of configured InfoHub panels (displays)."""

    CREATE_UPDATE_SCHEMA = vol.Schema(CREATE_FIELDS)

    async def _process_create_data(self, data: dict[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], self.CREATE_UPDATE_SCHEMA(data))

    @callback
    def _get_suggested_id(self, info: dict[str, Any]) -> str:
        return cast(str, info["name"])

    async def _update_data(
        self, item: dict[str, Any], update_data: dict[str, Any]
    ) -> dict[str, Any]:
        validated = vol.Schema(UPDATE_FIELDS)(update_data)
        return {**item, **validated}


def get_default_panel(panels: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Picks the panel display clients should get, or None if there are none.

    Prefers the panel flagged is_default; falls back to the first panel
    so the system still serves *something* if nobody has flagged one yet.
    """
    if not panels:
        return None
    for panel in panels:
        if panel.get("is_default"):
            return panel
    return panels[0]


def resolve_panel_id(panels: list[dict[str, Any]], device_id: str | None) -> str | None:
    """Finds which panel a connecting display client should get.

    Prefers the panel explicitly assigned to `device_id` (via the
    sidebar panel's device dropdown); falls back to the default panel
    for unidentified/unassigned devices (or clients too old to send a
    device_id at all).
    """
    if device_id:
        for panel in panels:
            if panel.get("assigned_device_id") == device_id:
                return panel["id"]
    default = get_default_panel(panels)
    return default["id"] if default else None


def union_panel_entities(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merges every panel's entity list into one, deduplicated by entity_id.

    The coordinator tracks this union - a single shared hass.states
    subscription/data stream - since every display currently gets the
    same data and only differs in which widgets (and thus which parts of
    that data) it actually shows. See the implementation plan's "Nicht
    enthalten" section for why per-panel data streams weren't built.
    """
    merged: dict[str, dict[str, Any]] = {}
    for panel in panels:
        for entity in panel.get("entities", []):
            merged[entity["entity_id"]] = entity
    return list(merged.values())


async def async_setup_panel_collection(
    hass: HomeAssistant, entry_options: dict[str, Any]
) -> InfoHubPanelStorageCollection:
    """Loads the panel collection, seeding/upgrading panels as needed.

    First run ever (no panels at all): creates one "Standard" panel from
    whatever the old options-flow-based entity list already had.
    Existing panels created before the "widgets" field existed (an
    earlier version of this integration) get DEFAULT_WIDGETS backfilled
    once, so they don't silently end up with an empty layout.
    """
    store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    panel_collection = InfoHubPanelStorageCollection(store, collection.IDManager())
    await panel_collection.async_load()

    existing = panel_collection.async_items()
    if not existing:
        seed_entities = entry_options.get(CONF_ENTITIES) or entity_groups_as_list(
            DEFAULT_ENTITY_GROUPS
        )
        await panel_collection.async_create_item(
            {
                "name": "Standard",
                "is_default": True,
                "entities": seed_entities,
                "widgets": DEFAULT_WIDGETS,
            }
        )
        logger.info("InfoHub: Standard-Panel aus bisherigen Optionen angelegt")
    else:
        for panel in existing:
            if not panel.get("widgets"):
                await panel_collection.async_update_item(
                    panel["id"], {"widgets": DEFAULT_WIDGETS}
                )
                logger.info(
                    "InfoHub: Panel '%s' auf neues Widget-Layout migriert", panel["name"]
                )

    return panel_collection
