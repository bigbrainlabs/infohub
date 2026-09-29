"""Layout protocol for InfoHub display clients.

Defines the grid-based screen/widget layout that the integration sends to
display clients as a `layout_update` websocket message, kept strictly
separate from the live data (`full_update` / `entity_update`) messages.
Clients cache the layout and only re-render structure when it changes;
data flows independently and fills the widgets the layout describes.

This module is intentionally free of any Home Assistant imports so it can
be built and inspected (e.g. `Layout.as_message()`) without a running HA
instance. The layout is now built entirely from a panel's stored widget
list (see panels.py) via layout_from_panel() - there is no more
hardcoded default layout here; that lives as widgets.DEFAULT_WIDGETS,
the seed for a freshly created panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .const import DEFAULT_LANGUAGE, GROUP_CUSTOM, PROTOCOL_VERSION
from .widgets import GRID_COLS, GRID_ROWS, WIDGET_VALUE_TILE, widget_label

# Which full_update data group each widget type reads from. "clock" has
# none - it renders local time, not HA state. "value_tile" also reads
# GROUP_CUSTOM, but unlike the others needs a specific entity_id within
# it too - see layout_from_panel().
_TYPE_TO_GROUP = {
    "weather_current": "wetter",
    "power_gauge": "strom",
    "waste_next": "abfall",
    "indoor_climate": "raumklima",
    "calendar_month": "kalender",
    WIDGET_VALUE_TILE: GROUP_CUSTOM,
}

_SCREEN_LABELS = {"de": "Übersicht", "en": "Overview"}


@dataclass(frozen=True)
class WidgetPosition:
    """Grid position of a widget within its screen's grid."""

    col: int
    row: int
    colspan: int = 1
    rowspan: int = 1

    def as_dict(self) -> dict[str, int]:
        return {
            "col": self.col,
            "row": self.row,
            "colspan": self.colspan,
            "rowspan": self.rowspan,
        }


@dataclass(frozen=True)
class Widget:
    """A single widget placed on a screen.

    `data_source` binds the widget to a group (and optionally a specific
    entity_id within it) from the existing full_update data payload -
    e.g. {"group": "strom"}. `options` carries widget-specific extras
    (e.g. max_value for a gauge) that don't belong in live data.
    """

    id: str
    type: str
    pos: WidgetPosition
    label: str = ""
    data_source: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "pos": self.pos.as_dict(),
            "label": self.label,
            "data_source": self.data_source,
            "options": self.options,
        }


@dataclass(frozen=True)
class Screen:
    """A screen (page) made up of a grid of widgets."""

    id: str
    label: str
    icon: str
    grid_cols: int
    grid_rows: int
    widgets: tuple[Widget, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "icon": self.icon,
            "grid": {"cols": self.grid_cols, "rows": self.grid_rows},
            "widgets": [w.as_dict() for w in self.widgets],
        }


@dataclass(frozen=True)
class Navigation:
    """Navigation bar configuration - which screens, in which order."""

    order: tuple[str, ...]
    type: str = "tab_bar"

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type, "order": list(self.order)}


@dataclass(frozen=True)
class Layout:
    """Full layout: all screens plus navigation between them.

    `language` is the panel's display language ("de"/"en") - display
    clients use it to pick between their own built-in string tables for
    things the server doesn't send text for (weekday/month names,
    weather condition terms, etc.); everything the server *does* send
    text for (widget labels) is already localized before it gets here.
    """

    screens: tuple[Screen, ...]
    navigation: Navigation
    language: str = DEFAULT_LANGUAGE

    def as_dict(self) -> dict[str, Any]:
        return {
            "screens": [s.as_dict() for s in self.screens],
            "navigation": self.navigation.as_dict(),
            "language": self.language,
        }

    def as_message(self) -> dict[str, Any]:
        """Build the full `layout_update` websocket message."""
        return {
            "type": "layout_update",
            "protocol_version": PROTOCOL_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **self.as_dict(),
        }


def _widget_label(
    widget: dict[str, Any], entities_by_id: dict[str, dict[str, Any]], language: str
) -> str:
    """A widget's display label.

    A user-set `alias` (a plain field on the widget, like `pos` - not a
    type-specific "option") always wins if present. Otherwise: the bound
    entity's own label for value_tile (falling back to the generic type
    label until an entity is picked), or just the type's catalog label.
    """
    alias = (widget.get("alias") or "").strip()
    if alias:
        return alias
    if widget["type"] == WIDGET_VALUE_TILE:
        entity_id = widget.get("options", {}).get("entity_id")
        entity = entities_by_id.get(entity_id) if entity_id else None
        if entity and entity.get("label"):
            return entity["label"]
    return widget_label(widget["type"], language)


def _widget_data_source(widget: dict[str, Any]) -> dict[str, Any]:
    """A widget's data_source - value_tile also needs the specific
    entity_id its "entity_id" option names, not just the group."""
    group = _TYPE_TO_GROUP.get(widget["type"])
    if group is None:
        return {}
    if widget["type"] == WIDGET_VALUE_TILE:
        entity_id = widget.get("options", {}).get("entity_id")
        if not entity_id:
            return {}
        return {"group": group, "entity_id": entity_id}
    return {"group": group}


def layout_from_panel(panel: dict[str, Any]) -> Layout:
    """Builds the wire-protocol Layout from a panel's stored widget list.

    There is still only ever one real screen ("overview") - a panel's
    `widgets` list *is* that screen's content. Each widget's data_source
    and display label are derived from its type via widgets.widget_label()/
    _TYPE_TO_GROUP, not stored per-instance, since those are inherent to
    the type, not something the user configures per widget - except
    "value_tile" (see _widget_label()/_widget_data_source() below), which
    picks one specific entity out of the shared GROUP_CUSTOM pool via its
    own "entity_id" option, so both its label and data_source depend on
    that choice instead of just its type. The display label is resolved
    to the panel's own `language` (see Layout).
    """
    language = panel.get("language") or DEFAULT_LANGUAGE
    entities_by_id = {e["entity_id"]: e for e in panel.get("entities", [])}
    widgets = tuple(
        Widget(
            id=w["id"],
            type=w["type"],
            pos=WidgetPosition(**w["pos"]),
            label=_widget_label(w, entities_by_id, language),
            data_source=_widget_data_source(w),
            options=w.get("options", {}),
        )
        for w in panel.get("widgets", [])
    )
    screen = Screen(
        id="overview",
        label=_SCREEN_LABELS.get(language, _SCREEN_LABELS["en"]),
        icon="mdi:home",
        grid_cols=GRID_COLS,
        grid_rows=GRID_ROWS,
        widgets=widgets,
    )
    return Layout(
        screens=(screen,), navigation=Navigation(order=(screen.id,)), language=language
    )
