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
# Generic widget: shows one entity the user picks (its "entity_id"
# option) from the shared "custom" entity group (const.GROUP_CUSTOM) -
# unlike the other types, which each read every entity of their own
# fixed group. Lets the widget gallery grow to "any HA entity" without
# a new hardcoded type/renderer per kind of information.
WIDGET_VALUE_TILE = "value_tile"

# Bilingual widget display names - keyed by wire language code ("de"/"en",
# see const.LANGUAGE_CHOICES). layout.py's layout_from_panel() resolves
# the right one per-panel and sends it as each widget's wire "label" -
# that's what display clients render as the card title, see
# widget_label() below. The sidebar panel's JS keeps its own matching
# copy (WIDGET_CATALOG.label) since there's no build step to share it.
WIDGET_LABELS: dict[str, dict[str, str]] = {
    WIDGET_CLOCK: {"de": "Uhr", "en": "Clock"},
    WIDGET_WEATHER_CURRENT: {"de": "Wetter", "en": "Weather"},
    WIDGET_POWER_GAUGE: {"de": "Strom", "en": "Power"},
    WIDGET_INDOOR_CLIMATE: {"de": "Raumklima", "en": "Indoor Climate"},
    WIDGET_WASTE_NEXT: {"de": "Abfall", "en": "Waste"},
    WIDGET_CALENDAR_MONTH: {"de": "Kalender", "en": "Calendar"},
    WIDGET_VALUE_TILE: {"de": "Info-Kachel", "en": "Info Tile"},
}

# default_size = (colspan, rowspan) in grid units, used when a widget is
# newly added without an explicit size. options: field name -> schema
# dict with at least "type" ("bool" | "number" | "select") and "default".
WIDGET_CATALOG: dict[str, dict[str, Any]] = {
    WIDGET_CLOCK: {
        "default_size": (7, 3),
        "options": {
            "format": {"type": "select", "choices": ["24h", "12h"], "default": "24h"},
            "show_seconds": {"type": "bool", "default": False},
        },
    },
    WIDGET_WEATHER_CURRENT: {
        "default_size": (7, 8),
        "options": {
            "show_scene": {"type": "bool", "default": True},
        },
    },
    WIDGET_POWER_GAUGE: {
        "default_size": (8, 6),
        "options": {
            "max_value": {"type": "number", "default": 5000},
        },
    },
    WIDGET_INDOOR_CLIMATE: {
        "default_size": (7, 5),
        "options": {},
    },
    WIDGET_WASTE_NEXT: {
        "default_size": (8, 8),
        "options": {},
    },
    WIDGET_CALENDAR_MONTH: {
        "default_size": (9, 14),
        "options": {
            "months_shown": {"type": "number", "default": 2, "min": 1, "max": 2},
        },
    },
    WIDGET_VALUE_TILE: {
        "default_size": (7, 6),
        # No per-instance entity selection - it just shows every entity
        # currently in the panel's GROUP_CUSTOM list, one per row (see
        # layout.py's data_source and the client's update_custom()).
        # Picking a subset is what the entity table itself is for.
        "options": {},
    },
}


def widget_label(widget_type: str, language: str) -> str:
    """Bilingual display name for a widget type, e.g. for the wire label."""
    labels = WIDGET_LABELS.get(widget_type, {})
    return labels.get(language) or labels.get("en") or widget_type


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
