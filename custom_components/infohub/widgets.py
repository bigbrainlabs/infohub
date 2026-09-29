"""Widget catalog for InfoHub panels.

Describes every widget type a panel's widget list can contain: its
display label, a sensible default size (grid units) for "add widget",
and its options schema - used both to seed DEFAULT_WIDGETS for a
freshly created panel and by the sidebar panel's frontend to build the
per-widget options form (panel/infohub-panel.js keeps a matching copy
of this catalog in JS, since there's no build step to share it directly).

Grid: 24 columns x 14 rows, 80x80px cells, covering the display's
content area below its 80px header (24*80=1920, 14*80=1120=1200-80).
See layout.py's layout_from_panel() for how a panel's widget list
becomes the wire-protocol Layout.
"""

from __future__ import annotations

from typing import Any

GRID_COLS = 24
GRID_ROWS = 14

WIDGET_CLOCK = "clock"
WIDGET_WEATHER_CURRENT = "weather_current"
WIDGET_POWER_GAUGE = "power_gauge"
WIDGET_WASTE_NEXT = "waste_next"
WIDGET_INDOOR_CLIMATE = "indoor_climate"
WIDGET_CALENDAR_MONTH = "calendar_month"

# default_size = (colspan, rowspan) in grid units, used when a widget is
# newly added without an explicit size. options: field name -> schema
# dict with at least "type" ("bool" | "number" | "select") and "default".
WIDGET_CATALOG: dict[str, dict[str, Any]] = {
    WIDGET_CLOCK: {
        "label": "Uhr",
        "default_size": (7, 3),
        "options": {
            "format": {"type": "select", "choices": ["24h", "12h"], "default": "24h"},
            "show_seconds": {"type": "bool", "default": False},
        },
    },
    WIDGET_WEATHER_CURRENT: {
        "label": "Wetter",
        "default_size": (7, 8),
        "options": {
            "show_scene": {"type": "bool", "default": True},
        },
    },
    WIDGET_POWER_GAUGE: {
        "label": "Strom",
        "default_size": (8, 6),
        "options": {
            "max_value": {"type": "number", "default": 5000},
        },
    },
    WIDGET_INDOOR_CLIMATE: {
        "label": "Raumklima",
        "default_size": (7, 5),
        "options": {},
    },
    WIDGET_WASTE_NEXT: {
        "label": "Abfall",
        "default_size": (8, 8),
        "options": {},
    },
    WIDGET_CALENDAR_MONTH: {
        "label": "Kalender",
        "default_size": (9, 14),
        "options": {
            "months_shown": {"type": "number", "default": 2, "min": 1, "max": 2},
        },
    },
}


def default_options(widget_type: str) -> dict[str, Any]:
    """Returns the default options dict for a widget type."""
    schema = WIDGET_CATALOG.get(widget_type, {}).get("options", {})
    return {name: field["default"] for name, field in schema.items()}


def _widget(
    widget_id: str,
    widget_type: str,
    col: int,
    row: int,
    colspan: int | None = None,
    rowspan: int | None = None,
    **options: Any,
) -> dict[str, Any]:
    default_colspan, default_rowspan = WIDGET_CATALOG[widget_type]["default_size"]
    merged_options = default_options(widget_type)
    merged_options.update(options)
    return {
        "id": widget_id,
        "type": widget_type,
        "pos": {
            "col": col,
            "row": row,
            "colspan": colspan if colspan is not None else default_colspan,
            "rowspan": rowspan if rowspan is not None else default_rowspan,
        },
        "options": merged_options,
    }


# Rough re-creation of today's real 5-card dashboard (see
# architecture_reality_vs_docs) plus the newly-independent clock, on the
# new 24x14 grid - a starting point for a freshly created panel, not a
# pixel-exact reproduction (the whole point of this step is that the
# user can now drag it to taste). Left column (clock+weather+raumklima)
# rows sum to 14 (3+6+5), right column (strom+abfall) rows sum to 14
# (6+8), middle column (calendar) spans the full 14 rows - no overlaps.
DEFAULT_WIDGETS: list[dict[str, Any]] = [
    _widget("clock_1", WIDGET_CLOCK, col=0, row=0),
    _widget("weather_1", WIDGET_WEATHER_CURRENT, col=0, row=3, rowspan=6),
    _widget("raumklima_1", WIDGET_INDOOR_CLIMATE, col=0, row=9),
    _widget("calendar_1", WIDGET_CALENDAR_MONTH, col=7, row=0),
    _widget("strom_1", WIDGET_POWER_GAUGE, col=16, row=0),
    _widget("abfall_1", WIDGET_WASTE_NEXT, col=16, row=6),
]
