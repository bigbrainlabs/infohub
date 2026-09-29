"""
InfoHub Display Client - MicroPython + LVGL
Verbindet sich mit InfoHub WebSocket und zeigt Daten auf dem Display an
"""

import lvgl as lv
import time
import json
import asyncio
import socket
import random

# Configuration
INFOHUB_HOST = "192.168.2.49"
INFOHUB_PORT = 8765
DISPLAY_WIDTH = 1920
DISPLAY_HEIGHT = 1200
HEADER_HEIGHT = 80

# Stabile Geraete-ID, mit der sich dieser Client beim Server meldet (siehe
# _ws_encode_frame()/"hello"-Nachricht) - der InfoHub-Sidebar-Panel kann
# darueber ein bestimmtes Panel-Layout genau diesem Geraet zuordnen.
# Nutzt den Hostnamen (z.B. "infopanel1"), mit hartcodiertem Fallback
# falls dieser MicroPython-Port kein os.uname() kennt.
try:
    import os
    DEVICE_ID = os.uname().nodename
except Exception:
    DEVICE_ID = "infopanel1"

# Theme colors
THEME = {
    "bg": 0x1a1a2e,
    "primary": 0x4a90d9,
    "secondary": 0x64748b,
    "text": 0xffffff,
    "text_secondary": 0x94a3b8,
    "success": 0x22c55e,
    "warning": 0xf59e0b,
    "error": 0xef4444,
    "card_bg": 0x2d2d44,
    "rain_blue": 0x5b9bd5,
}

# Display language ("de"/"en") - set from each layout_update's top-level
# "language" field (see apply_layout()), which mirrors the panel's own
# language setting (custom_components/infohub/panels.py). A module-level
# global rather than an instance attribute since several of the lookup
# functions below (_format_waste_date, _format_days_text, ...) are plain
# module functions with no `self`, and this script is single-threaded
# cooperative asyncio - no concurrency concern in reading/writing it.
# Default "de" matches this client's behavior before this field existed,
# so an old cached layout (or the brief window before the first
# layout_update arrives) still looks like it always did.
_LANGUAGE = "de"

# Condition translation map
CONDITION_MAP = {
    "de": {
        "sunny": "Sonnig",
        "clear-night": "Klare Nacht",
        "partlycloudy": "Teilw. bewoelkt",
        "cloudy": "Bewoelkt",
        "rainy": "Regen",
        "pouring": "Starkregen",
        "snowy": "Schnee",
        "snowy-rainy": "Schneeregen",
        "fog": "Nebel",
        "hail": "Hagel",
        "lightning": "Gewitter",
        "lightning-rainy": "Gewitter+Regen",
        "windy": "Windig",
        "windy-variant": "Windig",
        "exceptional": "Besonders",
    },
    "en": {
        "sunny": "Sunny",
        "clear-night": "Clear Night",
        "partlycloudy": "Partly Cloudy",
        "cloudy": "Cloudy",
        "rainy": "Rainy",
        "pouring": "Heavy Rain",
        "snowy": "Snowy",
        "snowy-rainy": "Sleet",
        "fog": "Fog",
        "hail": "Hail",
        "lightning": "Thunderstorm",
        "lightning-rainy": "Storm+Rain",
        "windy": "Windy",
        "windy-variant": "Windy",
        "exceptional": "Exceptional",
    },
}

# Day name map (0=Monday .. 6=Sunday)
DAY_NAMES = {
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
DAY_NAMES_FULL = {
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
           "Freitag", "Samstag", "Sonntag"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday",
           "Friday", "Saturday", "Sunday"],
}
MONTH_NAMES = {
    "de": ["Jan", "Feb", "Maer", "Apr", "Mai", "Jun",
           "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}
MONTH_NAMES_FULL = {
    "de": ["Januar", "Februar", "Maerz", "April", "Mai", "Juni",
           "Juli", "August", "September", "Oktober", "November", "Dezember"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
}

# Wind compass abbreviations - German uses O (Ost) where English uses E
# (East), so this isn't just a lookup-table-format nicety.
WIND_DIRS = {
    "de": ["N", "NO", "O", "SO", "S", "SW", "W", "NW"],
    "en": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
}

# Static UI text that isn't a lookup table - see _t().
STRINGS = {
    "de": {
        "connecting": "Verbinde...",
        "connected": "Verbunden",
        "disconnected": "Getrennt",
        "forecast": "Vorhersage",
        "no_forecast": "Keine Vorhersage verfuegbar",
        "clouds": "Wolken",
        "humidity_short": "Feuchte",
        "precipitation_short": "Nieders.",
        "wind": "Wind",
        "pressure": "Druck",
        "visibility": "Sicht",
        "comfort": "Komfort",
        "temperature": "Temperatur",
        "humidity": "Luftfeuchtigkeit",
        "current_power": "Aktuelle Leistung",
        "daily_consumption": "Tagesverbrauch",
        "power_price": "Strompreis",
        "monthly_cost": "Monatskosten",
        "all_dates": "Alle Termine",
        "next_appointments": "Naechste Termine",
        "appointments_on": "Termine am",
        "all_day": "Ganztaegig",
        "reminder": "Erinnerung",
        "now": "Jetzt!",
        "today": "Heute!",
        "tomorrow": "Morgen",
        "in_days": "Tagen",
        "in_minutes": "Minuten",
    },
    "en": {
        "connecting": "Connecting...",
        "connected": "Connected",
        "disconnected": "Disconnected",
        "forecast": "Forecast",
        "no_forecast": "No forecast available",
        "clouds": "Clouds",
        "humidity_short": "Humidity",
        "precipitation_short": "Precip.",
        "wind": "Wind",
        "pressure": "Pressure",
        "visibility": "Visibility",
        "comfort": "Comfort",
        "temperature": "Temperature",
        "humidity": "Humidity",
        "current_power": "Current Power",
        "daily_consumption": "Daily Usage",
        "power_price": "Power Price",
        "monthly_cost": "Monthly Cost",
        "all_dates": "All Dates",
        "next_appointments": "Upcoming",
        "appointments_on": "Events on",
        "all_day": "All day",
        "reminder": "Reminder",
        "now": "Now!",
        "today": "Today!",
        "tomorrow": "Tomorrow",
        "in_days": "days",
        "in_minutes": "minutes",
    },
}


def _t(key):
    """Looks up a static UI string in the current display language."""
    return STRINGS.get(_LANGUAGE, STRINGS["de"]).get(key, key)

# 7-Segment digit patterns: (a, b, c, d, e, f, g)
SEGMENTS = {
    0: (1, 1, 1, 1, 1, 1, 0),
    1: (0, 1, 1, 0, 0, 0, 0),
    2: (1, 1, 0, 1, 1, 0, 1),
    3: (1, 1, 1, 1, 0, 0, 1),
    4: (0, 1, 1, 0, 0, 1, 1),
    5: (1, 0, 1, 1, 0, 1, 1),
    6: (1, 0, 1, 1, 1, 1, 1),
    7: (1, 1, 1, 0, 0, 0, 0),
    8: (1, 1, 1, 1, 1, 1, 1),
    9: (1, 1, 1, 1, 0, 1, 1),
}

# Event accent colors (cycled)
EVENT_COLORS = [0x4a90d9, 0x22c55e, 0xf59e0b, 0xe879f9, 0xfb7185, 0x38bdf8, 0xa78bfa, 0x34d399]

# Waste type colors (echte deutsche Tonnen-Farben)
WASTE_COLORS = {
    "restmuell": 0x37474F,
    "bioabfall": 0x6D4C41,
    "altpapier": 0x1565C0,
    "gelber_sack": 0xF9A825,
}
WASTE_COLORS_LIGHT = {
    "restmuell": 0x546E7A,
    "bioabfall": 0x8D6E63,
    "altpapier": 0x1E88E5,
    "gelber_sack": 0xFDD835,
}

# Sky scene themes: (top_color, bottom_color, cloud_color)
SKY_THEMES = {
    "sunny":           (0x87CEEB, 0x4682B4, 0xD4D4D4),
    "clear-night":     (0x0a0a20, 0x15102a, 0x303050),
    "partlycloudy":    (0x6CA6CD, 0x4A7A9B, 0xC8C8D0),
    "cloudy":          (0x808890, 0x606870, 0x909098),
    "rainy":           (0x505860, 0x404850, 0x707880),
    "pouring":         (0x404850, 0x303840, 0x606870),
    "snowy":           (0x7888A0, 0x5868A0, 0xB0B8C8),
    "snowy-rainy":     (0x607080, 0x506070, 0x909AA8),
    "fog":             (0x808890, 0x707880, 0x989898),
    "lightning":       (0x404050, 0x303040, 0x606068),
    "lightning-rainy": (0x383848, 0x282838, 0x585860),
    "windy":           (0x6090B0, 0x4070A0, 0xA8B0C0),
    "windy-variant":   (0x6090B0, 0x4070A0, 0xA8B0C0),
    "hail":            (0x506070, 0x405060, 0x808890),
    "exceptional":     (0x808890, 0x606870, 0x909098),
}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _zfill(s, n):
    """Zero-fill a string to n characters."""
    s = str(s)
    while len(s) < n:
        s = "0" + s
    return s


def _translate_condition(condition):
    """Translate HA weather condition to the current display language."""
    table = CONDITION_MAP.get(_LANGUAGE, CONDITION_MAP["de"])
    return table.get(condition, str(condition))


def _fmt1(v):
    """Format a numeric value to max 1 decimal place (integer math)."""
    try:
        f = float(v)
        neg = f < 0
        a = abs(f)
        r = int(round(a * 10))
        whole = r // 10
        frac = r % 10
        s = str(whole) if frac == 0 else str(whole) + "." + str(frac)
        return "-" + s if neg and r > 0 else s
    except (TypeError, ValueError):
        return str(v)


def _bearing_to_compass(bearing):
    """Convert wind bearing (degrees) to compass direction."""
    if bearing is None:
        return ""
    try:
        bearing = float(bearing)
    except (TypeError, ValueError):
        return ""
    dirs = WIND_DIRS.get(_LANGUAGE, WIND_DIRS["de"])
    idx = int((bearing + 22.5) / 45) % 8
    return dirs[idx]


def _get_day_name(date_str):
    """Extract short day name from ISO date string."""
    try:
        date_part = date_str.split("T")[0]
        parts = date_part.split("-")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        t = time.mktime((year, month, day, 0, 0, 0, 0, 0, -1))
        lt = time.localtime(t)
        return DAY_NAMES.get(_LANGUAGE, DAY_NAMES["de"])[lt[6]]
    except Exception:
        return "?"


def _detect_waste_type(entity_id):
    """Detect waste type from entity_id."""
    eid = entity_id.lower()
    if "restm" in eid:
        return "restmuell"
    if "bio" in eid:
        return "bioabfall"
    if "papier" in eid:
        return "altpapier"
    if "gelb" in eid:
        return "gelber_sack"
    return "restmuell"


def _format_waste_date(date_str):
    """Format '2026-02-11' to 'Di, 11. Feb'."""
    try:
        parts = date_str.split("-")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        t = time.mktime((year, month, day, 0, 0, 0, 0, 0, -1))
        lt = time.localtime(t)
        day_name = DAY_NAMES.get(_LANGUAGE, DAY_NAMES["de"])[lt[6]]
        month_name = MONTH_NAMES.get(_LANGUAGE, MONTH_NAMES["de"])[month - 1]
        return day_name + ", " + str(day) + ". " + month_name
    except Exception:
        return str(date_str)


def _safe_text(text):
    """Replace German umlauts for LVGL Montserrat font."""
    t = str(text)
    for old, new in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                     ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue")]:
        t = t.replace(old, new)
    return t


def _estimate_gts_200(current_gts, forecast):
    """Estimate when GTS >= 200 will be reached using forecast data."""
    if current_gts is None or current_gts >= 200:
        return ""
    if not forecast or len(forecast) < 2:
        return "--"

    now = time.localtime()
    year = now[0]
    month = now[1]
    day = now[2]

    # Calculate daily GTS contributions from forecast
    fc_beitraege = []
    for fc in forecast[1:6]:
        t_hi = fc.get("temperature")
        t_lo = fc.get("templow")
        if t_hi is None or t_lo is None:
            continue
        t_avg = (float(t_hi) + float(t_lo)) / 2.0
        fc_date = fc.get("datetime", "")
        fc_month = month
        if len(fc_date) >= 7:
            try:
                fc_month = int(fc_date[5:7])
            except:
                pass
        if fc_month == 1:
            faktor = 0.5
        elif fc_month == 2:
            faktor = 0.75
        else:
            faktor = 1.0
        beitrag = max(0, t_avg) * faktor
        fc_beitraege.append(beitrag)

    if not fc_beitraege:
        return "--"

    avg_beitrag = sum(fc_beitraege) / len(fc_beitraege)
    if avg_beitrag <= 0:
        return "--"

    # Simulate day by day
    gts = float(current_gts)
    sim_day = day
    sim_month = month
    sim_year = year
    days_in = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if sim_year % 4 == 0:
        days_in[1] = 29

    for i in range(365):
        if i < len(fc_beitraege):
            gts += fc_beitraege[i]
        else:
            gts += avg_beitrag
        sim_day += 1
        if sim_day > days_in[sim_month - 1]:
            sim_day = 1
            sim_month += 1
            if sim_month > 12:
                sim_month = 1
                sim_year += 1
        if gts >= 200:
            month_names = MONTH_NAMES.get(_LANGUAGE, MONTH_NAMES["de"])
            return "~" + str(sim_day) + ". " + month_names[sim_month - 1]

    return "--"


def _format_days_text(days):
    """Format days until collection in the current display language."""
    if days is None:
        return "--"
    if days == 0:
        return _t("today")
    if days == 1:
        return _t("tomorrow")
    return "in " + str(days) + " " + _t("in_days")


def _days_in_month(year, month):
    """Return number of days in the given month."""
    if month == 12:
        nm, ny = 1, year + 1
    else:
        nm, ny = month + 1, year
    t = time.mktime((ny, nm, 1, 0, 0, 0, 0, 0, -1))
    return time.localtime(t - 86400)[2]


def _weekday_of_first(year, month):
    """Return weekday of first day of month (0=Monday)."""
    t = time.mktime((year, month, 1, 0, 0, 0, 0, 0, -1))
    return time.localtime(t)[6]


def _moon_phase(year, month, day):
    """Return moon phase 0-1 (0=new, 0.5=full) using synodic month."""
    import math
    # Julian day number
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    # Reference new moon: 6 Jan 2000 18:14 UTC = JDN 2451550.26
    days_since = jdn - 2451550.26
    phase = (days_since % 29.53059) / 29.53059
    return phase


def _darken_color(color, factor=0.4):
    """Darken an RGB color and add slight blue shift for night."""
    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    r = int(r * factor)
    g = int(g * factor)
    b = min(255, int(b * factor + 20))
    return (r << 16) | (g << 8) | b


# ---------------------------------------------------------------------------
# Programmatic Weather Icons
# ---------------------------------------------------------------------------

def _draw_circle(parent, cx, cy, r, color):
    """Draw a filled circle using a rounded lv.obj."""
    c = lv.obj(parent)
    c.set_size(r * 2, r * 2)
    c.set_pos(cx - r, cy - r)
    c.set_style_bg_color(lv.color_hex(color), 0)
    c.set_style_bg_opa(255, 0)
    c.set_style_radius(r, 0)
    c.set_style_border_width(0, 0)
    c.remove_flag(lv.obj.FLAG.CLICKABLE)
    c.remove_flag(lv.obj.FLAG.SCROLLABLE)
    return c


def _draw_line(parent, points, color, width=2):
    """Draw a line given list of (x,y) tuples."""
    line = lv.line(parent)
    p_arr = []
    for px, py in points:
        p = lv.point_precise_t()
        p.x = px
        p.y = py
        p_arr.append(p)
    line.set_points(p_arr, len(p_arr))
    line.set_style_line_color(lv.color_hex(color), 0)
    line.set_style_line_width(width, 0)
    line.set_style_line_rounded(True, 0)
    line.remove_flag(lv.obj.FLAG.CLICKABLE)
    return line


def _draw_cloud(parent, cx, cy, s, color=0xc8c8d0):
    """Draw a cloud shape from overlapping circles."""
    r1 = int(18 * s)
    r2 = int(14 * s)
    r3 = int(12 * s)
    _draw_circle(parent, cx, cy, r1, color)
    _draw_circle(parent, cx - int(16 * s), cy + int(4 * s), r2, color)
    _draw_circle(parent, cx + int(16 * s), cy + int(4 * s), r2, color)
    _draw_circle(parent, cx - int(8 * s), cy - int(10 * s), r3, color)
    _draw_circle(parent, cx + int(8 * s), cy - int(8 * s), r3, color)
    rect = lv.obj(parent)
    rect.set_size(int(48 * s), int(16 * s))
    rect.set_pos(cx - int(24 * s), cy)
    rect.set_style_bg_color(lv.color_hex(color), 0)
    rect.set_style_bg_opa(255, 0)
    rect.set_style_border_width(0, 0)
    rect.set_style_radius(int(4 * s), 0)
    rect.remove_flag(lv.obj.FLAG.CLICKABLE)
    rect.remove_flag(lv.obj.FLAG.SCROLLABLE)


def _draw_rain_drops(parent, cx, cy, count, s, color=0x5b9bd5):
    """Draw rain drop lines below a cloud."""
    spacing = int(14 * s)
    start_x = cx - (count - 1) * spacing // 2
    for i in range(count):
        x = start_x + i * spacing
        _draw_line(parent,
                   [(x, cy), (x - int(4 * s), cy + int(14 * s))],
                   color, max(2, int(2 * s)))


def _draw_snow_dots(parent, cx, cy, count, s):
    """Draw snow dots below a cloud."""
    spacing = int(14 * s)
    start_x = cx - (count - 1) * spacing // 2
    for i in range(count):
        x = start_x + i * spacing
        y_off = int(4 * s) if i % 2 == 0 else 0
        _draw_circle(parent, x, cy + y_off, max(2, int(3 * s)), 0xffffff)


def _draw_sun(parent, cx, cy, r, s):
    """Draw sun: yellow circle + rays."""
    _draw_circle(parent, cx, cy, r, 0xffd700)
    ray_len = int(12 * s)
    ray_start = r + int(4 * s)
    import math
    for i in range(8):
        angle = i * math.pi / 4
        x1 = cx + int(ray_start * math.cos(angle))
        y1 = cy + int(ray_start * math.sin(angle))
        x2 = cx + int((ray_start + ray_len) * math.cos(angle))
        y2 = cy + int((ray_start + ray_len) * math.sin(angle))
        _draw_line(parent, [(x1, y1), (x2, y2)], 0xffd700, max(2, int(3 * s)))


def _draw_bolt(parent, cx, cy, s, color=0xffd700):
    """Draw a lightning bolt zigzag."""
    _draw_line(parent, [
        (cx, cy),
        (cx - int(6 * s), cy + int(10 * s)),
        (cx + int(4 * s), cy + int(12 * s)),
        (cx - int(2 * s), cy + int(22 * s)),
    ], color, max(2, int(3 * s)))


def _draw_power_bolt(parent, cx, cy, s):
    """Draw a power bolt icon with glow effect for the Strom card."""
    glow_r = int(30 * s)
    glow = lv.obj(parent)
    glow.set_size(glow_r * 2, glow_r * 2)
    glow.set_pos(cx - glow_r, cy - glow_r)
    glow.set_style_bg_color(lv.color_hex(0xffd700), 0)
    glow.set_style_bg_opa(40, 0)
    glow.set_style_radius(glow_r, 0)
    glow.set_style_border_width(0, 0)
    glow.remove_flag(lv.obj.FLAG.CLICKABLE)
    glow.remove_flag(lv.obj.FLAG.SCROLLABLE)
    bolt_pts1 = [
        (cx + int(2 * s), cy - int(18 * s)),
        (cx - int(6 * s), cy - int(2 * s)),
        (cx + int(4 * s), cy + int(2 * s)),
        (cx - int(2 * s), cy + int(18 * s)),
    ]
    _draw_line(parent, bolt_pts1, 0xffd700, max(3, int(4 * s)))
    bolt_pts2 = [
        (cx + int(4 * s), cy - int(18 * s)),
        (cx - int(4 * s), cy - int(2 * s)),
        (cx + int(6 * s), cy + int(2 * s)),
        (cx, cy + int(18 * s)),
    ]
    _draw_line(parent, bolt_pts2, 0xffd700, max(3, int(4 * s)))


def draw_weather_icon(parent, condition, size):
    """Draw a programmatic weather icon into parent."""
    container = lv.obj(parent)
    container.set_size(size, size)
    container.set_style_bg_opa(0, 0)
    container.set_style_border_width(0, 0)
    container.set_style_pad_all(0, 0)
    container.remove_flag(lv.obj.FLAG.CLICKABLE)
    container.remove_flag(lv.obj.FLAG.SCROLLABLE)

    s = size / 120.0
    cx = size // 2
    cy = size // 2

    if condition == "sunny":
        _draw_sun(container, cx, cy, int(20 * s), s)
    elif condition == "clear-night":
        _draw_circle(container, cx, cy, int(22 * s), 0xffd700)
        _draw_circle(container, cx + int(10 * s), cy - int(8 * s), int(18 * s), 0x050510)
    elif condition == "partlycloudy":
        _draw_sun(container, cx + int(18 * s), cy - int(15 * s), int(12 * s), s * 0.7)
        _draw_cloud(container, cx - int(5 * s), cy + int(8 * s), s * 0.9)
    elif condition == "cloudy":
        _draw_cloud(container, cx - int(8 * s), cy - int(6 * s), s * 0.8, 0xa0a0b0)
        _draw_cloud(container, cx + int(8 * s), cy + int(6 * s), s * 0.9)
    elif condition == "rainy":
        _draw_cloud(container, cx, cy - int(8 * s), s * 0.9)
        _draw_rain_drops(container, cx, cy + int(16 * s), 3, s)
    elif condition == "pouring":
        _draw_cloud(container, cx, cy - int(8 * s), s * 0.9)
        _draw_rain_drops(container, cx, cy + int(16 * s), 5, s)
    elif condition in ("snowy", "snowy-rainy"):
        _draw_cloud(container, cx, cy - int(8 * s), s * 0.9)
        _draw_snow_dots(container, cx, cy + int(18 * s), 5, s)
    elif condition == "fog":
        for i in range(4):
            y = cy - int(12 * s) + i * int(10 * s)
            w = int((50 - i * 5) * s)
            _draw_line(container,
                       [(cx - w // 2, y), (cx + w // 2, y)],
                       0x9098a8, max(3, int(4 * s)))
    elif condition == "lightning":
        _draw_cloud(container, cx, cy - int(10 * s), s * 0.9, 0x808090)
        _draw_bolt(container, cx, cy + int(6 * s), s)
    elif condition == "lightning-rainy":
        _draw_cloud(container, cx, cy - int(10 * s), s * 0.9, 0x808090)
        _draw_bolt(container, cx + int(8 * s), cy + int(6 * s), s * 0.8)
        _draw_rain_drops(container, cx - int(8 * s), cy + int(16 * s), 2, s * 0.7)
    elif condition in ("windy", "windy-variant"):
        for i in range(3):
            y = cy - int(14 * s) + i * int(14 * s)
            w = int((40 - i * 6) * s)
            _draw_line(container,
                       [(cx - w // 2, y), (cx + w // 2, y + int(3 * s)),
                        (cx + w // 2 + int(6 * s), y)],
                       0xb0b8c8, max(2, int(3 * s)))
    elif condition == "hail":
        _draw_cloud(container, cx, cy - int(8 * s), s * 0.9)
        spacing = int(12 * s)
        for i in range(4):
            x = cx - int(18 * s) + i * spacing
            _draw_circle(container, x, cy + int(20 * s), max(2, int(4 * s)), 0xd0e0f0)
    else:
        lbl = lv.label(container)
        lbl.set_text("?")
        lbl.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        lbl.set_style_text_font(lv.font_montserrat_24, 0)
        lbl.align(lv.ALIGN.CENTER, 0, 0)

    return container


# ---------------------------------------------------------------------------
# Programmatic Waste Icons
# ---------------------------------------------------------------------------

def _draw_rect(parent, x, y, w, h, color, radius=0, opa=255):
    """Draw a filled rectangle."""
    r = lv.obj(parent)
    r.set_size(w, h)
    r.set_pos(x, y)
    r.set_style_bg_color(lv.color_hex(color), 0)
    r.set_style_bg_opa(opa, 0)
    r.set_style_border_width(0, 0)
    r.set_style_radius(radius, 0)
    r.remove_flag(lv.obj.FLAG.CLICKABLE)
    r.remove_flag(lv.obj.FLAG.SCROLLABLE)
    return r


def _draw_muelltonne(parent, cx, cy, s, color, color_light):
    """Draw a realistic German Muelltonne (wheeled bin)."""
    bw = int(64 * s)
    bh = int(80 * s)
    bx = cx - bw // 2
    by = cy - bh // 2 + int(6 * s)
    _draw_rect(parent, bx, by, bw, bh, color, int(5 * s))
    pw = int(44 * s)
    ph = int(54 * s)
    _draw_rect(parent, cx - pw // 2, by + int(14 * s), pw, ph,
               color_light, int(3 * s))
    gw = int(34 * s)
    gh = max(2, int(3 * s))
    _draw_rect(parent, cx - gw // 2, by + int(34 * s), gw, gh,
               color, int(1 * s))
    lw = int(72 * s)
    lh = int(12 * s)
    lx = cx - lw // 2
    ly = by - lh + int(2 * s)
    _draw_rect(parent, lx, ly, lw, lh, color, int(4 * s))
    _draw_rect(parent, lx + int(2 * s), ly, lw - int(4 * s), max(2, int(4 * s)),
               color_light, int(3 * s))
    hw = int(28 * s)
    hh = max(3, int(6 * s))
    _draw_rect(parent, cx - hw // 2, ly - hh + int(1 * s), hw, hh,
               color_light, int(3 * s))
    wheel_r = max(3, int(7 * s))
    wheel_y = by + bh + int(2 * s)
    _draw_circle(parent, bx + int(10 * s), wheel_y, wheel_r, 0x263238)
    _draw_circle(parent, bx + bw - int(10 * s), wheel_y, wheel_r, 0x263238)
    hub_r = max(1, int(3 * s))
    _draw_circle(parent, bx + int(10 * s), wheel_y, hub_r, 0x455A64)
    _draw_circle(parent, bx + bw - int(10 * s), wheel_y, hub_r, 0x455A64)
    _draw_line(parent,
               [(bx + int(10 * s), wheel_y),
                (bx + bw - int(10 * s), wheel_y)],
               0x37474F, max(2, int(2 * s)))


def _draw_gelber_sack(parent, cx, cy, s, color, color_light):
    """Draw a Gelber Sack (yellow waste bag)."""
    bw = int(64 * s)
    bh = int(78 * s)
    _draw_rect(parent, cx - bw // 2, cy - bh // 2 + int(8 * s),
               bw, bh, color, int(20 * s))
    hw = int(38 * s)
    hh = int(50 * s)
    _draw_rect(parent, cx - hw // 2, cy - hh // 2 + int(8 * s),
               hw, hh, color_light, int(14 * s))
    nw = int(30 * s)
    nh = int(14 * s)
    ny = cy - bh // 2 + int(2 * s)
    _draw_rect(parent, cx - nw // 2, ny, nw, nh, color, int(6 * s))
    ear_r = max(3, int(8 * s))
    ear_y = ny - int(2 * s)
    _draw_circle(parent, cx - int(10 * s), ear_y, ear_r, color)
    _draw_circle(parent, cx + int(10 * s), ear_y, ear_r, color)
    _draw_circle(parent, cx, ear_y + int(2 * s), max(2, int(4 * s)), color_light)
    for i in range(3):
        wy = cy + int(4 * s) + i * int(14 * s)
        ww = int((26 - i * 4) * s)
        _draw_line(parent,
                   [(cx - ww // 2, wy), (cx + ww // 2, wy)],
                   color, max(1, int(2 * s)))


def draw_waste_icon(parent, waste_type, size):
    """Draw a programmatic waste icon."""
    container = lv.obj(parent)
    container.set_size(size, size)
    container.set_style_bg_opa(0, 0)
    container.set_style_border_width(0, 0)
    container.set_style_pad_all(0, 0)
    container.remove_flag(lv.obj.FLAG.CLICKABLE)
    container.remove_flag(lv.obj.FLAG.SCROLLABLE)

    s = size / 200.0
    cx = size // 2
    cy = size // 2
    color = WASTE_COLORS.get(waste_type, 0x37474F)
    color_light = WASTE_COLORS_LIGHT.get(waste_type, 0x546E7A)

    if waste_type == "gelber_sack":
        _draw_gelber_sack(container, cx, cy, s, color, color_light)
    else:
        _draw_muelltonne(container, cx, cy, s, color, color_light)
        if waste_type == "bioabfall":
            leaf_cx = cx + int(20 * s)
            leaf_cy = cy - int(46 * s)
            _draw_circle(container, leaf_cx, leaf_cy, max(3, int(7 * s)), 0x558B2F)
            _draw_circle(container, leaf_cx - int(8 * s), leaf_cy + int(4 * s),
                         max(2, int(5 * s)), 0x558B2F)
        elif waste_type == "altpapier":
            lid_top = cy - int(48 * s)
            pw = int(18 * s)
            ph = int(22 * s)
            _draw_rect(container, cx - int(12 * s), lid_top - ph + int(4 * s),
                       pw, ph, 0xE3F2FD, int(2 * s))
            _draw_rect(container, cx + int(4 * s), lid_top - ph + int(8 * s),
                       pw, ph - int(4 * s), 0xBBDEFB, int(2 * s))
            for j in range(3):
                py = lid_top - ph + int((10 + j * 6) * s)
                _draw_line(container,
                           [(cx - int(8 * s), py), (cx + int(2 * s), py)],
                           0x90CAF9, max(1, int(1 * s)))

    return container


# ---------------------------------------------------------------------------
# 7-Segment Clock Functions
# ---------------------------------------------------------------------------

def _create_7seg_digit(parent, x, y, w=45, h=75, sw=6, color=0x4a90d9):
    """Create a 7-segment digit display. Returns list of 7 segment objects (a-g)."""
    half_h = h // 2
    seg_defs = [
        (x + sw, y, w - 2 * sw, sw),                    # a: top horizontal
        (x + w - sw, y + sw, sw, half_h - sw),           # b: upper right vertical
        (x + w - sw, y + half_h, sw, h - half_h - sw),   # c: lower right vertical
        (x + sw, y + h - sw, w - 2 * sw, sw),            # d: bottom horizontal
        (x, y + half_h, sw, h - half_h - sw),            # e: lower left vertical
        (x, y + sw, sw, half_h - sw),                    # f: upper left vertical
        (x + sw, y + half_h - sw // 2, w - 2 * sw, sw),  # g: middle horizontal
    ]
    segments = []
    for sx, sy, seg_w, seg_h in seg_defs:
        seg = _draw_rect(parent, sx, sy, seg_w, seg_h, color, sw // 2)
        segments.append(seg)
    return segments


def _update_7seg_digit(segments, number):
    """Update a 7-segment digit to show the given number (0-9)."""
    pattern = SEGMENTS.get(number, (0, 0, 0, 0, 0, 0, 0))
    for i, seg in enumerate(segments):
        if pattern[i]:
            seg.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            seg.add_flag(lv.obj.FLAG.HIDDEN)


# ---------------------------------------------------------------------------
# Main Display Class
# ---------------------------------------------------------------------------

class InfoHubDisplay:
    def __init__(self):
        self.data = {}
        self.connected = False
        self.scr = None
        self.status_label = None

        # Weather current card refs
        self.weather_card = None
        self.weather_temp_label = None
        self.gts_label = None
        self.gts_estimate_label = None
        self.weather_cond_label = None
        self.weather_detail_labels = {}
        self.weather_warning_bar = None
        self.weather_warning_label = None
        self._current_condition = None
        self._is_night = False
        self._scene_is_night = None
        self._weather_show_scene = True

        # Sky scene object pools
        self._scene_sky_bands = []
        self._scene_sun = None
        self._scene_moon = None
        self._scene_moon_cutout = None
        self._scene_clouds = []
        self._scene_rain_drops = []
        self._scene_snow_dots = []
        self._scene_fog_bars = []
        self._scene_lightning = []
        self._scene_sun_glow = None
        self._scene_stars = []
        self._scene_flash = None
        self._scene_timer = None
        self._scene_condition = None
        self._scene_frame = 0
        # Animation state arrays
        self._rain_y = []
        self._rain_x = []
        self._rain_speed = 8
        self._snow_x = []
        self._snow_y = []
        self._cloud_x = []
        self._cloud_dir = []
        self._lightning_counter = 0
        self._lightning_active = False
        self._fog_x_offset = []

        # Indoor climate refs
        self.indoor_temp_label = None
        self.indoor_hum_label = None
        self.raumklima_card = None
        self.raumklima_arc = None
        self.raumklima_index_label = None
        self._current_raumklima_color = None

        # Forecast refs (integrated in weather card)
        self.forecast_cols = []
        self.forecast_fallback_label = None
        self._forecast_conditions = [None] * 5

        # Strom card refs
        self.power_card = None
        self.power_arc = None
        self.power_bolt_container = None
        self.power_value_label = None
        self.power_hint_label = None
        self.power_consumption_label = None
        self.power_consumption_hint = None
        self.power_price_label = None
        self.power_price_hint = None
        self.power_cost_label = None
        self.power_cost_hint = None
        self._current_power_color = None
        self._power_max_value = 5000

        # Waste card refs
        self.waste_main_icon_cont = None
        self.waste_main_type_label = None
        self.waste_main_days_label = None
        self.waste_main_date_label = None
        self._current_waste_type = None
        self.waste_preview_cols = []
        self._preview_waste_types = [None, None, None]

        # Value-tile refs - unlike the other widget types (one card ref
        # each), any number of value_tile widgets can exist at once, each
        # bound to a different entity_id from the shared "custom" group -
        # so this is a list, populated in _setup_value_tile_card() and
        # walked by update_custom() to update just the right one(s).
        self._value_tiles = []

        # Clock card refs (standalone widget, see _setup_clock_card)
        self.clock_digits = []
        self.clock_colon_dots = []
        self.clock_colon_visible = True
        self.clock_weekday_label = None
        self.clock_date_label = None
        self._clock_format_12h = False
        self._clock_show_seconds = False

        # Calendar card refs
        self.calendar_card = None
        self.cal_month_year_label = None
        self.cal_grid_cells = []
        self._cal_months_shown = 2
        self._cal_display_month = None
        self._cal_display_year = None
        self._cal_display_day = None
        # Grid 2 (next month)
        self.cal_grid2_month_year_label = None
        self.cal_grid2_cells = []
        self._cal_display_month2 = None
        self._cal_display_year2 = None
        # Selection state
        self._cal_selected_grid = 0
        self._cal_selected_day = None
        self._cal_selected_cell = None
        self.cal_event_header = None
        self.cal_event_items = []
        self._cal_events = []
        self._clock_timer = None

        # Layout-driven screens (built by apply_layout() from the
        # server's layout_update message, not hardcoded)
        self._screen_containers = {}
        self._layout_screen_ids = []
        self._current_page = 0
        self._page_dots = []
        self._swipe_start_x = 0
        self._swipe_start_y = 0

        # Reminder overlay refs
        self._reminder_dim = None
        self._reminder_card = None
        self._reminder_title_label = None
        self._reminder_time_label = None
        self._reminder_until_label = None
        self._reminder_auto_timer = None
        self._shown_reminders = {}
        self._reminder_check_counter = 0

    def init_display(self):
        """Initialize LVGL and framebuffer"""
        lv.init()
        disp = lv.linux_fbdev_create()
        lv.linux_fbdev_set_file(disp, "/dev/fb0")
        print("Display initialized")
        self.touch = None

    def init_touch(self):
        """Initialize touch input after UI is created"""
        try:
            import evdev
            scr = lv.screen_active()
            self.touch = evdev.mouse_indev(scr, cursor=None, device="/dev/input/mice")
            print("Touch input initialized: /dev/input/mice")
        except Exception as e:
            print("Touch init error:", e)

    # ------------------------------------------------------------------
    # UI Creation
    # ------------------------------------------------------------------

    def create_ui(self):
        """Create the always-visible shell (background + header).

        No cards are built here anymore - screens/widgets come from the
        server's layout_update message and are built by apply_layout()
        once it arrives. This keeps the client structurally in sync with
        whatever the InfoHub integration currently describes, instead of
        a hardcoded page/card list.
        """
        self.scr = lv.obj()
        self.scr.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self.scr.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Background + Header stay on screen (always visible)
        self._create_gradient_background()
        self._create_header()

        # Reminder overlay (on top of everything, independent of layout)
        self._create_reminder_overlay()

        lv.screen_load(self.scr)

        print("UI shell created, waiting for layout_update")

    def _create_header(self):
        """Create header bar"""
        header = lv.obj(self.scr)
        header.set_size(DISPLAY_WIDTH, 80)
        header.set_pos(0, 0)
        header.set_style_bg_color(lv.color_hex(0x000000), 0)
        header.set_style_bg_opa(120, 0)
        header.set_style_border_width(0, 0)
        header.set_style_radius(0, 0)
        header.remove_flag(lv.obj.FLAG.CLICKABLE)

        title = lv.label(header)
        title.set_text("InfoHub")
        title.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        title.set_style_text_font(lv.font_montserrat_24, 0)
        title.align(lv.ALIGN.LEFT_MID, 30, 0)

        self.status_label = lv.label(header)
        self.status_label.set_text(_t("connecting"))
        self.status_label.set_style_text_color(lv.color_hex(THEME["warning"]), 0)
        self.status_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.status_label.align(lv.ALIGN.RIGHT_MID, -30, 0)

    def _create_gradient_background(self):
        """Create a smooth multi-layer gradient background (night sky effect)"""
        self.scr.set_style_bg_color(lv.color_hex(0x050510), 0)

        gradient_colors = [
            (0x0a0a20, 0, 200, 0.9),
            (0x15102a, 200, 250, 0.7),
            (0x1a1035, 400, 300, 0.6),
            (0x0f1a30, 650, 300, 0.5),
            (0x0a1525, 900, 350, 0.6),
        ]
        for color, y_pos, height, opacity in gradient_colors:
            layer = lv.obj(self.scr)
            layer.set_size(DISPLAY_WIDTH, height)
            layer.set_pos(0, y_pos)
            layer.set_style_bg_color(lv.color_hex(color), 0)
            layer.set_style_bg_opa(int(opacity * 255), 0)
            layer.set_style_border_width(0, 0)
            layer.set_style_radius(0, 0)
            layer.remove_flag(lv.obj.FLAG.CLICKABLE)

        import random
        random.seed(42)
        for _ in range(80):
            star = lv.obj(self.scr)
            size = random.choice([2, 2, 2, 3, 3, 4])
            star.set_size(size, size)
            star.set_pos(random.randint(0, DISPLAY_WIDTH - size),
                         random.randint(0, DISPLAY_HEIGHT - 100))
            star.set_style_bg_color(lv.color_hex(0xffffff), 0)
            star.set_style_bg_opa(random.randint(80, 200), 0)
            star.set_style_radius(size, 0)
            star.set_style_border_width(0, 0)
            star.remove_flag(lv.obj.FLAG.CLICKABLE)

        print("Gradient background with stars created")

    def _create_page_dots(self, count):
        """Create page indicator dots at the bottom of the screen."""
        self._page_dots = []
        dot_size = 12
        dot_spacing = 20
        total_width = count * dot_size + (count - 1) * dot_spacing
        start_x = (DISPLAY_WIDTH - total_width) // 2

        for i in range(count):
            dot = lv.obj(self.scr)
            dot.set_size(dot_size, dot_size)
            dot.set_pos(start_x + i * (dot_size + dot_spacing), DISPLAY_HEIGHT - 30)
            dot.set_style_radius(dot_size // 2, 0)
            dot.set_style_border_width(0, 0)
            dot.remove_flag(lv.obj.FLAG.CLICKABLE)
            dot.remove_flag(lv.obj.FLAG.SCROLLABLE)

            if i == 0:
                dot.set_style_bg_color(lv.color_hex(THEME["primary"]), 0)
                dot.set_style_bg_opa(255, 0)
            else:
                dot.set_style_bg_color(lv.color_hex(THEME["secondary"]), 0)
                dot.set_style_bg_opa(120, 0)

            self._page_dots.append(dot)

    def _setup_swipe_detection(self):
        """Set up swipe gesture detection on screen."""
        self.scr.add_event_cb(self._on_swipe_press, lv.EVENT.PRESSED, None)
        self.scr.add_event_cb(self._on_swipe_release, lv.EVENT.RELEASED, None)

    def _on_swipe_press(self, event):
        """Record touch start position."""
        try:
            try:
                indev = lv.indev_active()
            except Exception:
                indev = lv.indev_get_act()
            if indev is None:
                return
            point = lv.point_t()
            indev.get_point(point)
            self._swipe_start_x = point.x
            self._swipe_start_y = point.y
        except Exception as e:
            print("Swipe press error:", e)

    def _on_swipe_release(self, event):
        """Check for swipe gesture on release."""
        try:
            try:
                indev = lv.indev_active()
            except Exception:
                indev = lv.indev_get_act()
            if indev is None:
                return
            point = lv.point_t()
            indev.get_point(point)
            dx = point.x - self._swipe_start_x
            dy = point.y - self._swipe_start_y
            if abs(dx) > 100 and abs(dx) > abs(dy):
                if dx < -100:
                    self._switch_page(self._current_page + 1)
                elif dx > 100:
                    self._switch_page(self._current_page - 1)
        except Exception as e:
            print("Swipe release error:", e)

    def _switch_page(self, page):
        """Switch to the screen at `page` in self._layout_screen_ids."""
        if page == self._current_page:
            return
        if page < 0 or page >= len(self._layout_screen_ids):
            return
        self._current_page = page
        for index, screen_id in enumerate(self._layout_screen_ids):
            container = self._screen_containers.get(screen_id)
            if container is None:
                continue
            if index == page:
                container.remove_flag(lv.obj.FLAG.HIDDEN)
            else:
                container.add_flag(lv.obj.FLAG.HIDDEN)
        # Update dots
        for i, dot in enumerate(self._page_dots):
            if i == page:
                dot.set_style_bg_color(lv.color_hex(THEME["primary"]), 0)
                dot.set_style_bg_opa(255, 0)
            else:
                dot.set_style_bg_color(lv.color_hex(THEME["secondary"]), 0)
                dot.set_style_bg_opa(120, 0)
        print("Switched to page", page)

    def _create_card(self, parent, x, y, w, h, title):
        """Create a card widget with glass effect"""
        card = lv.obj(parent)
        card.set_size(w, h)
        card.set_pos(x, y)
        card.set_style_bg_color(lv.color_hex(0x1a1a3a), 0)
        card.set_style_bg_opa(180, 0)
        card.set_style_radius(20, 0)
        card.set_style_border_width(1, 0)
        card.set_style_border_color(lv.color_hex(0x4a4a6a), 0)
        card.set_style_border_opa(100, 0)
        card.set_style_shadow_width(20, 0)
        card.set_style_shadow_color(lv.color_hex(0x000000), 0)
        card.set_style_shadow_opa(80, 0)
        card.remove_flag(lv.obj.FLAG.SCROLLABLE)
        card.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        title_label = lv.label(card)
        title_label.set_text(title)
        title_label.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        title_label.set_style_text_font(lv.font_montserrat_14, 0)
        title_label.align(lv.ALIGN.TOP_LEFT, 15, 15)

        return card

    # ------------------------------------------------------------------
    # Weather Card Setup (560x700) - Animated Sky Scene
    # ------------------------------------------------------------------

    def _setup_weather_card(self, card, options=None):
        """Set up weather card with animated sky scene background.

        `options["show_scene"]` (default True): when False, the sky
        gradient/sun/moon/clouds/etc. stay hidden - see the guards in
        _update_scene_condition()/_animate_scene(). The rest of this
        function (scene object creation) runs unchanged either way,
        since hiding after the fact is far lower-risk than threading a
        conditional through ~400 lines of scene-drawing code nobody can
        visually verify from here.
        """
        import random
        random.seed(int(time.time()))
        self._weather_show_scene = (options or {}).get("show_scene", True)

        # Enable corner clipping and remove padding for edge-to-edge scene
        card.set_style_clip_corner(True, 0)
        card.set_style_pad_all(0, 0)

        # --- Sky gradient bands (5 layers for smoother gradient) ---
        self._scene_sky_bands = []
        for y, h in [(0, 160), (140, 160), (280, 160), (400, 160), (520, 180)]:
            band = lv.obj(card)
            band.set_size(560, h)
            band.set_pos(0, y)
            band.set_style_bg_color(lv.color_hex(0x4682B4), 0)
            band.set_style_bg_opa(255, 0)
            band.set_style_border_width(0, 0)
            band.set_style_radius(0, 0)
            band.remove_flag(lv.obj.FLAG.CLICKABLE)
            band.remove_flag(lv.obj.FLAG.SCROLLABLE)
            if not self._weather_show_scene:
                band.add_flag(lv.obj.FLAG.HIDDEN)
            self._scene_sky_bands.append(band)

        # --- Night stars (15 dots, shown only for clear-night) ---
        self._scene_stars = []
        for _ in range(15):
            sx = random.randint(20, 530)
            sy = random.randint(10, 180)
            sz = random.choice([2, 2, 3, 3, 3])
            star = lv.obj(card)
            star.set_size(sz, sz)
            star.set_pos(sx, sy)
            star.set_style_bg_color(lv.color_hex(0xffffff), 0)
            star.set_style_bg_opa(random.randint(100, 200), 0)
            star.set_style_border_width(0, 0)
            star.set_style_radius(sz, 0)
            star.remove_flag(lv.obj.FLAG.CLICKABLE)
            star.add_flag(lv.obj.FLAG.HIDDEN)
            self._scene_stars.append(star)

        # --- Sun glow (soft glow behind sun) ---
        self._scene_sun_glow = lv.obj(card)
        self._scene_sun_glow.set_size(200, 200)
        self._scene_sun_glow.set_pos(350, -5)
        self._scene_sun_glow.set_style_bg_color(lv.color_hex(0xffd700), 0)
        self._scene_sun_glow.set_style_bg_opa(35, 0)
        self._scene_sun_glow.set_style_radius(100, 0)
        self._scene_sun_glow.set_style_border_width(0, 0)
        self._scene_sun_glow.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._scene_sun_glow.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self._scene_sun_glow.add_flag(lv.obj.FLAG.HIDDEN)

        # --- Sun (container with sun drawing) ---
        self._scene_sun = lv.obj(card)
        self._scene_sun.set_size(160, 160)
        self._scene_sun.set_pos(370, 15)
        self._scene_sun.set_style_bg_opa(0, 0)
        self._scene_sun.set_style_border_width(0, 0)
        self._scene_sun.set_style_pad_all(0, 0)
        self._scene_sun.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._scene_sun.remove_flag(lv.obj.FLAG.SCROLLABLE)
        _draw_sun(self._scene_sun, 80, 80, 45, 1.0)
        self._scene_sun.add_flag(lv.obj.FLAG.HIDDEN)

        # --- Moon (crescent via circle + cutout) ---
        self._scene_moon = lv.obj(card)
        self._scene_moon.set_size(100, 100)
        self._scene_moon.set_pos(400, 30)
        self._scene_moon.set_style_bg_opa(0, 0)
        self._scene_moon.set_style_border_width(0, 0)
        self._scene_moon.set_style_pad_all(0, 0)
        self._scene_moon.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._scene_moon.remove_flag(lv.obj.FLAG.SCROLLABLE)
        _draw_circle(self._scene_moon, 50, 50, 35, 0xffd700)
        self._scene_moon_cutout = _draw_circle(
            self._scene_moon, 62, 40, 35, 0x0a0a20)
        self._scene_moon.add_flag(lv.obj.FLAG.HIDDEN)

        # --- 3 Clouds (containers with cloud shapes) ---
        self._scene_clouds = []
        self._cloud_x = [60.0, 250.0, 400.0]
        self._cloud_dir = [0.5, -0.3, 0.4]
        cloud_y = [55, 95, 70]
        cloud_s = [1.3, 1.1, 0.9]
        for ci in range(3):
            s = cloud_s[ci]
            cw = int(72 * s)
            ch = int(48 * s)
            cloud = lv.obj(card)
            cloud.set_size(cw, ch)
            cloud.set_pos(int(self._cloud_x[ci]), cloud_y[ci])
            cloud.set_style_bg_opa(0, 0)
            cloud.set_style_border_width(0, 0)
            cloud.set_style_pad_all(0, 0)
            cloud.remove_flag(lv.obj.FLAG.CLICKABLE)
            cloud.remove_flag(lv.obj.FLAG.SCROLLABLE)
            cx = cw // 2
            cy = ch // 2
            color = 0xC8C8D0
            _draw_circle(cloud, cx, cy, int(18 * s), color)
            _draw_circle(cloud, cx - int(16 * s), cy + int(4 * s),
                         int(14 * s), color)
            _draw_circle(cloud, cx + int(16 * s), cy + int(4 * s),
                         int(14 * s), color)
            _draw_circle(cloud, cx - int(8 * s), cy - int(10 * s),
                         int(12 * s), color)
            _draw_circle(cloud, cx + int(8 * s), cy - int(8 * s),
                         int(12 * s), color)
            rect = lv.obj(cloud)
            rect.set_size(int(48 * s), int(16 * s))
            rect.set_pos(cx - int(24 * s), cy)
            rect.set_style_bg_color(lv.color_hex(color), 0)
            rect.set_style_bg_opa(255, 0)
            rect.set_style_border_width(0, 0)
            rect.set_style_radius(int(4 * s), 0)
            rect.remove_flag(lv.obj.FLAG.CLICKABLE)
            cloud.add_flag(lv.obj.FLAG.HIDDEN)
            self._scene_clouds.append(cloud)

        # --- 30 Rain drops (taller for realism) ---
        self._scene_rain_drops = []
        self._rain_x = []
        self._rain_y = []
        for i in range(30):
            drop = lv.obj(card)
            drop.set_size(2, 18)
            rx = random.randint(10, 540)
            ry = random.randint(-20, 380)
            drop.set_pos(rx, ry)
            drop.set_style_bg_color(lv.color_hex(0x5b9bd5), 0)
            drop.set_style_bg_opa(180, 0)
            drop.set_style_border_width(0, 0)
            drop.set_style_radius(1, 0)
            drop.remove_flag(lv.obj.FLAG.CLICKABLE)
            drop.add_flag(lv.obj.FLAG.HIDDEN)
            self._scene_rain_drops.append(drop)
            self._rain_x.append(float(rx))
            self._rain_y.append(float(ry))

        # --- 20 Snow dots ---
        self._scene_snow_dots = []
        self._snow_x = []
        self._snow_y = []
        for i in range(20):
            dot = lv.obj(card)
            dot.set_size(5, 5)
            sx = random.randint(10, 540)
            sy = random.randint(-20, 380)
            dot.set_pos(sx, sy)
            dot.set_style_bg_color(lv.color_hex(0xffffff), 0)
            dot.set_style_bg_opa(200, 0)
            dot.set_style_border_width(0, 0)
            dot.set_style_radius(3, 0)
            dot.remove_flag(lv.obj.FLAG.CLICKABLE)
            dot.add_flag(lv.obj.FLAG.HIDDEN)
            self._scene_snow_dots.append(dot)
            self._snow_x.append(float(sx))
            self._snow_y.append(float(sy))

        # --- 4 Fog bars ---
        self._scene_fog_bars = []
        self._fog_x_offset = [0.0, 0.0, 0.0, 0.0]
        fog_configs = [(80, 500), (125, 460), (170, 420), (215, 380)]
        for fy, fw in fog_configs:
            bar = lv.obj(card)
            bar.set_size(fw, 8)
            bar.set_pos((560 - fw) // 2, fy)
            bar.set_style_bg_color(lv.color_hex(0x9098a8), 0)
            bar.set_style_bg_opa(120, 0)
            bar.set_style_border_width(0, 0)
            bar.set_style_radius(4, 0)
            bar.remove_flag(lv.obj.FLAG.CLICKABLE)
            bar.add_flag(lv.obj.FLAG.HIDDEN)
            self._scene_fog_bars.append(bar)

        # --- 2 Lightning bolts (containers with bolt drawings) ---
        self._scene_lightning = []
        for bx, by in [(160, 130), (340, 110)]:
            bolt_cont = lv.obj(card)
            bolt_cont.set_size(50, 60)
            bolt_cont.set_pos(bx, by)
            bolt_cont.set_style_bg_opa(0, 0)
            bolt_cont.set_style_border_width(0, 0)
            bolt_cont.set_style_pad_all(0, 0)
            bolt_cont.remove_flag(lv.obj.FLAG.CLICKABLE)
            bolt_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)
            _draw_bolt(bolt_cont, 25, 5, 1.5, 0xffd700)
            bolt_cont.add_flag(lv.obj.FLAG.HIDDEN)
            self._scene_lightning.append(bolt_cont)

        # --- Lightning flash overlay (covers sky area, normally invisible) ---
        self._scene_flash = lv.obj(card)
        self._scene_flash.set_size(560, 200)
        self._scene_flash.set_pos(0, 0)
        self._scene_flash.set_style_bg_color(lv.color_hex(0xffffff), 0)
        self._scene_flash.set_style_bg_opa(0, 0)
        self._scene_flash.set_style_border_width(0, 0)
        self._scene_flash.set_style_radius(0, 0)
        self._scene_flash.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._scene_flash.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # --- Dark overlay gradient (3 layers for smooth transition) ---
        for oy, oh, oopa in [(180, 60, 40), (220, 60, 90), (260, 440, 160)]:
            ov = lv.obj(card)
            ov.set_size(560, oh)
            ov.set_pos(0, oy)
            ov.set_style_bg_color(lv.color_hex(0x000000), 0)
            ov.set_style_bg_opa(oopa, 0)
            ov.set_style_border_width(0, 0)
            ov.set_style_radius(0, 0)
            ov.remove_flag(lv.obj.FLAG.CLICKABLE)
            ov.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # === Data labels (on top of scene + overlay) ===

        # Temperature glow background for readability
        self._temp_glow_bg = lv.obj(card)
        self._temp_glow_bg.set_size(200, 70)
        self._temp_glow_bg.set_pos(20, 35)
        self._temp_glow_bg.set_style_bg_color(lv.color_hex(0x000000), 0)
        self._temp_glow_bg.set_style_bg_opa(80, 0)
        self._temp_glow_bg.set_style_border_width(0, 0)
        self._temp_glow_bg.set_style_radius(10, 0)
        self._temp_glow_bg.remove_flag(lv.obj.FLAG.CLICKABLE)
        self._temp_glow_bg.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Temperature - large, in the sky area above overlay
        self.weather_temp_label = lv.label(card)
        self.weather_temp_label.set_text("-- C")
        self.weather_temp_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.weather_temp_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.weather_temp_label.set_pos(30, 45)
        self.weather_temp_label.set_style_transform_scale(576, 0)
        self.weather_temp_label.set_style_transform_pivot_x(0, 0)
        self.weather_temp_label.set_style_transform_pivot_y(0, 0)

        # GTS (Gruenlandtemperatursumme) - top right
        gts_bg = lv.obj(card)
        gts_bg.set_size(130, 75)
        gts_bg.set_pos(410, 35)
        gts_bg.set_style_bg_color(lv.color_hex(0x000000), 0)
        gts_bg.set_style_bg_opa(80, 0)
        gts_bg.set_style_border_width(0, 0)
        gts_bg.set_style_radius(10, 0)
        gts_bg.remove_flag(lv.obj.FLAG.CLICKABLE)
        gts_bg.remove_flag(lv.obj.FLAG.SCROLLABLE)

        gts_header = lv.label(card)
        gts_header.set_text("GTS")
        gts_header.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        gts_header.set_style_text_font(lv.font_montserrat_14, 0)
        gts_header.set_pos(420, 38)

        self.gts_label = lv.label(card)
        self.gts_label.set_text("--")
        self.gts_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.gts_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.gts_label.set_pos(420, 55)

        self.gts_estimate_label = lv.label(card)
        self.gts_estimate_label.set_text("")
        self.gts_estimate_label.set_style_text_color(
            lv.color_hex(THEME["text_secondary"]), 0)
        self.gts_estimate_label.set_style_text_font(
            lv.font_montserrat_14, 0)
        self.gts_estimate_label.set_pos(420, 83)

        # Condition text
        self.weather_cond_label = lv.label(card)
        self.weather_cond_label.set_text("--")
        self.weather_cond_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.weather_cond_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.weather_cond_label.set_pos(30, 120)
        self.weather_cond_label.set_style_transform_scale(320, 0)
        self.weather_cond_label.set_style_transform_pivot_x(0, 0)
        self.weather_cond_label.set_style_transform_pivot_y(0, 0)

        # Separator
        sep = lv.obj(card)
        sep.set_size(520, 2)
        sep.set_pos(20, 295)
        sep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        sep.set_style_bg_opa(120, 0)
        sep.set_style_border_width(0, 0)
        sep.set_style_radius(1, 0)
        sep.remove_flag(lv.obj.FLAG.CLICKABLE)

        # Detail grid
        detail_items_left = [
            ("clouds", _t("clouds"), "-- %"),
            ("humidity", _t("humidity_short"), "-- %"),
            ("precipitation", _t("precipitation_short"), "-- mm"),
        ]
        detail_items_right = [
            ("wind", _t("wind"), "-- km/h"),
            ("pressure", _t("pressure"), "-- hPa"),
            ("visibility", _t("visibility"), "-- km"),
        ]
        y_start = 305
        y_step = 45
        left_x = 30
        right_x = 290

        # Vertical separator between left and right columns
        vsep = lv.obj(card)
        vsep.set_size(1, y_step * 3)
        vsep.set_pos(270, y_start)
        vsep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        vsep.set_style_bg_opa(80, 0)
        vsep.set_style_border_width(0, 0)
        vsep.set_style_radius(0, 0)
        vsep.remove_flag(lv.obj.FLAG.CLICKABLE)

        for i, (key, label_text, default) in enumerate(detail_items_left):
            y = y_start + i * y_step
            lbl = lv.label(card)
            lbl.set_text(label_text + ":")
            lbl.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
            lbl.set_style_text_font(lv.font_montserrat_14, 0)
            lbl.set_pos(left_x, y)
            val = lv.label(card)
            val.set_text(default)
            val.set_style_text_color(lv.color_hex(THEME["text"]), 0)
            val.set_style_text_font(lv.font_montserrat_16, 0)
            val.set_pos(left_x + 130, y)
            self.weather_detail_labels[key] = val

        for i, (key, label_text, default) in enumerate(detail_items_right):
            y = y_start + i * y_step
            lbl = lv.label(card)
            lbl.set_text(label_text + ":")
            lbl.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
            lbl.set_style_text_font(lv.font_montserrat_14, 0)
            lbl.set_pos(right_x, y)
            val = lv.label(card)
            val.set_text(default)
            val.set_style_text_color(lv.color_hex(THEME["text"]), 0)
            val.set_style_text_font(lv.font_montserrat_16, 0)
            val.set_pos(right_x + 130, y)
            self.weather_detail_labels[key] = val

        # Warning bar
        self.weather_warning_bar = lv.obj(card)
        self.weather_warning_bar.set_size(520, 50)
        self.weather_warning_bar.set_pos(20, 435)
        self.weather_warning_bar.set_style_bg_color(lv.color_hex(THEME["error"]), 0)
        self.weather_warning_bar.set_style_bg_opa(180, 0)
        self.weather_warning_bar.set_style_radius(10, 0)
        self.weather_warning_bar.set_style_border_width(0, 0)
        self.weather_warning_bar.remove_flag(lv.obj.FLAG.CLICKABLE)
        self.weather_warning_bar.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self.weather_warning_bar.add_flag(lv.obj.FLAG.HIDDEN)

        self.weather_warning_label = lv.label(self.weather_warning_bar)
        self.weather_warning_label.set_text("")
        self.weather_warning_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.weather_warning_label.set_style_text_font(lv.font_montserrat_14, 0)
        self.weather_warning_label.align(lv.ALIGN.LEFT_MID, 15, 0)

        # === Integrated Forecast Section ===
        forecast_sep = lv.obj(card)
        forecast_sep.set_size(520, 2)
        forecast_sep.set_pos(20, 485)
        forecast_sep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        forecast_sep.set_style_bg_opa(120, 0)
        forecast_sep.set_style_border_width(0, 0)
        forecast_sep.set_style_radius(1, 0)
        forecast_sep.remove_flag(lv.obj.FLAG.CLICKABLE)

        forecast_header = lv.label(card)
        forecast_header.set_text(_t("forecast"))
        forecast_header.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        forecast_header.set_style_text_font(lv.font_montserrat_14, 0)
        forecast_header.set_pos(20, 492)

        self.forecast_cols = []
        col_width = 100
        total_width = 5 * col_width
        start_x = (560 - total_width) // 2

        for i in range(5):
            col_x = start_x + i * col_width
            col = {}

            day_lbl = lv.label(card)
            day_lbl.set_text("--")
            day_lbl.set_style_text_color(lv.color_hex(THEME["text"]), 0)
            day_lbl.set_style_text_font(lv.font_montserrat_16, 0)
            day_lbl.set_pos(col_x + 50 - 12, 515)
            col["day"] = day_lbl

            icon_cont = lv.obj(card)
            icon_cont.set_size(85, 85)
            icon_cont.set_pos(col_x + 50 - 42, 540)
            icon_cont.set_style_bg_opa(0, 0)
            icon_cont.set_style_border_width(0, 0)
            icon_cont.set_style_pad_all(0, 0)
            icon_cont.remove_flag(lv.obj.FLAG.CLICKABLE)
            icon_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)
            col["icon_container"] = icon_cont

            temp_lbl = lv.label(card)
            temp_lbl.set_text("--/-- C")
            temp_lbl.set_style_text_color(lv.color_hex(THEME["text"]), 0)
            temp_lbl.set_style_text_font(lv.font_montserrat_16, 0)
            temp_lbl.set_pos(col_x + 50 - 30, 635)
            col["temp"] = temp_lbl

            precip_lbl = lv.label(card)
            precip_lbl.set_text("--%")
            precip_lbl.set_style_text_color(lv.color_hex(THEME["rain_blue"]), 0)
            precip_lbl.set_style_text_font(lv.font_montserrat_14, 0)
            precip_lbl.set_pos(col_x + 50 - 15, 660)
            col["precip"] = precip_lbl

            self.forecast_cols.append(col)

        self.forecast_fallback_label = lv.label(card)
        self.forecast_fallback_label.set_text(_t("no_forecast"))
        self.forecast_fallback_label.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        self.forecast_fallback_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.forecast_fallback_label.set_pos(150, 580)
        self.forecast_fallback_label.add_flag(lv.obj.FLAG.HIDDEN)

    # ------------------------------------------------------------------
    # Sky Scene Animation
    # ------------------------------------------------------------------

    def _start_scene_timer(self):
        """Start the 150ms animation timer for the sky scene."""
        self._scene_timer = lv.timer_create(
            lambda t: self._animate_scene(), 150, None)

    def _update_moon_phase(self):
        """Position moon cutout based on current lunar phase."""
        import math
        lt = time.localtime()
        phase = _moon_phase(lt[0], lt[1], lt[2])

        # Near new moon - hide entirely
        if phase < 0.03 or phase > 0.97:
            self._scene_moon.add_flag(lv.obj.FLAG.HIDDEN)
            return

        R = 35
        # d = displacement of cutout circle from moon center
        d = int((1 - math.cos(2 * math.pi * phase)) * R)
        cx_base = 50  # moon body center x within container
        cy_base = 50
        if phase < 0.5:
            # Waxing: cutout left of center (right side illuminated)
            cx = cx_base - R + d
        else:
            # Waning: cutout right of center (left side illuminated)
            cx = cx_base + R - d
        self._scene_moon_cutout.set_pos(cx - R, cy_base - R)

    def _update_scene_condition(self, condition, is_night=False):
        """Update sky scene objects based on weather condition and time."""
        if not self._weather_show_scene:
            return
        if (condition == self._scene_condition
                and is_night == self._scene_is_night):
            return
        self._scene_condition = condition
        self._scene_is_night = is_night

        # For night: use clear-night theme for sunny/partlycloudy,
        # darken other themes
        if is_night and condition in ("sunny", "partlycloudy"):
            theme = SKY_THEMES.get("clear-night")
        elif is_night:
            day_theme = SKY_THEMES.get(condition, SKY_THEMES.get("cloudy"))
            theme = (
                _darken_color(day_theme[0]),
                _darken_color(day_theme[1]),
                _darken_color(day_theme[2], 0.6),
            )
        else:
            theme = SKY_THEMES.get(condition, SKY_THEMES.get("cloudy"))
        top_color, bottom_color, cloud_color = theme

        # Interpolate 5 colors for smooth gradient
        tr = (top_color >> 16) & 0xFF
        tg = (top_color >> 8) & 0xFF
        tb = top_color & 0xFF
        br = (bottom_color >> 16) & 0xFF
        bg_ = (bottom_color >> 8) & 0xFF
        bb = bottom_color & 0xFF
        band_colors = []
        for frac in [0, 25, 50, 75, 100]:
            r = tr + (br - tr) * frac // 100
            g = tg + (bg_ - tg) * frac // 100
            b = tb + (bb - tb) * frac // 100
            band_colors.append((r << 16) | (g << 8) | b)

        # Update 5 sky bands
        for i, band in enumerate(self._scene_sky_bands):
            band.set_style_bg_color(lv.color_hex(band_colors[i]), 0)

        # Update moon cutout to match sky
        if self._scene_moon_cutout:
            self._scene_moon_cutout.set_style_bg_color(
                lv.color_hex(top_color), 0)

        # Determine what to show based on condition + night
        if is_night:
            show_sun = False
            show_moon = condition in (
                "sunny", "partlycloudy", "clear-night",
                "cloudy", "windy", "windy-variant")
            show_stars = condition in (
                "sunny", "partlycloudy", "clear-night")
        else:
            show_sun = condition in ("sunny", "partlycloudy")
            show_moon = condition in ("clear-night",)
            show_stars = condition in ("clear-night",)

        show_clouds = condition in (
            "partlycloudy", "cloudy", "rainy", "pouring",
            "snowy", "snowy-rainy", "lightning", "lightning-rainy",
            "hail", "fog")
        show_rain = condition in (
            "rainy", "pouring", "lightning-rainy", "snowy-rainy")
        show_snow = condition in ("snowy", "snowy-rainy", "hail")
        show_fog = condition in ("fog",)
        show_lightning = condition in ("lightning", "lightning-rainy")

        # Stars
        for star in self._scene_stars:
            if show_stars:
                star.remove_flag(lv.obj.FLAG.HIDDEN)
            else:
                star.add_flag(lv.obj.FLAG.HIDDEN)

        # Sun/Moon + Sun glow
        if show_sun:
            self._scene_sun.remove_flag(lv.obj.FLAG.HIDDEN)
            self._scene_sun_glow.remove_flag(lv.obj.FLAG.HIDDEN)
        else:
            self._scene_sun.add_flag(lv.obj.FLAG.HIDDEN)
            self._scene_sun_glow.add_flag(lv.obj.FLAG.HIDDEN)
        if show_moon:
            self._scene_moon.remove_flag(lv.obj.FLAG.HIDDEN)
            self._update_moon_phase()
        else:
            self._scene_moon.add_flag(lv.obj.FLAG.HIDDEN)

        # Clouds - update count and color from theme
        num_clouds = 3 if show_clouds else 0
        if condition == "partlycloudy":
            num_clouds = 2
        for i, cloud in enumerate(self._scene_clouds):
            if i < num_clouds:
                cloud.remove_flag(lv.obj.FLAG.HIDDEN)
                # Update cloud color from theme
                child_cnt = cloud.get_child_count()
                for ci in range(child_cnt):
                    child = cloud.get_child(ci)
                    child.set_style_bg_color(lv.color_hex(cloud_color), 0)
            else:
                cloud.add_flag(lv.obj.FLAG.HIDDEN)

        # Rain drops
        self._rain_speed = 12 if condition == "pouring" else 8
        num_drops = 30 if condition == "pouring" else (20 if show_rain else 0)
        for i, drop in enumerate(self._scene_rain_drops):
            if i < num_drops:
                drop.remove_flag(lv.obj.FLAG.HIDDEN)
            else:
                drop.add_flag(lv.obj.FLAG.HIDDEN)

        # Snow dots
        num_snow = 20 if show_snow else 0
        for i, dot in enumerate(self._scene_snow_dots):
            if i < num_snow:
                dot.remove_flag(lv.obj.FLAG.HIDDEN)
            else:
                dot.add_flag(lv.obj.FLAG.HIDDEN)

        # Fog bars
        for bar in self._scene_fog_bars:
            if show_fog:
                bar.remove_flag(lv.obj.FLAG.HIDDEN)
            else:
                bar.add_flag(lv.obj.FLAG.HIDDEN)

        # Lightning + flash overlay reset
        self._lightning_active = show_lightning
        self._lightning_counter = 0
        for bolt in self._scene_lightning:
            bolt.add_flag(lv.obj.FLAG.HIDDEN)
        if self._scene_flash:
            self._scene_flash.set_style_bg_opa(0, 0)

        # Wind - faster cloud drift
        if condition in ("windy", "windy-variant"):
            self._cloud_dir = [1.5, -1.0, 1.2]
            for cloud in self._scene_clouds:
                cloud.remove_flag(lv.obj.FLAG.HIDDEN)

    def _update_scene_intensity(self, cloud_pct, precip, wind, visibility):
        """Adjust scene intensity from live weather data."""
        try:
            # Adjust rain drop count based on precipitation
            if self._scene_condition in (
                    "rainy", "pouring", "lightning-rainy", "snowy-rainy"):
                p = float(precip) if precip and precip != "--" else 0
                count = min(30, max(5, int(p * 10)))
                for i, drop in enumerate(self._scene_rain_drops):
                    if i < count:
                        drop.remove_flag(lv.obj.FLAG.HIDDEN)
                    else:
                        drop.add_flag(lv.obj.FLAG.HIDDEN)

            # Adjust cloud count from cloud coverage
            if cloud_pct and cloud_pct != "--":
                cp = float(cloud_pct)
                num_c = 0 if cp < 20 else (1 if cp < 50 else (2 if cp < 80 else 3))
                for i, cloud in enumerate(self._scene_clouds):
                    if i < num_c:
                        cloud.remove_flag(lv.obj.FLAG.HIDDEN)

            # Adjust rain speed from wind
            if wind and wind != "--":
                w = float(wind)
                self._rain_speed = min(20, max(6, int(6 + w * 0.3)))

            # Fog density from visibility
            if self._scene_condition == "fog" and visibility and visibility != "--":
                v = float(visibility)
                opa = min(200, max(60, int(200 - v * 15)))
                for bar in self._scene_fog_bars:
                    bar.set_style_bg_opa(opa, 0)

            # Sun dimming from cloud coverage
            if self._scene_sun and cloud_pct and cloud_pct != "--":
                cp = float(cloud_pct)
                sun_opa = max(80, int(255 - cp * 1.5))
                self._scene_sun.set_style_opa(sun_opa, 0)
        except Exception:
            pass

    def _animate_scene(self):
        """Animation tick for the sky scene (~6.7 FPS at 150ms)."""
        if not self._weather_show_scene:
            return
        import random
        self._scene_frame += 1

        # Rain drops - fall down with wind drift
        for i, drop in enumerate(self._scene_rain_drops):
            if not drop.has_flag(lv.obj.FLAG.HIDDEN):
                self._rain_y[i] += self._rain_speed
                self._rain_x[i] += 1.0
                if self._rain_y[i] > 450 or self._rain_x[i] > 555:
                    self._rain_y[i] = float(random.randint(-30, -5))
                    self._rain_x[i] = float(random.randint(10, 540))
                drop.set_pos(int(self._rain_x[i]), int(self._rain_y[i]))

        # Snow dots - drift and fall slowly
        for i, dot in enumerate(self._scene_snow_dots):
            if not dot.has_flag(lv.obj.FLAG.HIDDEN):
                self._snow_y[i] += 2.5
                self._snow_x[i] += float(random.randint(-1, 1))
                if self._snow_y[i] > 450:
                    self._snow_y[i] = float(random.randint(-30, -5))
                    self._snow_x[i] = float(random.randint(10, 540))
                if self._snow_x[i] < 5:
                    self._snow_x[i] = 5.0
                elif self._snow_x[i] > 545:
                    self._snow_x[i] = 545.0
                dot.set_pos(int(self._snow_x[i]), int(self._snow_y[i]))

        # Clouds - gentle horizontal drift
        for i, cloud in enumerate(self._scene_clouds):
            if not cloud.has_flag(lv.obj.FLAG.HIDDEN):
                self._cloud_x[i] += self._cloud_dir[i]
                if self._cloud_x[i] > 480:
                    self._cloud_dir[i] = -abs(self._cloud_dir[i])
                elif self._cloud_x[i] < -20:
                    self._cloud_dir[i] = abs(self._cloud_dir[i])
                cloud.set_x(int(self._cloud_x[i]))

        # Lightning flash (every ~3 seconds) + scene flash overlay
        if self._lightning_active:
            self._lightning_counter += 1
            if self._lightning_counter == 1:
                idx = random.randint(0, len(self._scene_lightning) - 1)
                self._scene_lightning[idx].remove_flag(lv.obj.FLAG.HIDDEN)
                if self._scene_flash:
                    self._scene_flash.set_style_bg_opa(60, 0)
            elif self._lightning_counter == 2:
                if self._scene_flash:
                    self._scene_flash.set_style_bg_opa(0, 0)
            elif self._lightning_counter == 3:
                for bolt in self._scene_lightning:
                    bolt.add_flag(lv.obj.FLAG.HIDDEN)
            elif self._lightning_counter > 20:
                self._lightning_counter = 0

        # Fog bars - slight horizontal oscillation
        for i, bar in enumerate(self._scene_fog_bars):
            if not bar.has_flag(lv.obj.FLAG.HIDDEN):
                import math
                self._fog_x_offset[i] = math.sin(
                    self._scene_frame * 0.1 + i * 1.5) * 10
                bar.set_x(int((560 - bar.get_width()) // 2 +
                              self._fog_x_offset[i]))

    # ------------------------------------------------------------------
    # Raumklima Card Setup (560x350)
    # ------------------------------------------------------------------

    def _setup_raumklima_card(self, card, options=None):
        """Set up the indoor climate card with 180-degree comfort gauge."""
        # 180° arc gauge (centered semicircle at top)
        self.raumklima_arc = lv.arc(card)
        self.raumklima_arc.set_size(300, 300)
        self.raumklima_arc.set_pos(130, 30)
        self.raumklima_arc.set_rotation(180)
        self.raumklima_arc.set_bg_angles(0, 180)
        self.raumklima_arc.set_range(0, 100)
        self.raumklima_arc.set_value(50)
        self.raumklima_arc.set_style_arc_color(lv.color_hex(0x0f0f23), lv.PART.MAIN)
        self.raumklima_arc.set_style_arc_width(18, lv.PART.MAIN)
        self.raumklima_arc.set_style_arc_color(
            lv.color_hex(THEME["success"]), lv.PART.INDICATOR)
        self.raumklima_arc.set_style_arc_width(18, lv.PART.INDICATOR)
        self.raumklima_arc.set_style_bg_opa(0, lv.PART.KNOB)
        self.raumklima_arc.set_style_pad_all(0, lv.PART.KNOB)
        self.raumklima_arc.remove_flag(lv.obj.FLAG.CLICKABLE)

        # Comfort index label (centered in semicircle)
        self.raumklima_index_label = lv.label(card)
        self.raumklima_index_label.set_text("--")
        self.raumklima_index_label.set_style_text_color(
            lv.color_hex(THEME["success"]), 0)
        self.raumklima_index_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.raumklima_index_label.set_width(200)
        self.raumklima_index_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self.raumklima_index_label.set_pos(180, 115)

        comfort_hint = lv.label(card)
        comfort_hint.set_text(_t("comfort"))
        comfort_hint.set_style_text_color(
            lv.color_hex(THEME["text_secondary"]), 0)
        comfort_hint.set_style_text_font(lv.font_montserrat_14, 0)
        comfort_hint.set_width(200)
        comfort_hint.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        comfort_hint.set_pos(180, 148)

        # Separator below arc area
        rk_sep = lv.obj(card)
        rk_sep.set_size(520, 2)
        rk_sep.set_pos(20, 200)
        rk_sep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        rk_sep.set_style_bg_opa(120, 0)
        rk_sep.set_style_border_width(0, 0)
        rk_sep.set_style_radius(1, 0)
        rk_sep.remove_flag(lv.obj.FLAG.CLICKABLE)

        # Temperature (left column)
        temp_header = lv.label(card)
        temp_header.set_text(_t("temperature"))
        temp_header.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        temp_header.set_style_text_font(lv.font_montserrat_14, 0)
        temp_header.set_pos(60, 220)

        self.indoor_temp_label = lv.label(card)
        self.indoor_temp_label.set_text("-- C")
        self.indoor_temp_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.indoor_temp_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.indoor_temp_label.set_pos(60, 248)

        # Vertical separator between columns
        rk_vsep = lv.obj(card)
        rk_vsep.set_size(1, 80)
        rk_vsep.set_pos(278, 215)
        rk_vsep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        rk_vsep.set_style_bg_opa(80, 0)
        rk_vsep.set_style_border_width(0, 0)
        rk_vsep.set_style_radius(0, 0)
        rk_vsep.remove_flag(lv.obj.FLAG.CLICKABLE)

        # Humidity (right column)
        hum_header = lv.label(card)
        hum_header.set_text(_t("humidity"))
        hum_header.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        hum_header.set_style_text_font(lv.font_montserrat_14, 0)
        hum_header.set_pos(310, 220)

        self.indoor_hum_label = lv.label(card)
        self.indoor_hum_label.set_text("-- %")
        self.indoor_hum_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.indoor_hum_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.indoor_hum_label.set_pos(310, 248)

    # ------------------------------------------------------------------
    # Strom Card Setup (560x490)
    # ------------------------------------------------------------------

    def _setup_strom_card(self, card, options=None):
        """Set up the Strom card with arc gauge, bolt icon, and 4 data fields."""
        card.set_style_pad_all(0, 0)
        try:
            self._power_max_value = float((options or {}).get("max_value", 5000))
        except (TypeError, ValueError):
            self._power_max_value = 5000

        self.power_arc = lv.arc(card)
        self.power_arc.set_size(280, 280)
        self.power_arc.set_pos(15, 50)
        self.power_arc.set_rotation(135)
        self.power_arc.set_bg_angles(0, 270)
        self.power_arc.set_range(0, 100)
        self.power_arc.set_value(0)
        self.power_arc.set_style_arc_color(lv.color_hex(0x0f0f23), lv.PART.MAIN)
        self.power_arc.set_style_arc_width(18, lv.PART.MAIN)
        self.power_arc.set_style_arc_opa(255, lv.PART.MAIN)
        self.power_arc.set_style_arc_color(lv.color_hex(THEME["success"]), lv.PART.INDICATOR)
        self.power_arc.set_style_arc_width(18, lv.PART.INDICATOR)
        self.power_arc.set_style_bg_opa(0, lv.PART.KNOB)
        self.power_arc.set_style_pad_all(0, lv.PART.KNOB)
        self.power_arc.set_style_bg_opa(0, 0)
        self.power_arc.set_style_border_width(0, 0)
        self.power_arc.remove_flag(lv.obj.FLAG.CLICKABLE)
        self.power_arc.remove_flag(lv.obj.FLAG.SCROLLABLE)

        self.power_bolt_container = lv.obj(card)
        self.power_bolt_container.set_size(80, 80)
        self.power_bolt_container.set_pos(115, 145)
        self.power_bolt_container.set_style_bg_opa(0, 0)
        self.power_bolt_container.set_style_border_width(0, 0)
        self.power_bolt_container.set_style_pad_all(0, 0)
        self.power_bolt_container.remove_flag(lv.obj.FLAG.CLICKABLE)
        self.power_bolt_container.remove_flag(lv.obj.FLAG.SCROLLABLE)
        _draw_power_bolt(self.power_bolt_container, 40, 40, 1.0)

        self.power_value_label = lv.label(card)
        self.power_value_label.set_text("-- W")
        self.power_value_label.set_style_text_color(lv.color_hex(THEME["success"]), 0)
        self.power_value_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.power_value_label.set_pos(310, 90)

        self.power_hint_label = lv.label(card)
        self.power_hint_label.set_text(_t("current_power"))
        self.power_hint_label.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        self.power_hint_label.set_style_text_font(lv.font_montserrat_14, 0)
        self.power_hint_label.set_pos(310, 125)

        mini_sep = lv.obj(card)
        mini_sep.set_size(220, 1)
        mini_sep.set_pos(310, 160)
        mini_sep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        mini_sep.set_style_bg_opa(80, 0)
        mini_sep.set_style_border_width(0, 0)
        mini_sep.set_style_radius(0, 0)
        mini_sep.remove_flag(lv.obj.FLAG.CLICKABLE)

        self.power_consumption_label = lv.label(card)
        self.power_consumption_label.set_text("-- kWh")
        self.power_consumption_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.power_consumption_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.power_consumption_label.set_pos(310, 180)

        self.power_consumption_hint = lv.label(card)
        self.power_consumption_hint.set_text(_t("daily_consumption"))
        self.power_consumption_hint.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        self.power_consumption_hint.set_style_text_font(lv.font_montserrat_14, 0)
        self.power_consumption_hint.set_pos(310, 210)

        sep = lv.obj(card)
        sep.set_size(520, 2)
        sep.set_pos(20, 350)
        sep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        sep.set_style_bg_opa(120, 0)
        sep.set_style_border_width(0, 0)
        sep.set_style_radius(1, 0)
        sep.remove_flag(lv.obj.FLAG.CLICKABLE)

        _draw_rect(card, 30, 375, 4, 50, THEME["warning"], 2)
        self.power_price_label = lv.label(card)
        self.power_price_label.set_text("-- ct/kWh")
        self.power_price_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.power_price_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.power_price_label.set_pos(50, 375)

        self.power_price_hint = lv.label(card)
        self.power_price_hint.set_text(_t("power_price"))
        self.power_price_hint.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        self.power_price_hint.set_style_text_font(lv.font_montserrat_14, 0)
        self.power_price_hint.set_pos(50, 405)

        _draw_rect(card, 290, 375, 4, 50, THEME["primary"], 2)
        self.power_cost_label = lv.label(card)
        self.power_cost_label.set_text("-- EUR")
        self.power_cost_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.power_cost_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.power_cost_label.set_pos(310, 375)

        self.power_cost_hint = lv.label(card)
        self.power_cost_hint.set_text(_t("monthly_cost"))
        self.power_cost_hint.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        self.power_cost_hint.set_style_text_font(lv.font_montserrat_14, 0)
        self.power_cost_hint.set_pos(310, 405)

        card.remove_flag(lv.obj.FLAG.SCROLLABLE)

    # ------------------------------------------------------------------
    # Waste Card Setup (560x560)
    # ------------------------------------------------------------------

    def _setup_waste_card(self, card, options=None):
        """Set up the waste collection card with main display + 3 previews."""
        self.waste_main_icon_cont = lv.obj(card)
        self.waste_main_icon_cont.set_size(150, 150)
        self.waste_main_icon_cont.set_pos(25, 50)
        self.waste_main_icon_cont.set_style_bg_opa(0, 0)
        self.waste_main_icon_cont.set_style_border_width(0, 0)
        self.waste_main_icon_cont.set_style_pad_all(0, 0)
        self.waste_main_icon_cont.remove_flag(lv.obj.FLAG.CLICKABLE)
        self.waste_main_icon_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)

        self.waste_main_type_label = lv.label(card)
        self.waste_main_type_label.set_text("--")
        self.waste_main_type_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.waste_main_type_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.waste_main_type_label.set_pos(190, 75)

        self.waste_main_days_label = lv.label(card)
        self.waste_main_days_label.set_text("--")
        self.waste_main_days_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.waste_main_days_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.waste_main_days_label.set_pos(190, 120)

        self.waste_main_date_label = lv.label(card)
        self.waste_main_date_label.set_text("")
        self.waste_main_date_label.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        self.waste_main_date_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.waste_main_date_label.set_pos(190, 165)

        overview_title = lv.label(card)
        overview_title.set_text(_t("all_dates"))
        overview_title.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        overview_title.set_style_text_font(lv.font_montserrat_14, 0)
        overview_title.set_pos(370, 55)

        self.waste_overview_rows = []
        for i in range(4):
            row_y = 85 + i * 48
            row = {}
            dot = lv.obj(card)
            dot.set_size(14, 14)
            dot.set_pos(370, row_y + 3)
            dot.set_style_bg_color(lv.color_hex(0x78909C), 0)
            dot.set_style_bg_opa(255, 0)
            dot.set_style_radius(7, 0)
            dot.set_style_border_width(0, 0)
            dot.remove_flag(lv.obj.FLAG.CLICKABLE)
            row["dot"] = dot

            name_lbl = lv.label(card)
            name_lbl.set_text("--")
            name_lbl.set_style_text_color(lv.color_hex(THEME["text"]), 0)
            name_lbl.set_style_text_font(lv.font_montserrat_14, 0)
            name_lbl.set_pos(395, row_y)
            row["name"] = name_lbl

            days_lbl = lv.label(card)
            days_lbl.set_text("")
            days_lbl.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
            days_lbl.set_style_text_font(lv.font_montserrat_14, 0)
            days_lbl.set_pos(395, row_y + 20)
            row["days"] = days_lbl

            self.waste_overview_rows.append(row)

        sep = lv.obj(card)
        sep.set_size(520, 2)
        sep.set_pos(20, 290)
        sep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        sep.set_style_bg_opa(120, 0)
        sep.set_style_border_width(0, 0)
        sep.set_style_radius(1, 0)
        sep.remove_flag(lv.obj.FLAG.CLICKABLE)

        self.waste_preview_cols = []
        col_width = 170
        start_x = (560 - 3 * col_width) // 2

        for i in range(3):
            col_x = start_x + i * col_width
            col = {}

            icon_cont = lv.obj(card)
            icon_cont.set_size(90, 90)
            icon_cont.set_pos(col_x + col_width // 2 - 45, 305)
            icon_cont.set_style_bg_opa(0, 0)
            icon_cont.set_style_border_width(0, 0)
            icon_cont.set_style_pad_all(0, 0)
            icon_cont.remove_flag(lv.obj.FLAG.CLICKABLE)
            icon_cont.remove_flag(lv.obj.FLAG.SCROLLABLE)
            col["icon_container"] = icon_cont

            type_lbl = lv.label(card)
            type_lbl.set_text("--")
            type_lbl.set_style_text_color(lv.color_hex(THEME["text"]), 0)
            type_lbl.set_style_text_font(lv.font_montserrat_14, 0)
            type_lbl.set_pos(col_x + col_width // 2 - 40, 405)
            col["type"] = type_lbl

            days_lbl = lv.label(card)
            days_lbl.set_text("--")
            days_lbl.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
            days_lbl.set_style_text_font(lv.font_montserrat_14, 0)
            days_lbl.set_pos(col_x + col_width // 2 - 40, 430)
            col["days"] = days_lbl

            self.waste_preview_cols.append(col)

    # ------------------------------------------------------------------
    # Calendar Card Setup (730x1070)
    # ------------------------------------------------------------------

    def _setup_value_tile_card(self, card, options=None):
        """Generic widget: shows one entity's state, chosen server-side via
        the widget's own "entity_id" option (widgets.py's WIDGET_VALUE_TILE).

        v1: a single display style (big centered value + unit). The
        card's title is already set by _create_card() from the wire
        "label" - the server resolves that to the bound entity's own
        configured label (see layout.py's _widget_label()), so nothing
        extra is needed here for it.
        """
        options = options or {}
        entity_id = options.get("entity_id") or ""
        card_w = options.get("_card_w") or 300

        value_label = lv.label(card)
        value_label.set_text("?" if not entity_id else "--")
        value_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        value_label.set_style_text_font(lv.font_montserrat_24, 0)
        value_label.set_width(max(40, card_w - 30))
        value_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        value_label.align(lv.ALIGN.CENTER, 0, 10)

        self._value_tiles.append({"entity_id": entity_id, "label": value_label})

    def _setup_clock_card(self, card, options=None):
        """Set up the standalone digital clock card (7-segment digits + date).

        Content (digits + optional seconds + weekday/date) is centered
        both horizontally and vertically within the card, using the
        actual card size passed via options["_card_w"]/["_card_h"] (see
        _build_screen_widgets) - the clock is a free-standing, user-
        placed/resized widget now, it can't assume a fixed card size.
        `options["format"]` selects 24h/12h; `options["show_seconds"]`
        adds a second HH:MM:SS pair of digits (and a second colon).
        """
        options = options or {}
        self._clock_format_12h = options.get("format") == "12h"
        show_seconds = bool(options.get("show_seconds"))
        self._clock_show_seconds = show_seconds

        card_w = options.get("_card_w") or 560
        card_h = options.get("_card_h") or 240

        # Digit: w=90, h=150, seg_w=12. Within a HH/MM/SS pair the digits
        # sit 10px apart; between pairs there's a 46px gap that fits the
        # 16px-wide colon plus margins (10 + 16 + 20) - see the layout
        # this was extracted from (display-client git history).
        digit_w, digit_h, seg_w = 90, 150, 12

        if show_seconds:
            offsets = [0, 100, 236, 336, 472, 572]
            colon_offsets = [200, 436]
            block_w = offsets[-1] + digit_w
        else:
            offsets = [0, 100, 236, 336]
            colon_offsets = [200]
            block_w = offsets[-1] + digit_w

        content_h = 226  # Digit-Hoehe (150) + Wochentag/Datum darunter
        content_x0 = max(0, (card_w - block_w) // 2)
        content_y0 = max(0, (card_h - content_h) // 2)

        self.clock_digits = []
        for dx in offsets:
            segs = _create_7seg_digit(card, content_x0 + dx, content_y0,
                                      digit_w, digit_h, seg_w, THEME["primary"])
            self.clock_digits.append(segs)

        self.clock_colon_dots = []
        for cx in colon_offsets:
            dot1 = _draw_rect(card, content_x0 + cx, content_y0 + 40, 14, 14,
                              THEME["primary"], 7)
            dot2 = _draw_rect(card, content_x0 + cx, content_y0 + 100, 14, 14,
                              THEME["primary"], 7)
            self.clock_colon_dots.append(dot1)
            self.clock_colon_dots.append(dot2)

        # === Date display (centered below clock, same width as the digit block) ===
        self.clock_weekday_label = lv.label(card)
        self.clock_weekday_label.set_text("--")
        self.clock_weekday_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.clock_weekday_label.set_style_text_font(lv.font_montserrat_24, 0)
        self.clock_weekday_label.set_pos(content_x0, content_y0 + 165)
        self.clock_weekday_label.set_width(block_w)
        self.clock_weekday_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self.clock_date_label = lv.label(card)
        self.clock_date_label.set_text("--")
        self.clock_date_label.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
        self.clock_date_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.clock_date_label.set_pos(content_x0, content_y0 + 200)
        self.clock_date_label.set_width(block_w)
        self.clock_date_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

    def _setup_calendar_card(self, card, options=None):
        """Set up the calendar card: month grid(s) + event list.

        `options["months_shown"]` (1 or 2, default 2) controls whether
        the second (next-month) grid is built at all.
        """
        options = options or {}
        try:
            months_shown = int(options.get("months_shown", 2))
        except (TypeError, ValueError):
            months_shown = 2
        self._cal_months_shown = 1 if months_shown == 1 else 2

        # === Calendar Grid (left) + Events (right) ===
        grid_x = 20
        grid_top = 30

        # Month/Year header
        self.cal_month_year_label = lv.label(card)
        self.cal_month_year_label.set_text("-- ----")
        self.cal_month_year_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        self.cal_month_year_label.set_style_text_font(lv.font_montserrat_16, 0)
        self.cal_month_year_label.set_pos(grid_x, grid_top)

        # Weekday headers
        col_w = 50
        for i, day in enumerate(DAY_NAMES):
            lbl = lv.label(card)
            lbl.set_text(day)
            lbl.set_style_text_color(lv.color_hex(THEME["text_secondary"]), 0)
            lbl.set_style_text_font(lv.font_montserrat_14, 0)
            lbl.set_pos(grid_x + i * col_w + 15, grid_top + 35)

        # Day grid cells (6 rows x 7 cols)
        self.cal_grid_cells = []
        for row in range(6):
            for col in range(7):
                cell_x = grid_x + col * col_w
                cell_y = grid_top + 65 + row * col_w
                idx = row * 7 + col

                cell = lv.obj(card)
                cell.set_size(col_w, col_w)
                cell.set_pos(cell_x, cell_y)
                cell.set_style_bg_opa(0, 0)
                cell.set_style_border_width(0, 0)
                cell.set_style_pad_all(0, 0)
                cell.set_style_radius(25, 0)
                cell.remove_flag(lv.obj.FLAG.SCROLLABLE)
                cell.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
                cell.add_flag(lv.obj.FLAG.CLICKABLE)
                cell.add_event_cb(
                    lambda e, i=idx: self._on_cell_tap(i, 0),
                    lv.EVENT.CLICKED, None)

                num_lbl = lv.label(cell)
                num_lbl.set_text("")
                num_lbl.set_style_text_color(lv.color_hex(THEME["text"]), 0)
                num_lbl.set_style_text_font(lv.font_montserrat_14, 0)
                num_lbl.align(lv.ALIGN.CENTER, 0, -4)

                dot = lv.obj(cell)
                dot.set_size(20, 5)
                dot.set_style_bg_color(lv.color_hex(THEME["primary"]), 0)
                dot.set_style_bg_opa(255, 0)
                dot.set_style_radius(2, 0)
                dot.set_style_border_width(0, 0)
                dot.remove_flag(lv.obj.FLAG.CLICKABLE)
                dot.remove_flag(lv.obj.FLAG.SCROLLABLE)
                dot.align(lv.ALIGN.BOTTOM_MID, 0, -2)
                dot.add_flag(lv.obj.FLAG.HIDDEN)

                self.cal_grid_cells.append({
                    "obj": cell, "label": num_lbl, "dot": dot, "day": 0,
                })

        # === Grid 2: Next month (below grid 1) - nur wenn months_shown==2 ===
        self.cal_grid2_month_year_label = None
        self.cal_grid2_cells = []
        if self._cal_months_shown == 2:
            grid2_top = grid_top + 375
            self.cal_grid2_month_year_label = lv.label(card)
            self.cal_grid2_month_year_label.set_text("-- ----")
            self.cal_grid2_month_year_label.set_style_text_color(
                lv.color_hex(THEME["text"]), 0)
            self.cal_grid2_month_year_label.set_style_text_font(
                lv.font_montserrat_16, 0)
            self.cal_grid2_month_year_label.set_pos(grid_x, grid2_top)

            for i, day in enumerate(DAY_NAMES):
                lbl = lv.label(card)
                lbl.set_text(day)
                lbl.set_style_text_color(
                    lv.color_hex(THEME["text_secondary"]), 0)
                lbl.set_style_text_font(lv.font_montserrat_14, 0)
                lbl.set_pos(grid_x + i * col_w + 15, grid2_top + 35)

            for row in range(6):
                for col in range(7):
                    cell_x = grid_x + col * col_w
                    cell_y = grid2_top + 65 + row * col_w
                    idx = row * 7 + col

                    cell = lv.obj(card)
                    cell.set_size(col_w, col_w)
                    cell.set_pos(cell_x, cell_y)
                    cell.set_style_bg_opa(0, 0)
                    cell.set_style_border_width(0, 0)
                    cell.set_style_pad_all(0, 0)
                    cell.set_style_radius(25, 0)
                    cell.remove_flag(lv.obj.FLAG.SCROLLABLE)
                    cell.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
                    cell.add_flag(lv.obj.FLAG.CLICKABLE)
                    cell.add_event_cb(
                        lambda e, i=idx: self._on_cell_tap(i, 1),
                        lv.EVENT.CLICKED, None)

                    num_lbl = lv.label(cell)
                    num_lbl.set_text("")
                    num_lbl.set_style_text_color(
                        lv.color_hex(THEME["text_secondary"]), 0)
                    num_lbl.set_style_text_font(lv.font_montserrat_14, 0)
                    num_lbl.align(lv.ALIGN.CENTER, 0, -4)

                    dot = lv.obj(cell)
                    dot.set_size(20, 5)
                    dot.set_style_bg_color(
                        lv.color_hex(THEME["primary"]), 0)
                    dot.set_style_bg_opa(255, 0)
                    dot.set_style_radius(2, 0)
                    dot.set_style_border_width(0, 0)
                    dot.remove_flag(lv.obj.FLAG.CLICKABLE)
                    dot.remove_flag(lv.obj.FLAG.SCROLLABLE)
                    dot.align(lv.ALIGN.BOTTOM_MID, 0, -2)
                    dot.add_flag(lv.obj.FLAG.HIDDEN)

                    self.cal_grid2_cells.append({
                        "obj": cell, "label": num_lbl, "dot": dot, "day": 0,
                    })

        # === Event list (right of calendar grids) ===
        evt_x = 390
        evt_top = grid_top

        self.cal_event_header = lv.label(card)
        self.cal_event_header.set_text(_t("next_appointments"))
        self.cal_event_header.set_style_text_color(
            lv.color_hex(THEME["text_secondary"]), 0)
        self.cal_event_header.set_style_text_font(lv.font_montserrat_16, 0)
        self.cal_event_header.set_pos(evt_x, evt_top)

        # Vertical separator between grids and events
        sep2 = lv.obj(card)
        sep2.set_size(2, 740)
        sep2.set_pos(375, grid_top)
        sep2.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        sep2.set_style_bg_opa(80, 0)
        sep2.set_style_border_width(0, 0)
        sep2.set_style_radius(1, 0)
        sep2.remove_flag(lv.obj.FLAG.CLICKABLE)

        self.cal_event_items = []
        evt_max = 10
        for i in range(evt_max):
            item_y = evt_top + 40 + i * 65
            item = {}
            bar = _draw_rect(card, evt_x, item_y + 5, 4, 50,
                             EVENT_COLORS[i % len(EVENT_COLORS)], 2)
            item["bar"] = bar

            time_lbl = lv.label(card)
            time_lbl.set_text("")
            time_lbl.set_style_text_color(
                lv.color_hex(THEME["text_secondary"]), 0)
            time_lbl.set_style_text_font(lv.font_montserrat_14, 0)
            time_lbl.set_pos(evt_x + 15, item_y + 5)
            item["time"] = time_lbl

            title_lbl = lv.label(card)
            title_lbl.set_text("")
            title_lbl.set_style_text_color(lv.color_hex(THEME["text"]), 0)
            title_lbl.set_style_text_font(lv.font_montserrat_16, 0)
            title_lbl.set_pos(evt_x + 15, item_y + 28)
            title_lbl.set_width(310)
            item["title"] = title_lbl

            bar.add_flag(lv.obj.FLAG.HIDDEN)
            time_lbl.add_flag(lv.obj.FLAG.HIDDEN)
            title_lbl.add_flag(lv.obj.FLAG.HIDDEN)

            self.cal_event_items.append(item)

        # Build initial grids
        now = time.localtime()
        self._build_month_grid(self.cal_grid_cells,
                               self.cal_month_year_label, now[0], now[1])
        self._cal_display_year = now[0]
        self._cal_display_month = now[1]
        self._cal_display_day = now[2]
        if self.cal_grid2_month_year_label:
            ny, nm = (now[0] + 1, 1) if now[1] == 12 else (now[0], now[1] + 1)
            self._build_month_grid(self.cal_grid2_cells,
                                   self.cal_grid2_month_year_label, ny, nm)
            self._cal_display_year2 = ny
            self._cal_display_month2 = nm

        # Heartbeat-Timer wird zentral in apply_layout() erzeugt, nicht
        # hier - siehe apply_layout()/_update_clock().

    # ------------------------------------------------------------------
    # Calendar Grid
    # ------------------------------------------------------------------

    def _build_month_grid(self, cells, header_label, year, month):
        """Build/rebuild a calendar grid for the given month."""
        month_names_full = MONTH_NAMES_FULL.get(_LANGUAGE, MONTH_NAMES_FULL["de"])
        header_label.set_text(
            _safe_text(month_names_full[month - 1]) + " " + str(year))

        first_wd = _weekday_of_first(year, month)
        num_days = _days_in_month(year, month)

        now = time.localtime()
        today = now[2] if now[0] == year and now[1] == month else -1
        # Use dimmer text for grid 2 (next month)
        is_current = (cells is self.cal_grid_cells)
        txt_color = THEME["text"] if is_current else THEME["text_secondary"]

        day = 1
        for i in range(42):
            cell = cells[i]
            if i < first_wd or day > num_days:
                cell["label"].set_text("")
                cell["day"] = 0
                cell["obj"].set_style_bg_opa(0, 0)
                cell["dot"].add_flag(lv.obj.FLAG.HIDDEN)
                cell["obj"].remove_flag(lv.obj.FLAG.CLICKABLE)
                cell["label"].set_style_text_color(
                    lv.color_hex(txt_color), 0)
            else:
                cell["label"].set_text(str(day))
                cell["day"] = day
                cell["obj"].add_flag(lv.obj.FLAG.CLICKABLE)
                if day == today:
                    cell["obj"].set_style_bg_color(
                        lv.color_hex(THEME["primary"]), 0)
                    cell["obj"].set_style_bg_opa(60, 0)
                    cell["label"].set_style_text_color(
                        lv.color_hex(THEME["primary"]), 0)
                else:
                    cell["obj"].set_style_bg_opa(0, 0)
                    cell["label"].set_style_text_color(
                        lv.color_hex(txt_color), 0)
                cell["dot"].add_flag(lv.obj.FLAG.HIDDEN)
                day += 1

    def _rebuild_both_grids(self):
        """Rebuild both month grids and reset selection."""
        now = time.localtime()
        y, m = now[0], now[1]
        self._cal_display_year = y
        self._cal_display_month = m
        self._cal_display_day = now[2]
        self._build_month_grid(self.cal_grid_cells,
                               self.cal_month_year_label, y, m)
        if self.cal_grid2_month_year_label:
            ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
            self._cal_display_year2 = ny
            self._cal_display_month2 = nm
            self._build_month_grid(self.cal_grid2_cells,
                                   self.cal_grid2_month_year_label, ny, nm)
        self._cal_selected_day = None
        self._cal_selected_cell = None
        self._cal_selected_grid = 0
        if self._cal_events:
            self._update_calendar_dots()

    # ------------------------------------------------------------------
    # Clock Update
    # ------------------------------------------------------------------

    def _update_clock(self):
        """Once-a-second heartbeat.

        Independent of which widgets are actually on the current layout:
        clock digits/date only update if that widget exists, the month
        grid only rebuilds if the calendar widget exists, but the
        reminder check always runs (previously tied to the calendar
        card's timer, so reminders would never fire without it - not
        anymore).
        """
        now = time.localtime()

        if self.clock_digits:
            h = now[3]
            if self._clock_format_12h:
                h = h % 12
                if h == 0:
                    h = 12
            m = now[4]

            _update_7seg_digit(self.clock_digits[0], h // 10)
            _update_7seg_digit(self.clock_digits[1], h % 10)
            _update_7seg_digit(self.clock_digits[2], m // 10)
            _update_7seg_digit(self.clock_digits[3], m % 10)
            if self._clock_show_seconds and len(self.clock_digits) >= 6:
                s = now[5]
                _update_7seg_digit(self.clock_digits[4], s // 10)
                _update_7seg_digit(self.clock_digits[5], s % 10)

            self.clock_colon_visible = not self.clock_colon_visible
            for dot in self.clock_colon_dots:
                if self.clock_colon_visible:
                    dot.remove_flag(lv.obj.FLAG.HIDDEN)
                else:
                    dot.add_flag(lv.obj.FLAG.HIDDEN)

        if self.clock_weekday_label:
            weekday = DAY_NAMES_FULL.get(_LANGUAGE, DAY_NAMES_FULL["de"])[now[6]]
            month_names_full = MONTH_NAMES_FULL.get(_LANGUAGE, MONTH_NAMES_FULL["de"])
            date_str = (str(now[2]) + ". " +
                        month_names_full[now[1] - 1] + " " + str(now[0]))
            self.clock_weekday_label.set_text(_safe_text(weekday))
            self.clock_date_label.set_text(_safe_text(date_str))

        if self._cal_display_year is not None and (
                now[0] != self._cal_display_year or
                now[1] != self._cal_display_month or
                now[2] != self._cal_display_day):
            self._rebuild_both_grids()

        # Check reminders every 30 seconds
        self._reminder_check_counter += 1
        if self._reminder_check_counter >= 30:
            self._reminder_check_counter = 0
            self._check_reminders()

    # ------------------------------------------------------------------
    # Calendar Day Tap
    # ------------------------------------------------------------------

    def _on_cell_tap(self, cell_idx, grid=0):
        """Handle tap on a calendar day cell."""
        cells = self.cal_grid_cells if grid == 0 else self.cal_grid2_cells
        cell = cells[cell_idx]
        day = cell["day"]
        if day == 0:
            return

        # Deselect previous (may be on either grid)
        if self._cal_selected_cell is not None:
            prev_cells = (self.cal_grid_cells if self._cal_selected_grid == 0
                          else self.cal_grid2_cells)
            prev = prev_cells[self._cal_selected_cell]
            prev_y = (self._cal_display_year if self._cal_selected_grid == 0
                      else self._cal_display_year2)
            prev_m = (self._cal_display_month if self._cal_selected_grid == 0
                      else self._cal_display_month2)
            now = time.localtime()
            today = now[2] if (now[0] == prev_y and
                               now[1] == prev_m) else -1
            if prev["day"] == today:
                prev["obj"].set_style_bg_color(
                    lv.color_hex(THEME["primary"]), 0)
                prev["obj"].set_style_bg_opa(60, 0)
            else:
                prev["obj"].set_style_bg_opa(0, 0)

        # Toggle off if same cell tapped again
        if (self._cal_selected_day == day and
                self._cal_selected_grid == grid):
            self._cal_selected_day = None
            self._cal_selected_cell = None
            self._update_event_list()
            return

        self._cal_selected_grid = grid
        self._cal_selected_day = day
        self._cal_selected_cell = cell_idx
        cell["obj"].set_style_bg_color(
            lv.color_hex(THEME["text_secondary"]), 0)
        cell["obj"].set_style_bg_opa(40, 0)
        self._update_event_list(day)

    # ------------------------------------------------------------------
    # Calendar Event Handling
    # ------------------------------------------------------------------

    def _update_calendar_dots(self):
        """Update event dots on both calendar grids."""
        grids = [
            (self.cal_grid_cells, self._cal_display_year,
             self._cal_display_month),
            (self.cal_grid2_cells, self._cal_display_year2,
             self._cal_display_month2),
        ]
        for cells, disp_y, disp_m in grids:
            if not cells or not disp_y:
                continue
            # Map day -> first event index (for color)
            day_colors = {}
            for ev_idx, ev in enumerate(self._cal_events):
                start = ev.get("start", "")
                date_part = start.split("T")[0]
                try:
                    parts = date_part.split("-")
                    y = int(parts[0])
                    mo = int(parts[1])
                    d = int(parts[2])
                    if y == disp_y and mo == disp_m:
                        if d not in day_colors:
                            day_colors[d] = ev_idx
                    if ev.get("all_day"):
                        end = ev.get("end", start)
                        end_part = end.split("T")[0]
                        eparts = end_part.split("-")
                        ey = int(eparts[0])
                        em = int(eparts[1])
                        ed = int(eparts[2])
                        if ey == disp_y and em == disp_m:
                            for dd in range(d, ed):
                                if 1 <= dd <= 31 and dd not in day_colors:
                                    day_colors[dd] = ev_idx
                except Exception:
                    pass
            for cell in cells:
                if cell["day"] > 0 and cell["day"] in day_colors:
                    cidx = day_colors[cell["day"]]
                    color = EVENT_COLORS[cidx % len(EVENT_COLORS)]
                    cell["dot"].set_style_bg_color(
                        lv.color_hex(color), 0)
                    cell["dot"].remove_flag(lv.obj.FLAG.HIDDEN)
                elif cell["day"] > 0:
                    cell["dot"].add_flag(lv.obj.FLAG.HIDDEN)

    def _update_event_list(self, day=None):
        """Update the event list display."""
        if day is not None:
            # Use selected grid's year/month
            if self._cal_selected_grid == 0:
                sel_y = self._cal_display_year
                sel_m = self._cal_display_month
            else:
                sel_y = self._cal_display_year2
                sel_m = self._cal_display_month2
            date_str = (str(sel_y) + "-" +
                        _zfill(sel_m, 2) + "-" +
                        _zfill(day, 2))
            weekday = ""
            try:
                t = time.mktime((sel_y, sel_m,
                                 day, 0, 0, 0, 0, 0, -1))
                lt = time.localtime(t)
                weekday = DAY_NAMES.get(_LANGUAGE, DAY_NAMES["de"])[lt[6]]
            except Exception:
                pass
            month_name = MONTH_NAMES.get(_LANGUAGE, MONTH_NAMES["de"])[sel_m - 1]
            header = (_t("appointments_on") + " " + weekday + ", " +
                      str(day) + ". " + month_name)
            self.cal_event_header.set_text(_safe_text(header))

            filtered = []
            for ev in self._cal_events:
                start = ev.get("start", "")
                start_date = start.split("T")[0]
                if start_date == date_str:
                    filtered.append(ev)
                elif ev.get("all_day"):
                    end = ev.get("end", start)
                    end_date = end.split("T")[0]
                    if start_date <= date_str and end_date >= date_str:
                        filtered.append(ev)
            events = filtered
        else:
            self.cal_event_header.set_text(_t("next_appointments"))
            now = time.localtime()
            today_str = (str(now[0]) + "-" + _zfill(now[1], 2) + "-" +
                         _zfill(now[2], 2))
            now_str = (today_str + "T" + _zfill(now[3], 2) + ":" +
                       _zfill(now[4], 2))
            events = []
            for ev in self._cal_events:
                end = ev.get("end", ev.get("start", ""))
                if "T" not in end:
                    # All-day: end date is exclusive, past if end <= today
                    if end > today_str:
                        events.append(ev)
                else:
                    # Strip timezone offset for comparison
                    if end[:16] >= now_str:
                        events.append(ev)
            events.sort(key=lambda e: e.get("start", ""))

        for i in range(len(self.cal_event_items)):
            item = self.cal_event_items[i]
            if i < len(events):
                ev = events[i]
                item["bar"].remove_flag(lv.obj.FLAG.HIDDEN)
                item["time"].remove_flag(lv.obj.FLAG.HIDDEN)
                item["title"].remove_flag(lv.obj.FLAG.HIDDEN)

                # Use global event index for consistent color with grid dots
                try:
                    ev_idx = self._cal_events.index(ev)
                except ValueError:
                    ev_idx = i
                color = EVENT_COLORS[ev_idx % len(EVENT_COLORS)]
                ev_color = ev.get("color")
                if ev_color and isinstance(ev_color, int):
                    color = ev_color
                item["bar"].set_style_bg_color(lv.color_hex(color), 0)

                if ev.get("all_day"):
                    item["time"].set_text(_t("all_day"))
                else:
                    start = ev.get("start", "")
                    end = ev.get("end", "")
                    st = start.split("T")[1][:5] if "T" in start else ""
                    et = end.split("T")[1][:5] if "T" in end else ""
                    item["time"].set_text(st + " - " + et)

                item["title"].set_text(_safe_text(ev.get("summary", "")))
            else:
                item["bar"].add_flag(lv.obj.FLAG.HIDDEN)
                item["time"].add_flag(lv.obj.FLAG.HIDDEN)
                item["title"].add_flag(lv.obj.FLAG.HIDDEN)

    def update_calendar(self, data):
        """Update calendar card with event data from server."""
        if not self.cal_event_header:
            return
        try:
            self._cal_events = data.get("events", [])
            self._update_calendar_dots()
            if self._cal_selected_day:
                self._update_event_list(self._cal_selected_day)
            else:
                self._update_event_list()
        except Exception as e:
            print("Calendar update error:", e)

    # ------------------------------------------------------------------
    # Medication Page Setup
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Reminder Overlay
    # ------------------------------------------------------------------

    def _create_reminder_overlay(self):
        """Create the floating reminder overlay (hidden initially)."""
        # Full-screen dim background
        self._reminder_dim = lv.obj(self.scr)
        self._reminder_dim.set_size(DISPLAY_WIDTH, DISPLAY_HEIGHT)
        self._reminder_dim.set_pos(0, 0)
        self._reminder_dim.set_style_bg_color(lv.color_hex(0x000000), 0)
        self._reminder_dim.set_style_bg_opa(120, 0)
        self._reminder_dim.set_style_border_width(0, 0)
        self._reminder_dim.set_style_radius(0, 0)
        self._reminder_dim.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self._reminder_dim.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self._reminder_dim.add_flag(lv.obj.FLAG.CLICKABLE)
        self._reminder_dim.add_event_cb(
            lambda e: self._dismiss_reminder(), lv.EVENT.CLICKED, None)
        self._reminder_dim.add_flag(lv.obj.FLAG.HIDDEN)

        # Floating card (centered)
        card_w = 700
        card_h = 280
        card_x = (DISPLAY_WIDTH - card_w) // 2
        card_y = (DISPLAY_HEIGHT - card_h) // 2 - 50

        self._reminder_card = lv.obj(self.scr)
        self._reminder_card.set_size(card_w, card_h)
        self._reminder_card.set_pos(card_x, card_y)
        self._reminder_card.set_style_bg_color(lv.color_hex(0x1a1a3a), 0)
        self._reminder_card.set_style_bg_opa(240, 0)
        self._reminder_card.set_style_radius(20, 0)
        self._reminder_card.set_style_border_width(2, 0)
        self._reminder_card.set_style_border_color(
            lv.color_hex(THEME["primary"]), 0)
        self._reminder_card.set_style_border_opa(200, 0)
        self._reminder_card.set_style_shadow_width(40, 0)
        self._reminder_card.set_style_shadow_color(lv.color_hex(0x000000), 0)
        self._reminder_card.set_style_shadow_opa(150, 0)
        self._reminder_card.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self._reminder_card.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self._reminder_card.add_flag(lv.obj.FLAG.HIDDEN)

        # Bell icon (text) + header
        header_lbl = lv.label(self._reminder_card)
        header_lbl.set_text(_t("reminder"))
        header_lbl.set_style_text_color(lv.color_hex(THEME["primary"]), 0)
        header_lbl.set_style_text_font(lv.font_montserrat_24, 0)
        header_lbl.set_pos(25, 20)

        # Close button (X) - top right (stored on self to prevent GC)
        self._reminder_close_btn = lv.obj(self._reminder_card)
        self._reminder_close_btn.set_size(60, 60)
        self._reminder_close_btn.set_pos(card_w - 75, 5)
        self._reminder_close_btn.set_style_bg_color(lv.color_hex(THEME["error"]), 0)
        self._reminder_close_btn.set_style_bg_opa(60, 0)
        self._reminder_close_btn.set_style_radius(30, 0)
        self._reminder_close_btn.set_style_border_width(0, 0)
        self._reminder_close_btn.add_flag(lv.obj.FLAG.CLICKABLE)
        self._reminder_close_btn.remove_flag(lv.obj.FLAG.SCROLLABLE)
        self._reminder_close_btn.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self._reminder_close_btn.add_event_cb(
            lambda e: self._dismiss_reminder(), lv.EVENT.CLICKED, None)

        x_label = lv.label(self._reminder_close_btn)
        x_label.set_text("X")
        x_label.set_style_text_color(lv.color_hex(THEME["text"]), 0)
        x_label.set_style_text_font(lv.font_montserrat_24, 0)
        x_label.align(lv.ALIGN.CENTER, 0, 0)

        # Separator
        sep = lv.obj(self._reminder_card)
        sep.set_size(card_w - 50, 2)
        sep.set_pos(25, 60)
        sep.set_style_bg_color(lv.color_hex(0x4a4a6a), 0)
        sep.set_style_bg_opa(150, 0)
        sep.set_style_border_width(0, 0)
        sep.remove_flag(lv.obj.FLAG.CLICKABLE)

        # Event title
        self._reminder_title_label = lv.label(self._reminder_card)
        self._reminder_title_label.set_text("")
        self._reminder_title_label.set_style_text_color(
            lv.color_hex(THEME["text"]), 0)
        self._reminder_title_label.set_style_text_font(
            lv.font_montserrat_24, 0)
        self._reminder_title_label.set_pos(25, 80)
        self._reminder_title_label.set_width(card_w - 60)

        # Event time
        self._reminder_time_label = lv.label(self._reminder_card)
        self._reminder_time_label.set_text("")
        self._reminder_time_label.set_style_text_color(
            lv.color_hex(THEME["text_secondary"]), 0)
        self._reminder_time_label.set_style_text_font(
            lv.font_montserrat_16, 0)
        self._reminder_time_label.set_pos(25, 130)

        # "in X Minuten"
        self._reminder_until_label = lv.label(self._reminder_card)
        self._reminder_until_label.set_text("")
        self._reminder_until_label.set_style_text_color(
            lv.color_hex(THEME["warning"]), 0)
        self._reminder_until_label.set_style_text_font(
            lv.font_montserrat_24, 0)
        self._reminder_until_label.set_pos(25, 170)

    def _show_reminder(self, summary, time_str, minutes_until):
        """Show the reminder overlay with event details."""
        self._reminder_title_label.set_text(_safe_text(str(summary)))
        self._reminder_time_label.set_text(str(time_str))

        if minutes_until <= 0:
            self._reminder_until_label.set_text(_t("now"))
            self._reminder_until_label.set_style_text_color(
                lv.color_hex(THEME["error"]), 0)
        elif minutes_until < 60:
            self._reminder_until_label.set_text(
                "in " + str(minutes_until) + " " + _t("in_minutes"))
            self._reminder_until_label.set_style_text_color(
                lv.color_hex(THEME["warning"]), 0)
        else:
            h = minutes_until // 60
            m = minutes_until % 60
            txt = "in " + str(h) + "h"
            if m > 0:
                txt += " " + str(m) + "min"
            self._reminder_until_label.set_text(txt)
            self._reminder_until_label.set_style_text_color(
                lv.color_hex(THEME["warning"]), 0)

        self._reminder_dim.remove_flag(lv.obj.FLAG.HIDDEN)
        self._reminder_card.remove_flag(lv.obj.FLAG.HIDDEN)

        # Auto-close after 2 hours (7200 seconds = 7200000 ms)
        if self._reminder_auto_timer:
            self._reminder_auto_timer.delete()
        self._reminder_auto_timer = lv.timer_create(
            lambda t: self._dismiss_reminder(), 7200000, None)
        self._reminder_auto_timer.set_repeat_count(1)

    def _dismiss_reminder(self):
        """Hide the reminder overlay."""
        if self._reminder_dim:
            self._reminder_dim.add_flag(lv.obj.FLAG.HIDDEN)
        if self._reminder_card:
            self._reminder_card.add_flag(lv.obj.FLAG.HIDDEN)
        if self._reminder_auto_timer:
            self._reminder_auto_timer.delete()
            self._reminder_auto_timer = None

    def _check_reminders(self):
        """Check if any calendar event reminders should fire now."""
        if not self._cal_events:
            return
        try:
            now = time.localtime()
            now_epoch = time.mktime(now)

            for ev in self._cal_events:
                reminder_mins = ev.get("reminder_minutes")
                if not reminder_mins:
                    continue

                start_str = ev.get("start", "")
                if ev.get("all_day"):
                    continue

                event_epoch = self._parse_event_epoch(start_str)
                if event_epoch is None:
                    continue

                summary = ev.get("summary", "Termin")

                for rm in reminder_mins:
                    reminder_epoch = event_epoch - rm * 60
                    # Unique key for this specific reminder
                    rkey = str(start_str) + "|" + str(summary) + "|" + str(rm)

                    if rkey in self._shown_reminders:
                        continue

                    # Fire if we're within the reminder window
                    # (reminder_time <= now < event_start + 5min grace)
                    if reminder_epoch <= now_epoch < event_epoch + 300:
                        mins_until = max(0, int(
                            (event_epoch - now_epoch) / 60))
                        time_display = self._format_event_time(start_str, ev.get("end", ""))
                        self._show_reminder(summary, time_display, mins_until)
                        self._shown_reminders[rkey] = now_epoch
                        return  # Show one at a time

            # Clean old shown reminders (older than 3 hours)
            old_keys = [
                k for k, v in self._shown_reminders.items()
                if now_epoch - v > 10800
            ]
            for k in old_keys:
                del self._shown_reminders[k]

        except Exception as e:
            print("Reminder check error:", e)

    def _parse_event_epoch(self, dt_str):
        """Parse ISO datetime string to epoch seconds."""
        try:
            parts = dt_str.split("T")
            d = parts[0].split("-")
            year, month, day = int(d[0]), int(d[1]), int(d[2])
            hour, minute, second = 0, 0, 0
            if len(parts) > 1:
                # Strip timezone offset (+01:00 or Z)
                t = parts[1]
                if "+" in t:
                    t = t.split("+")[0]
                elif t.endswith("Z"):
                    t = t[:-1]
                elif t.count("-") > 0:
                    # Could be negative offset like -05:00
                    # Take only time part before last -
                    tp_check = t.split(":")
                    if len(tp_check) >= 3 and "-" in tp_check[-1]:
                        t = t.rsplit("-", 1)[0]
                tp = t.split(":")
                hour = int(tp[0])
                minute = int(tp[1])
                if len(tp) > 2:
                    second = int(tp[2].split(".")[0])
            return time.mktime(
                (year, month, day, hour, minute, second, 0, 0))
        except Exception:
            return None

    def _format_event_time(self, start_str, end_str):
        """Format event start/end as readable time string."""
        try:
            s_parts = start_str.split("T")
            e_parts = end_str.split("T") if "T" in end_str else None
            if len(s_parts) > 1:
                s_time = s_parts[1].split("+")[0].split("Z")[0]
                s_hm = s_time[:5]  # "15:30"
                if e_parts and len(e_parts) > 1:
                    e_time = e_parts[1].split("+")[0].split("Z")[0]
                    e_hm = e_time[:5]
                    return s_hm + " - " + e_hm
                return s_hm
            return start_str
        except Exception:
            return str(start_str)

    # ------------------------------------------------------------------
    # Update Methods
    # ------------------------------------------------------------------

    def update_weather_current(self, data):
        """Update weather current card with entity data."""
        if not self.weather_temp_label:
            return
        try:
            # Extract sun state for night detection
            sun_data = data.get("sun.sun")
            if sun_data:
                self._is_night = sun_data.get(
                    "state") == "below_horizon"

            for entity_id, entity_data in data.items():
                # Skip non-weather entities (e.g. sun.sun)
                attrs = entity_data.get("attributes", {})
                if "temperature" not in attrs:
                    continue

                temp = attrs.get("temperature", "--")
                condition = entity_data.get("state", "--")
                humidity = attrs.get("humidity", "--")
                pressure = attrs.get("pressure", "--")
                wind_speed = attrs.get("wind_speed", "--")
                wind_bearing = attrs.get("wind_bearing", None)
                visibility = attrs.get("visibility", "--")
                cloud_coverage = attrs.get("cloud_coverage",
                                           attrs.get("cloudiness", "--"))
                precipitation = attrs.get("precipitation",
                                          attrs.get("rain", "0"))

                self.weather_temp_label.set_text(_fmt1(temp) + " C")
                self.weather_cond_label.set_text(
                    _translate_condition(condition))

                # GTS update
                gts = entity_data.get("gts")
                if gts is not None and self.gts_label:
                    gts_val = int(round(float(gts)))
                    self.gts_label.set_text(str(gts_val))
                    if gts_val >= 200:
                        self.gts_label.set_style_text_color(
                            lv.color_hex(THEME["success"]), 0)
                    else:
                        self.gts_label.set_style_text_color(
                            lv.color_hex(THEME["text"]), 0)

                    # GTS estimate
                    forecast_fc = entity_data.get("forecast")
                    if self.gts_estimate_label:
                        est = _estimate_gts_200(gts_val, forecast_fc)
                        self.gts_estimate_label.set_text(est)

                # Update animated sky scene
                self._update_scene_condition(
                    condition, self._is_night)
                self._current_condition = condition

                self.weather_detail_labels["clouds"].set_text(
                    _fmt1(cloud_coverage) + " %")
                self.weather_detail_labels["humidity"].set_text(
                    _fmt1(humidity) + " %")
                self.weather_detail_labels["precipitation"].set_text(
                    _fmt1(precipitation) + " mm")

                wind_dir = _bearing_to_compass(wind_bearing)
                wind_text = _fmt1(wind_speed) + " km/h"
                if wind_dir:
                    wind_text += " " + wind_dir
                self.weather_detail_labels["wind"].set_text(wind_text)
                self.weather_detail_labels["pressure"].set_text(
                    _fmt1(pressure) + " hPa")
                self.weather_detail_labels["visibility"].set_text(
                    _fmt1(visibility) + " km")

                # Update scene intensity from live data
                self._update_scene_intensity(
                    cloud_coverage, precipitation,
                    wind_speed, visibility)

                forecast = entity_data.get("forecast")
                if forecast:
                    self.update_forecast(forecast)
                break
        except Exception as e:
            print("Weather update error:", e)

    def update_forecast(self, forecast_data):
        """Update the 5-day forecast card."""
        if not self.forecast_cols:
            return
        try:
            if not forecast_data or len(forecast_data) == 0:
                self.forecast_fallback_label.remove_flag(lv.obj.FLAG.HIDDEN)
                for col in self.forecast_cols:
                    col["day"].add_flag(lv.obj.FLAG.HIDDEN)
                    col["icon_container"].add_flag(lv.obj.FLAG.HIDDEN)
                    col["temp"].add_flag(lv.obj.FLAG.HIDDEN)
                    col["precip"].add_flag(lv.obj.FLAG.HIDDEN)
                return

            self.forecast_fallback_label.add_flag(lv.obj.FLAG.HIDDEN)
            days = forecast_data[1:6]
            for i in range(5):
                col = self.forecast_cols[i]
                if i < len(days):
                    day = days[i]
                    col["day"].remove_flag(lv.obj.FLAG.HIDDEN)
                    col["icon_container"].remove_flag(lv.obj.FLAG.HIDDEN)
                    col["temp"].remove_flag(lv.obj.FLAG.HIDDEN)
                    col["precip"].remove_flag(lv.obj.FLAG.HIDDEN)

                    dt = day.get("datetime", "")
                    col["day"].set_text(_get_day_name(dt))

                    t_high = day.get("temperature", "--")
                    t_low = day.get("templow",
                                    day.get("temp_low", "--"))
                    try:
                        t_high = int(round(float(t_high)))
                    except Exception:
                        pass
                    try:
                        t_low = int(round(float(t_low)))
                    except Exception:
                        pass
                    col["temp"].set_text(
                        str(t_high) + "/" + str(t_low) + " C")

                    precip = day.get("precipitation_probability",
                                     day.get("precipitation", "--"))
                    col["precip"].set_text(str(precip) + "%")

                    cond = day.get("condition", "")
                    if cond != self._forecast_conditions[i]:
                        self._forecast_conditions[i] = cond
                        self._redraw_icon(col["icon_container"],
                                          cond, 85, "weather")
                else:
                    col["day"].add_flag(lv.obj.FLAG.HIDDEN)
                    col["icon_container"].add_flag(lv.obj.FLAG.HIDDEN)
                    col["temp"].add_flag(lv.obj.FLAG.HIDDEN)
                    col["precip"].add_flag(lv.obj.FLAG.HIDDEN)
        except Exception as e:
            print("Forecast update error:", e)

    def update_strom(self, data):
        """Update Strom card with all 4 entities."""
        if not self.power_value_label:
            return
        try:
            power = None
            consumption = None
            price = None
            cost = None
            for entity_id, entity_data in data.items():
                state = entity_data.get("state", "--")
                unit = entity_data.get("unit", "")
                eid = entity_id.lower()
                if "leistung" in eid or unit == "W":
                    power = state
                elif ("verbrauch" in eid or "kumuliert" in eid) or unit == "kWh":
                    consumption = state
                elif "preis" in eid or "strompreis" in eid:
                    price = state
                elif "kosten" in eid or "monatlich" in eid:
                    cost = state

            if power is not None:
                try:
                    pw = float(power)
                    if pw >= 1000:
                        whole = int(pw)
                        txt = "{:,}".format(whole).replace(",", ".") + " W"
                    else:
                        txt = str(round(pw, 1)) + " W"
                    self.power_value_label.set_text(txt)
                    if pw < 1000:
                        color = THEME["success"]
                    elif pw < 3000:
                        color = THEME["warning"]
                    else:
                        color = THEME["error"]
                    if color != self._current_power_color:
                        self._current_power_color = color
                        self.power_value_label.set_style_text_color(
                            lv.color_hex(color), 0)
                        self.power_arc.set_style_arc_color(
                            lv.color_hex(color), lv.PART.INDICATOR)
                    pct = min(100, int(pw * 100 / self._power_max_value))
                    self.power_arc.set_value(pct)
                except (ValueError, TypeError):
                    self.power_value_label.set_text(str(power) + " W")

            if consumption is not None:
                try:
                    cv = float(consumption)
                    ci = int(round(cv * 100))
                    cv_str = str(ci // 100) + "." + _zfill(str(ci % 100), 2)
                    self.power_consumption_label.set_text(cv_str + " kWh")
                except (ValueError, TypeError):
                    self.power_consumption_label.set_text(
                        str(consumption) + " kWh")

            if price is not None:
                try:
                    pv = float(price)
                    if pv < 1:
                        pv = pv * 100
                    self.power_price_label.set_text(
                        str(round(pv, 1)) + " ct/kWh")
                except (ValueError, TypeError):
                    self.power_price_label.set_text(
                        str(price) + " ct/kWh")

            if cost is not None:
                try:
                    cv = float(cost)
                    ci = int(round(cv * 100))
                    cv_str = str(ci // 100) + "." + _zfill(str(ci % 100), 2)
                    self.power_cost_label.set_text(cv_str + " EUR")
                except (ValueError, TypeError):
                    self.power_cost_label.set_text(str(cost) + " EUR")
        except Exception as e:
            print("Strom update error:", e)

    def update_waste(self, data):
        """Update waste card with sorted collections + noon rotation."""
        if not self.waste_main_type_label:
            return
        try:
            collections = []
            for entity_id, entity_data in data.items():
                days = entity_data.get("days_until")
                if days is None:
                    continue
                label = entity_data.get("label", entity_id)
                next_date = entity_data.get("next_date", "")
                waste_type = _detect_waste_type(entity_id)
                collections.append((days, label, waste_type, next_date))

            collections.sort(key=lambda x: x[0])

            if collections and collections[0][0] == 0:
                hour = time.localtime()[3]
                if hour >= 12:
                    collections.append(collections.pop(0))

            if not collections:
                return

            main = collections[0]
            main_days, main_label, main_wtype, main_date = main

            self.waste_main_type_label.set_text(_safe_text(main_label))
            self.waste_main_days_label.set_text(
                _format_days_text(main_days))
            self.waste_main_date_label.set_text(
                _format_waste_date(main_date) if main_date else "")

            if main_days == 0:
                self.waste_main_days_label.set_style_text_color(
                    lv.color_hex(THEME["error"]), 0)
            elif main_days == 1:
                self.waste_main_days_label.set_style_text_color(
                    lv.color_hex(THEME["warning"]), 0)
            else:
                self.waste_main_days_label.set_style_text_color(
                    lv.color_hex(THEME["text"]), 0)

            if main_wtype != self._current_waste_type:
                self._current_waste_type = main_wtype
                self._redraw_icon(self.waste_main_icon_cont,
                                  main_wtype, 150, "waste")

            for i in range(4):
                if i < len(collections):
                    c_days, c_label, c_wtype, c_date = collections[i]
                    row = self.waste_overview_rows[i]
                    row["name"].set_text(_safe_text(c_label))
                    row["days"].set_text(_format_days_text(c_days))
                    row["dot"].set_style_bg_color(
                        lv.color_hex(WASTE_COLORS.get(c_wtype, 0x78909C)), 0)

            previews = collections[1:4]
            for i in range(3):
                col = self.waste_preview_cols[i]
                if i < len(previews):
                    p_days, p_label, p_wtype, p_date = previews[i]
                    col["type"].set_text(_safe_text(p_label))
                    col["days"].set_text(_format_days_text(p_days))
                    if p_wtype != self._preview_waste_types[i]:
                        self._preview_waste_types[i] = p_wtype
                        self._redraw_icon(col["icon_container"],
                                          p_wtype, 90, "waste")
                else:
                    col["type"].set_text("")
                    col["days"].set_text("")
        except Exception as e:
            print("Waste update error:", e)

    def _redraw_icon(self, container, icon_type, size, category):
        """Clear and redraw an icon in the given container."""
        child = container.get_child(0)
        while child is not None:
            next_child = container.get_child(0)
            child.delete()
            if next_child == child:
                break
            child = container.get_child(0)
        if category == "waste":
            draw_waste_icon(container, icon_type, size)
        else:
            draw_weather_icon(container, icon_type, size)

    def set_connected(self, connected):
        """Update connection status"""
        self.connected = connected
        if self.status_label:
            if connected:
                self.status_label.set_text(_t("connected"))
                self.status_label.set_style_text_color(
                    lv.color_hex(THEME["success"]), 0)
            else:
                self.status_label.set_text(_t("disconnected"))
                self.status_label.set_style_text_color(
                    lv.color_hex(THEME["error"]), 0)

    def update_indoor(self, data):
        """Update indoor climate labels and comfort gauge."""
        if not self.indoor_temp_label:
            return
        try:
            temp_val = None
            hum_val = None
            for entity_id, entity_data in data.items():
                state = str(entity_data.get('state', '--'))
                if 'temperature' in entity_id:
                    self.indoor_temp_label.set_text(_fmt1(state) + ' C')
                    try:
                        temp_val = float(state)
                    except Exception:
                        pass
                elif 'humidity' in entity_id:
                    self.indoor_hum_label.set_text(_fmt1(state) + ' %')
                    try:
                        hum_val = float(state)
                    except Exception:
                        pass

            # Update comfort gauge
            if self.raumklima_arc and temp_val is not None and hum_val is not None:
                # Comfort score: temp 20-22 ideal, humidity 40-60 ideal
                # Temp score (0-50): 50 if in 20-22, drops off outside
                if 20 <= temp_val <= 22:
                    t_score = 50
                elif temp_val < 20:
                    t_score = max(0, 50 - (20 - temp_val) * 10)
                else:
                    t_score = max(0, 50 - (temp_val - 22) * 10)
                # Humidity score (0-50): 50 if in 40-60, drops off outside
                if 40 <= hum_val <= 60:
                    h_score = 50
                elif hum_val < 40:
                    h_score = max(0, 50 - (40 - hum_val) * 2.5)
                else:
                    h_score = max(0, 50 - (hum_val - 60) * 2.5)
                comfort = int(t_score + h_score)
                self.raumklima_arc.set_value(comfort)

                # Color based on comfort level
                if comfort >= 70:
                    color = THEME["success"]
                    label = "Gut"
                elif comfort >= 40:
                    color = THEME["warning"]
                    label = "OK"
                else:
                    color = THEME["error"]
                    label = "Schlecht"

                if color != self._current_raumklima_color:
                    self._current_raumklima_color = color
                    self.raumklima_arc.set_style_arc_color(
                        lv.color_hex(color), lv.PART.INDICATOR)
                    self.raumklima_index_label.set_style_text_color(
                        lv.color_hex(color), 0)
                self.raumklima_index_label.set_text(label)
        except Exception as e:
            print('Indoor update error:', e)

    def update_custom(self, data):
        """Updates every value_tile widget from the shared "custom" group.

        `data` is keyed by entity_id (like every other group) - each
        value_tile in self._value_tiles picks out just the one entity_id
        its own "entity_id" option named (see _setup_value_tile_card).
        """
        for tile in self._value_tiles:
            entity_data = data.get(tile["entity_id"])
            if not entity_data:
                continue
            state = str(entity_data.get("state", "--"))
            unit = entity_data.get("unit", "")
            text = state + (" " + unit if unit else "")
            tile["label"].set_text(_safe_text(text))

    def process_message(self, msg):
        """Process incoming WebSocket message"""
        try:
            parsed = json.loads(msg)
            msg_type = parsed.get("type")

            if msg_type == "layout_update":
                self.apply_layout(parsed)
                return

            if msg_type == "full_update":
                data = parsed.get("data", {})
                for group, group_data in data.items():
                    self.data[group] = group_data
                    self._dispatch_group_update(group, group_data)
                return

            if msg_type == "entity_update":
                group = parsed.get("group")
                entity_id = parsed.get("entity_id")
                if group and entity_id:
                    self.data.setdefault(group, {})[entity_id] = parsed.get("data", {})
                    self._dispatch_group_update(group, self.data[group])
                return

            # "reminder" wird aktuell nicht ausgewertet - Erinnerungen
            # berechnet der Client selbst aus den gecachten Kalenderdaten
            # (siehe _check_reminders).
        except Exception as e:
            print("Message processing error:", e)

    def _dispatch_group_update(self, group, group_data):
        """Routes one group's data to the matching update_* method."""
        if group == "wetter":
            self.update_weather_current(group_data)
        elif group == "strom":
            self.update_strom(group_data)
        elif group == "abfall":
            self.update_waste(group_data)
        elif group == "kalender":
            self.update_calendar(group_data)
        elif group == "raumklima":
            self.update_indoor(group_data)
        elif group == "custom":
            self.update_custom(group_data)

    # ------------------------------------------------------------------
    # Layout (server-driven screens/widgets)
    # ------------------------------------------------------------------

    def apply_layout(self, layout_msg):
        """Rebuilds screens/cards from a layout_update message.

        Idempotent: the server resends layout_update on every (re)connect,
        so any previously built screens/timers are torn down first.
        """
        try:
            screens = layout_msg.get("screens", [])
            if not screens:
                return

            global _LANGUAGE
            _LANGUAGE = layout_msg.get("language", _LANGUAGE)

            self._delete_timer(self._scene_timer)
            self._scene_timer = None
            self._delete_timer(self._clock_timer)
            self._clock_timer = None

            for dot in self._page_dots:
                dot.delete()
            self._page_dots = []

            for container in self._screen_containers.values():
                container.delete()
            self._screen_containers = {}

            # Widget-Refs zuruecksetzen, bevor neu gebaut wird - sonst
            # zeigen sie nach einem Rebuild ohne dieses Widget (z.B. Uhr
            # aus dem Layout entfernt) auf laengst geloeschte LVGL-Objekte,
            # und der Heartbeat-Timer unten wuerde versuchen, sie trotzdem
            # zu aktualisieren.
            self.clock_digits = []
            self.clock_colon_dots = []
            self.clock_weekday_label = None
            self.clock_date_label = None
            self._cal_display_year = None
            self.weather_card = None
            self.raumklima_card = None
            self.calendar_card = None
            self.power_card = None
            self._value_tiles = []

            # "Did this value change since the last icon/color draw?"
            # guards - separate from the widget refs above, but just as
            # stale after a rebuild: the icon containers/arcs they guard
            # get recreated empty/default-colored, but these would still
            # remember the *old* value and skip redrawing into them,
            # leaving e.g. the waste icon blank until the value actually
            # changes again. Reset alongside the refs for the same reason.
            self._current_condition = None
            self._current_raumklima_color = None
            self._current_power_color = None
            self._current_waste_type = None
            self._preview_waste_types = [None, None, None]
            self._forecast_conditions = [None] * 5

            self._layout_screen_ids = [s.get("id") for s in screens]

            for index, screen in enumerate(screens):
                container = lv.obj(self.scr)
                container.set_size(DISPLAY_WIDTH, DISPLAY_HEIGHT)
                container.set_pos(0, 0)
                container.set_style_bg_opa(0, 0)
                container.set_style_border_width(0, 0)
                container.set_style_pad_all(0, 0)
                container.remove_flag(lv.obj.FLAG.SCROLLABLE)
                container.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
                container.remove_flag(lv.obj.FLAG.CLICKABLE)
                if index != 0:
                    container.add_flag(lv.obj.FLAG.HIDDEN)

                self._build_screen_widgets(container, screen)
                self._screen_containers[screen.get("id")] = container

            self._current_page = 0

            if len(screens) > 1:
                self._create_page_dots(len(screens))
                self._setup_swipe_detection()

            if self.weather_card:
                self._start_scene_timer()

            # Heartbeat-Timer: immer genau einer, unabhaengig davon, ob
            # Uhr/Kalender-Widgets ueberhaupt im Layout sind - siehe
            # _update_clock() fuer die einzeln abgesicherten Teile
            # (Uhr-Digits, Tageswechsel-Rebuild, Reminder-Check).
            self._clock_timer = lv.timer_create(
                lambda t: self._update_clock(), 1000, None)
            self._update_clock()

            # Bereits vorhandene Daten (z.B. bei einem Reconnect, falls ein
            # layout_update mal ohne direkt folgendes full_update kommt)
            # sofort erneut anwenden, statt auf den naechsten Server-Push
            # zu warten.
            for group, group_data in self.data.items():
                self._dispatch_group_update(group, group_data)

            print("Layout applied:", len(screens), "screen(s)")
        except Exception as e:
            print("Layout apply error:", e)

    def _delete_timer(self, timer):
        """Best-effort teardown of an lv.timer_create() handle."""
        if timer is None:
            return
        try:
            timer.delete()
        except Exception:
            try:
                timer.pause()
            except Exception:
                pass

    def _build_screen_widgets(self, container, screen):
        """Creates cards for one screen's widgets, dispatched by widget type.

        The grid describes the content area *below* the always-visible
        header (HEADER_HEIGHT), not the full screen.
        """
        grid = screen.get("grid", {})
        grid_cols = grid.get("cols") or 1
        grid_rows = grid.get("rows") or 1
        cell_w = DISPLAY_WIDTH / grid_cols
        cell_h = (DISPLAY_HEIGHT - HEADER_HEIGHT) / grid_rows

        setup_by_type = {
            "clock": self._setup_clock_card,
            "weather_current": self._setup_weather_card,
            "power_gauge": self._setup_strom_card,
            "waste_next": self._setup_waste_card,
            "indoor_climate": self._setup_raumklima_card,
            "calendar_month": self._setup_calendar_card,
            "value_tile": self._setup_value_tile_card,
        }

        for widget in screen.get("widgets", []):
            widget_type = widget.get("type")
            setup_fn = setup_by_type.get(widget_type)
            if not setup_fn:
                print("Unbekannter Widget-Typ:", widget_type)
                continue

            pos = widget.get("pos", {})
            x = round(pos.get("col", 0) * cell_w)
            y = HEADER_HEIGHT + round(pos.get("row", 0) * cell_h)
            w = round(pos.get("colspan", 1) * cell_w)
            h = round(pos.get("rowspan", 1) * cell_h)
            options = dict(widget.get("options") or {})
            # Kartengroesse mitgeben, statt sie in jedem _setup_*_card per
            # LVGL-Getter neu abzufragen - z.B. fuer die Uhr, die sich
            # unabhaengig von der Kartengroesse zentrieren muss.
            options["_card_w"] = w
            options["_card_h"] = h

            card = self._create_card(container, x, y, w, h, widget.get("label", ""))
            setup_fn(card, options)

            if widget_type == "weather_current":
                self.weather_card = card
            elif widget_type == "indoor_climate":
                self.raumklima_card = card
            elif widget_type == "calendar_month":
                self.calendar_card = card
            elif widget_type == "power_gauge":
                self.power_card = card


# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------

def _ws_encode_frame(payload_bytes, opcode=0x1):
    """Encodes a masked WebSocket frame (RFC 6455 requires client->server
    frames to be masked - the previous hand-rolled pong reply wasn't,
    which the server's `websockets` library likely treated as a protocol
    violation and closed the connection over, explaining the ~30s
    reconnect cycles observed since early in this project)."""
    mask = bytes([random.getrandbits(8) for _ in range(4)])
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload_bytes))
    length = len(payload_bytes)
    header = bytearray()
    header.append(0x80 | opcode)  # FIN + opcode
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header += length.to_bytes(2, 'big')
    else:
        header.append(0x80 | 127)
        header += length.to_bytes(8, 'big')
    header += mask
    return bytes(header) + masked


async def websocket_client(display):
    """Simple WebSocket client for MicroPython"""
    while True:
        sock = None
        try:
            print("Connecting to ws://" + INFOHUB_HOST + ":" +
                  str(INFOHUB_PORT) + "...")

            sock = socket.socket()
            sock.setblocking(True)
            addr = socket.getaddrinfo(INFOHUB_HOST, INFOHUB_PORT)[0][-1]
            sock.connect(addr)

            key = "dGhlIHNhbXBsZSBub25jZQ=="
            request = (
                "GET / HTTP/1.1\r\n"
                "Host: " + INFOHUB_HOST + ":" + str(INFOHUB_PORT) + "\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Key: " + key + "\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            )
            sock.send(request.encode())

            response = sock.recv(1024).decode()
            if "101" in response:
                print("WebSocket connected")
                display.set_connected(True)

                hello = json.dumps({"type": "hello", "device_id": DEVICE_ID}).encode()
                sock.send(_ws_encode_frame(hello))

                sock.setblocking(False)

                buffer = b""
                last_data_time = time.time()
                while True:
                    try:
                        # Stale connection check: no data for 60s
                        if time.time() - last_data_time > 60:
                            print("No data for 60s, reconnecting")
                            break

                        try:
                            data = sock.recv(1024)
                            if data:
                                buffer += data
                                last_data_time = time.time()
                        except OSError as e:
                            if e.args[0] != 11:
                                raise

                        while len(buffer) >= 2:
                            fin = buffer[0] & 0x80
                            opcode = buffer[0] & 0x0f
                            masked = buffer[1] & 0x80
                            length = buffer[1] & 0x7f

                            header_len = 2
                            if length == 126:
                                if len(buffer) < 4:
                                    break
                                length = (buffer[2] << 8) | buffer[3]
                                header_len = 4
                            elif length == 127:
                                if len(buffer) < 10:
                                    break
                                length = int.from_bytes(
                                    buffer[2:10], 'big')
                                header_len = 10

                            if masked:
                                header_len += 4

                            total_len = header_len + length
                            if len(buffer) < total_len:
                                break

                            if masked:
                                mask = buffer[header_len - 4:header_len]
                                payload = buffer[header_len:total_len]
                                payload = bytes(
                                    b ^ mask[i % 4]
                                    for i, b in enumerate(payload))
                            else:
                                payload = buffer[header_len:total_len]

                            buffer = buffer[total_len:]

                            if opcode == 1:
                                msg = payload.decode()
                                display.process_message(msg)
                            elif opcode == 8:
                                print("Server closed connection")
                                raise Exception("Connection closed")
                            elif opcode == 9:
                                sock.send(_ws_encode_frame(payload, opcode=0xA))

                        lv.timer_handler()
                        await asyncio.sleep(0.05)

                    except Exception as e:
                        if ("EAGAIN" not in str(e) and
                                "11" not in str(e)):
                            print("Receive error:", e)
                            break
            else:
                print("Handshake failed")

        except Exception as e:
            print("Connection error:", e)
            display.set_connected(False)
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass

        for _ in range(50):
            lv.timer_handler()
            await asyncio.sleep(0.1)
        print("Reconnecting...")


async def lvgl_timer():
    """LVGL timer handler task"""
    while True:
        lv.timer_handler()
        await asyncio.sleep(0.02)


async def main():
    """Main entry point"""
    print("InfoHub Display Client starting...")

    display = InfoHubDisplay()
    display.init_display()
    display.create_ui()
    display.init_touch()

    await asyncio.gather(
        websocket_client(display),
        lvgl_timer()
    )


if __name__ == "__main__":
    asyncio.run(main())
