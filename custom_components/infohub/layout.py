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

from .const import DEFAULT_LANGUAGE, PROTOCOL_VERSION
from .widgets import GRID_COLS, GRID_ROWS, widget_label

# Which full_update data group each widget type reads from. "clock" has
# none - it renders local time, not HA state.
_TYPE_TO_GROUP = {
    "weather_current": "wetter",
    "power_gauge": "strom",
    "waste_next": "abfall",
    "indoor_climate": "raumklima",
    "calendar_month": "kalender",
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


def layout_from_panel(panel: dict[str, Any]) -> Layout:
    """Builds the wire-protocol Layout from a panel's stored widget list.

    There is still only ever one real screen ("overview") - a panel's
    `widgets` list *is* that screen's content. Each widget's data_source
    and display label are derived from its type via widgets.widget_label()/
    _TYPE_TO_GROUP, not stored per-instance, since those are inherent to
    the type, not something the user configures per widget. The display
    label is resolved to the panel's own `language` (see Layout).
    """
    language = panel.get("language") or DEFAULT_LANGUAGE
    widgets = tuple(
        Widget(
            id=w["id"],
            type=w["type"],
            pos=WidgetPosition(**w["pos"]),
            label=widget_label(w["type"], language),
            data_source=(
                {"group": _TYPE_TO_GROUP[w["type"]]} if w["type"] in _TYPE_TO_GROUP else {}
            ),
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
