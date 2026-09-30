"""Constants for the InfoHub integration."""

DOMAIN = "infohub"

PROTOCOL_VERSION = 1

DEFAULT_WS_PORT = 8765
CONF_WS_PORT = "ws_port"
CONF_ENTITIES = "entities"

# GTS (Gruenlandtemperatursumme) - externe API (exotengaertner.de), kein
# hass.states. PLZ/Land werden ueber den Options-Flow konfiguriert; leere
# PLZ (Default) deaktiviert die Abfrage komplett, siehe coordinator.py.
CONF_GTS_PLZ = "gts_plz"
CONF_GTS_COUNTRY = "gts_country"
CONF_GTS_POLL_INTERVAL = "gts_poll_interval"
DEFAULT_GTS_PLZ = ""
DEFAULT_GTS_COUNTRY = "DE"
DEFAULT_GTS_POLL_INTERVAL = 3600
GTS_API_URL = "https://exotengaertner.de/wp-json/konfigurator/v1/gts"

# Kalender - Google-Kalender ueber HA's eigene Google-Kalender-Integration
# (calendar.*-Entity), abgefragt per calendar.get_events-Service. Ersetzt
# die verworfene CalDAV/Radicale-Anbindung des Standalone-Service.
CONF_CALENDAR_ENTITY_ID = "calendar_entity_id"
CONF_CALENDAR_POLL_INTERVAL = "calendar_poll_interval"
DEFAULT_CALENDAR_POLL_INTERVAL = 300

# Widget types/catalog now live in widgets.py (WIDGET_CATALOG) - that's
# also where the clock became its own widget type instead of being
# baked into calendar_month (see the panel-layout-editor implementation).

# Data groups referenced by data_source["group"] in the layout protocol -
# match the group keys used in full_update's `data` payload.
GROUP_WETTER = "wetter"
GROUP_STROM = "strom"
GROUP_ABFALL = "abfall"
GROUP_RAUMKLIMA = "raumklima"
GROUP_KALENDER = "kalender"
# Backing group for the generic "value_tile" widget type (widgets.py) -
# any entity added here can be picked, per value_tile instance, via that
# widget's own "entity_id" option. Unlike the other groups it isn't tied
# to one specific widget type 1:1; several value_tile widgets can share
# this same pool and each pick a different entity from it.
GROUP_CUSTOM = "custom"

# Per-panel display language - controls what's actually rendered on the
# physical display (widget titles, weekday/month names, weather terms in
# the client) for whichever device that panel is assigned to. Deliberately
# separate from the sidebar admin UI's own language, which just follows
# hass.language like any native HA panel - see panel/infohub-panel.js's
# module docstring. New panels default to "en" (publication default);
# panels that existed before this field was introduced are migrated to
# "de" once, in panels.async_setup_panel_collection(), to preserve their
# current real-world behavior.
LANGUAGE_CHOICES = ("de", "en")
DEFAULT_LANGUAGE = "en"
