"""Data coordinator for InfoHub - reads Home Assistant state directly.

Unlike the standalone infohub/ service (which polls HA's REST API from
outside every `poll_interval` seconds), this coordinator runs inside
Home Assistant and is push-based: it takes one initial snapshot from
hass.states, then reacts to `state_changed` events for the tracked
entities via async_track_state_change_event. No polling loop is needed
for HA-native sensors - matches manifest.json's `iot_class: local_push`.

Weather forecasts aren't part of state attributes on modern HA weather
entities (they come from the `weather.get_forecasts` service instead),
so the forecast is (re)fetched opportunistically whenever the weather
entity's own state changes - still fully event-driven, no timer.

GTS (Gruenlandtemperatursumme) and the calendar are the two exceptions
that *do* need a timer instead of an event:

- GTS comes from an external HTTP API (exotengaertner.de), not from
  hass.states. It's merged into the `wetter` group's weather-type entity
  as a "gts" field, mirroring how main_mp.py already reads it
  (data[entity_id]["gts"], see display-client/main_mp.py's
  update_weather_current()).
- The calendar comes from HA's native Google-Kalender integration via
  the `calendar.get_events` service - a calendar entity's *state* only
  ever holds the single next upcoming event, not a whole month, so
  there's no useful state_changed to react to for a month view. Replaces
  the dropped CalDAV/Radicale client; broadcasts the same
  {"events": [...]} shape under the "kalender" group that the old
  standalone service's CalDAV client used, for client-side compatibility.

Medications are out of scope entirely - see the implementation plan's
"Nicht enthalten" section.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import (
    DEFAULT_CALENDAR_POLL_INTERVAL,
    DEFAULT_GTS_COUNTRY,
    DEFAULT_GTS_POLL_INTERVAL,
    GROUP_AKTOREN,
    GROUP_KALENDER,
    GROUP_WETTER,
    GTS_API_URL,
)
from .entities import DEFAULT_ENTITY_GROUPS, EntityConfig, all_entity_ids, find_entity_config
from .websocket_server import InfoHubWebSocketServer

logger = logging.getLogger(__name__)


class InfoHubCoordinator:
    """Watches configured HA entities and pushes transformed updates to clients."""

    def __init__(
        self,
        hass: HomeAssistant,
        server: InfoHubWebSocketServer,
        entity_groups: dict[str, tuple[EntityConfig, ...]] = DEFAULT_ENTITY_GROUPS,
        gts_plz: str | None = None,
        gts_country: str = DEFAULT_GTS_COUNTRY,
        gts_poll_interval: int = DEFAULT_GTS_POLL_INTERVAL,
        calendar_entity_ids: list[str] | None = None,
        calendar_poll_interval: int = DEFAULT_CALENDAR_POLL_INTERVAL,
    ) -> None:
        self._hass = hass
        self._server = server
        self._entity_groups = entity_groups
        self._gts_plz = gts_plz
        self._gts_country = gts_country
        self._gts_poll_interval = gts_poll_interval
        self._gts_value: float | None = None
        # Multiple calendars are merged into one event list - see
        # _async_poll_calendar(). A single calendar is just the n=1 case.
        self._calendar_entity_ids = calendar_entity_ids or []
        self._calendar_poll_interval = calendar_poll_interval
        self._unsub_state_changes: list[callable] = []
        self._unsub_gts_timer: callable | None = None
        self._unsub_calendar_timer: callable | None = None

    async def async_start(self) -> None:
        """Sends an initial snapshot and starts listening for state changes."""
        await self._async_send_initial_snapshot()

        entity_ids = all_entity_ids(self._entity_groups)
        unsub = async_track_state_change_event(
            self._hass, entity_ids, self._handle_state_change
        )
        self._unsub_state_changes.append(unsub)
        logger.info("InfoHub-Coordinator aktiv, beobachtet %d Entities", len(entity_ids))

        if self._gts_plz:
            await self._async_poll_gts()
            self._unsub_gts_timer = async_track_time_interval(
                self._hass, self._async_poll_gts, timedelta(seconds=self._gts_poll_interval)
            )
            logger.info(
                "GTS-Abfrage aktiv: PLZ %s (%s), alle %ds",
                self._gts_plz, self._gts_country, self._gts_poll_interval,
            )

        if self._calendar_entity_ids:
            await self._async_poll_calendar()
            self._unsub_calendar_timer = async_track_time_interval(
                self._hass, self._async_poll_calendar,
                timedelta(seconds=self._calendar_poll_interval),
            )
            logger.info(
                "Kalender-Abfrage aktiv: %s, alle %ds",
                ", ".join(self._calendar_entity_ids), self._calendar_poll_interval,
            )

    def async_stop(self) -> None:
        """Stops listening for state changes and the GTS/calendar timers."""
        for unsub in self._unsub_state_changes:
            unsub()
        self._unsub_state_changes.clear()

        if self._unsub_gts_timer:
            self._unsub_gts_timer()
            self._unsub_gts_timer = None

        if self._unsub_calendar_timer:
            self._unsub_calendar_timer()
            self._unsub_calendar_timer = None

    async def async_apply_entities(
        self, entity_groups: dict[str, tuple[EntityConfig, ...]]
    ) -> None:
        """Live-swaps the tracked entities - no HA reload needed.

        Called whenever any panel changes (see panels.py): unsubscribes
        the old state_changed tracking, re-sends a fresh full snapshot,
        then re-subscribes for the new (union-of-all-panels) entity set.
        Layout distribution is a separate concern now, handled per
        connection by InfoHubWebSocketServer.refresh_layouts() - this
        coordinator only ever deals with data, not who sees which widgets.
        """
        for unsub in self._unsub_state_changes:
            unsub()
        self._unsub_state_changes.clear()

        self._entity_groups = entity_groups

        await self._async_send_initial_snapshot()

        entity_ids = all_entity_ids(self._entity_groups)
        unsub = async_track_state_change_event(
            self._hass, entity_ids, self._handle_state_change
        )
        self._unsub_state_changes.append(unsub)
        logger.info(
            "InfoHub-Panel gewechselt, beobachtet jetzt %d Entities", len(entity_ids)
        )

    async def _async_send_initial_snapshot(self) -> None:
        """Builds one full_update from the current state of all tracked entities."""
        data: dict[str, dict[str, Any]] = {}

        for entity_id in all_entity_ids(self._entity_groups):
            state = self._hass.states.get(entity_id)
            if state is None:
                logger.warning("Entity nicht gefunden: %s", entity_id)
                continue

            group, entity_config = find_entity_config(entity_id, self._entity_groups)
            transformed = await self._async_transform_state(state, entity_config, group)
            data.setdefault(group, {})[entity_id] = transformed

        await self._server.broadcast_full_update(data)

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Schedules the (async) transform+broadcast for one changed entity."""
        new_state = event.data["new_state"]
        if new_state is None:
            return

        found = find_entity_config(event.data["entity_id"], self._entity_groups)
        if found is None:
            return
        group, entity_config = found

        self._hass.async_create_task(
            self._async_broadcast_entity_change(group, new_state, entity_config)
        )

    async def _async_broadcast_entity_change(
        self, group: str, state: State, entity_config: EntityConfig
    ) -> None:
        transformed = await self._async_transform_state(state, entity_config, group)
        await self._server.broadcast_entity_update(group, state.entity_id, transformed)

    async def _async_transform_state(
        self, state: State, entity_config: EntityConfig, group: str | None = None
    ) -> dict[str, Any]:
        """Transforms a HA State into the InfoHub wire format (see websocket_server.py)."""
        transformed: dict[str, Any] = {
            "label": entity_config.label,
            "state": state.state,
        }
        if entity_config.unit:
            transformed["unit"] = entity_config.unit

        if group == GROUP_AKTOREN:
            # Which actuator control the client should render this row as -
            # see EntityConfig.type's docstring. "slider" additionally
            # needs a current value and range, derived per HA domain since
            # neither lives in a uniform place (state.state for
            # number/input_number, an attribute for light/cover).
            control = entity_config.type if entity_config.type in ("cover", "slider") else "toggle"
            transformed["control"] = control
            if control == "slider":
                domain = state.entity_id.split(".", 1)[0]
                value, attr_min, attr_max = _slider_value_and_range(domain, state)
                transformed["value"] = value
                transformed["min"] = (
                    entity_config.min_value if entity_config.min_value is not None else attr_min
                )
                transformed["max"] = (
                    entity_config.max_value if entity_config.max_value is not None else attr_max
                )

        if entity_config.type == "weather":
            transformed["attributes"] = dict(state.attributes)
            if self._gts_value is not None:
                transformed["gts"] = self._gts_value
            forecast = await self._async_get_forecast(state.entity_id)
            if forecast is not None:
                transformed["forecast"] = forecast
            elif "forecast" in state.attributes:
                transformed["forecast"] = state.attributes["forecast"]

        if "abfall" in entity_config.entity_id.lower() or "waste" in entity_config.entity_id.lower():
            attrs = state.attributes
            transformed["days_until"] = attrs.get("daysTo")
            date_keys = sorted(
                k for k in attrs
                if len(k) == 10 and k[4:5] == "-" and k[7:8] == "-" and k[0:4].isdigit()
            )
            if date_keys:
                transformed["next_date"] = date_keys[0]

        return transformed

    async def _async_get_forecast(self, entity_id: str) -> list | None:
        """Calls weather.get_forecasts, mirroring infohub/ha_client.py's get_forecast()."""
        try:
            response = await self._hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": entity_id, "type": "daily"},
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - service call can fail per weather integration
            logger.debug("Forecast-Abruf fehlgeschlagen fuer %s: %s", entity_id, err)
            return None

        if not response:
            return None
        return response.get(entity_id, {}).get("forecast")

    async def _async_poll_gts(self, now: Any = None) -> None:
        """Fetches the current GTS value and refreshes the weather entities with it.

        `now` is unused - async_track_time_interval passes the trigger time,
        but this also gets called once directly on startup without it.
        """
        session = async_get_clientsession(self._hass)
        url = f"{GTS_API_URL}?country={self._gts_country}&plz={self._gts_plz}&compact=1"

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    logger.error("GTS API Fehler: HTTP %s", response.status)
                    return
                data = await response.json()
        except aiohttp.ClientError as err:
            logger.error("GTS-Abruf fehlgeschlagen: %s", err)
            return
        except TimeoutError:
            logger.error("GTS-Abruf: Timeout")
            return

        gts_total = data.get("gts_total")
        if not isinstance(gts_total, (int, float)):
            return

        self._gts_value = round(gts_total, 1)
        logger.info("GTS-Update: %s (PLZ %s)", self._gts_value, self._gts_plz)
        await self._async_refresh_weather_entities()

    async def _async_refresh_weather_entities(self) -> None:
        """Re-broadcasts every weather-type entity so its "gts" field updates."""
        for entity_config in self._entity_groups.get(GROUP_WETTER, ()):
            if entity_config.type != "weather":
                continue
            state = self._hass.states.get(entity_config.entity_id)
            if state is None:
                continue
            transformed = await self._async_transform_state(state, entity_config, GROUP_WETTER)
            await self._server.broadcast_entity_update(
                GROUP_WETTER, entity_config.entity_id, transformed
            )

    async def _async_poll_calendar(self, now: Any = None) -> None:
        """Fetches this and next month's events via calendar.get_events and broadcasts them.

        `now` is unused - async_track_time_interval passes the trigger time,
        but this also gets called once directly on startup without it.
        One service call targets every configured calendar at once -
        calendar.get_events returns its response keyed by entity_id when
        targeting more than one, same shape as the single-calendar case
        just with more keys - and the merged result is sorted back into
        one chronological list, since multiple calendars' events don't
        arrive in a globally sorted order.
        """
        today = datetime.now()
        start = datetime(today.year, today.month, 1)
        month, year = today.month + 2, today.year
        if month > 12:
            month -= 12
            year += 1
        end = datetime(year, month, 1)

        try:
            response = await self._hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "entity_id": self._calendar_entity_ids,
                    "start_date_time": start.isoformat(),
                    "end_date_time": end.isoformat(),
                },
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - calendar platform can fail in many ways
            logger.error("Kalender-Abruf fehlgeschlagen: %s", err)
            return

        response = response or {}
        events = []
        for entity_id in self._calendar_entity_ids:
            raw_events = response.get(entity_id, {}).get("events", [])
            events.extend(e for e in (self._parse_event(raw) for raw in raw_events) if e is not None)
        events.sort(key=lambda e: e["start"])

        await self._server.broadcast_group_update(GROUP_KALENDER, {"events": events})
        logger.info("Kalender-Update: %d Events gesendet", len(events))

    def _parse_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Parses one calendar.get_events event into the InfoHub wire format."""
        start_raw = event.get("start")
        if start_raw is None:
            return None
        start_str, all_day = _normalize_event_datetime(start_raw)

        end_raw = event.get("end")
        end_str = _normalize_event_datetime(end_raw)[0] if end_raw is not None else start_str

        return {
            "summary": event.get("summary") or "Kein Titel",
            "start": start_str,
            "end": end_str,
            "all_day": all_day,
        }


def _slider_value_and_range(
    domain: str, state: State
) -> tuple[float | None, float | None, float | None]:
    """Reads a "slider" actuator's current value and default range for its
    HA domain - number/input_number expose min/max as state attributes
    natively, so those are read straight off the state; light (brightness)
    and cover (position) don't, so those default to a 0-100 percent range,
    overridable per-entity via EntityConfig.min_value/max_value.
    """
    attrs = state.attributes
    if domain in ("number", "input_number"):
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            value = None
        return value, attrs.get("min"), attrs.get("max")
    if domain == "light":
        brightness = attrs.get("brightness")
        value = round(brightness / 255 * 100) if brightness is not None else 0
        return value, 0, 100
    if domain == "cover":
        return attrs.get("current_position"), 0, 100
    return None, None, None


def _normalize_event_datetime(value: Any) -> tuple[str, bool]:
    """Normalizes a calendar.get_events start/end value to (iso_str, all_day).

    Handles both the flat ISO-string shape the service normally returns
    and a defensive fallback for a {"date": ...} / {"dateTime": ...}
    nested shape, in case a calendar platform returns the Google-API-style
    nested format instead.
    """
    if isinstance(value, dict):
        value = value.get("dateTime") or value.get("date") or ""
    value = str(value)
    return value, "T" not in value
