"""Config flow for the InfoHub integration.

Entity/layout management used to live here as options-flow steps; that's
now the job of the sidebar "InfoHub" panel (panels.py + panel/infohub-panel.js),
which manages Panel entries through Home Assistant's own collection
websocket API instead of a multi-step dialog. This options flow now only
covers integration-wide settings that aren't per-panel: the WebSocket
port, GTS, and which Google Calendar entity to read.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig, TextSelector

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
)


class InfoHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the (single-instance) setup of InfoHub."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="InfoHub", data=user_input)

        schema = vol.Schema({vol.Required(CONF_WS_PORT, default=DEFAULT_WS_PORT): int})
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> InfoHubOptionsFlow:
        return InfoHubOptionsFlow(config_entry)


class InfoHubOptionsFlow(config_entries.OptionsFlow):
    """Integration-wide settings: WebSocket port, GTS, Kalender.

    Panels (Entities/Screens je Display) werden ueber das Sidebar-Panel
    verwaltet, nicht hier - siehe panels.py.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # Newer HA core versions expose OptionsFlow.config_entry as a
        # read-only property set by the framework itself - assigning it
        # here raises AttributeError ("no setter").
        self._ws_port: int = config_entry.options.get(
            CONF_WS_PORT, config_entry.data.get(CONF_WS_PORT, DEFAULT_WS_PORT)
        )
        self._gts_plz: str = config_entry.options.get(CONF_GTS_PLZ, DEFAULT_GTS_PLZ)
        self._gts_country: str = config_entry.options.get(CONF_GTS_COUNTRY, DEFAULT_GTS_COUNTRY)
        self._gts_poll_interval: int = config_entry.options.get(
            CONF_GTS_POLL_INTERVAL, DEFAULT_GTS_POLL_INTERVAL
        )
        # CONF_CALENDAR_ENTITY_ID now stores a list (multiple calendars,
        # merged by the coordinator) - a lone leftover string from before
        # multi-select existed is read as a one-item list.
        raw_calendar = config_entry.options.get(CONF_CALENDAR_ENTITY_ID)
        self._calendar_entity_ids: list[str] = (
            raw_calendar if isinstance(raw_calendar, list) else ([raw_calendar] if raw_calendar else [])
        )
        self._calendar_poll_interval: int = config_entry.options.get(
            CONF_CALENDAR_POLL_INTERVAL, DEFAULT_CALENDAR_POLL_INTERVAL
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._ws_port = user_input[CONF_WS_PORT]
            self._gts_plz = user_input.get(CONF_GTS_PLZ) or ""
            self._gts_country = user_input[CONF_GTS_COUNTRY]
            self._gts_poll_interval = user_input[CONF_GTS_POLL_INTERVAL]
            self._calendar_entity_ids = user_input.get(CONF_CALENDAR_ENTITY_ID) or []
            self._calendar_poll_interval = user_input[CONF_CALENDAR_POLL_INTERVAL]
            return self.async_create_entry(
                title="",
                data={
                    CONF_WS_PORT: self._ws_port,
                    CONF_GTS_PLZ: self._gts_plz,
                    CONF_GTS_COUNTRY: self._gts_country,
                    CONF_GTS_POLL_INTERVAL: self._gts_poll_interval,
                    CONF_CALENDAR_ENTITY_ID: self._calendar_entity_ids,
                    CONF_CALENDAR_POLL_INTERVAL: self._calendar_poll_interval,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_WS_PORT, default=self._ws_port): int,
                vol.Optional(CONF_GTS_PLZ, default=self._gts_plz): TextSelector(),
                vol.Required(CONF_GTS_COUNTRY, default=self._gts_country): TextSelector(),
                vol.Required(CONF_GTS_POLL_INTERVAL, default=self._gts_poll_interval): int,
                vol.Optional(
                    CONF_CALENDAR_ENTITY_ID, default=self._calendar_entity_ids
                ): EntitySelector(EntitySelectorConfig(domain="calendar", multiple=True)),
                vol.Required(
                    CONF_CALENDAR_POLL_INTERVAL, default=self._calendar_poll_interval
                ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
