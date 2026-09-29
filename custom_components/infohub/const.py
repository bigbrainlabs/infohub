"""Constants for the InfoHub integration."""

DOMAIN = "infohub"

PROTOCOL_VERSION = 1

DEFAULT_WS_PORT = 8765
CONF_WS_PORT = "ws_port"
CONF_ENTITIES = "entities"

# GTS (Gruenlandtemperatursumme) - externe API (exotengaertner.de), kein
# hass.states. PLZ/Land werden ueber den Options-Flow konfiguriert; Default
# ist die PLZ aus der bisherigen config.yaml des Standalone-Service.
CONF_GTS_PLZ = "gts_plz"
CONF_GTS_COUNTRY = "gts_country"
CONF_GTS_POLL_INTERVAL = "gts_poll_interval"
DEFAULT_GTS_PLZ = "06774"
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

# Gruppen, die der Options-Flow beim manuellen Entity-Hinzufuegen zur
# Auswahl anbietet. "kalender" bewusst ausgeschlossen: Kalender-Events
# kommen spaeter ueber HA's calendar.get_events-Service, nicht als
# einzeln zugeordnete sensor.*-Entity wie die anderen Gruppen.
ENTITY_GROUP_CHOICES = (GROUP_WETTER, GROUP_STROM, GROUP_ABFALL, GROUP_RAUMKLIMA)
