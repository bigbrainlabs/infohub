# InfoHub

A Home Assistant custom integration that turns a Raspberry Pi (or similar
Linux-capable board) with a touch display into a fully server-configured
smart-home info panel - clock, weather, power usage, waste-collection
reminders, indoor climate and Google Calendar, all pushed live from Home
Assistant over a lightweight WebSocket protocol.

Unlike a Lovelace dashboard shown in a kiosk browser, the display client
here is a small standalone app (MicroPython + [LVGL](https://lvgl.io/))
running directly against the framebuffer - no browser, no X11. The
integration owns the *layout*: you design each screen with a drag-and-drop
grid editor in Home Assistant's sidebar, and the display just renders
whatever layout it's told, live, with no redeploy needed.

## Why this exists

Built for a Raspberry Pi Zero 2W driving a 10" HDMI touch display as a
kitchen/hallway info panel. Multiple displays are supported: each one
identifies itself with a stable device ID, and you assign it a specific
panel layout from a dropdown - one shared Home Assistant data stream,
per-device layout.

There's no off-the-shelf HA extension that does exactly this (checked
against [openHASP](https://github.com/HASwitchPlate/openHASP) and
[ESPHomeDesigner](https://github.com/hstjrmin/esphome-displayeditor-app) -
both are closer to compile-and-flash ESPHome/MQTT setups than a live,
server-driven WebSocket panel with a native HA sidebar editor).

## Architecture

```
Home Assistant
  +-- custom_components/infohub/   HA integration
  |     - reads hass.states (push, not polling)
  |     - polls Google Calendar (calendar.get_events) and an external
  |       GTS (Gruenlandtemperatursumme) API on a timer
  |     - sidebar panel: manage "Panels" (named layouts), assign
  |       entities and widgets per panel, assign a panel to a device
  |     - runs its own WebSocket server (separate port, no HA auth
  |       needed) and pushes layout_update / full_update / entity_update
  |
  +-- display-client/main_mp.py    MicroPython + LVGL client
        - connects to the integration's WebSocket server
        - identifies itself with a device ID (hello message)
        - renders whatever layout_update it receives - no hardcoded UI
```

## Features

- **Server-configured layout**: design screens visually (24x14 grid) in
  Home Assistant's sidebar - no code, no redeploy of the display client.
- **Widgets**: clock, current weather (with an animated day/night sky
  scene), power gauge, indoor climate, next waste collection, calendar
  month, an Info Tile (shows any entities you assign it, one per row),
  and Switches (same idea, but each row is a tappable toggle, an
  Auf/Stop/Zu button trio for covers, or a drag-to-set slider with
  configurable min/max, picked per entity) - each with its own
  per-widget options (clock format/seconds, weather scene on/off, gauge
  max value, months shown).
- **Multiple panels, multiple displays**: define as many named panel
  layouts as you like and assign each physical display to one via a
  dropdown, keyed off a stable per-device ID.
- **Push-based data**: entity changes are read straight from
  `hass.states` and pushed live - no REST polling loop.
- **Google Calendar** via Home Assistant's own Google Calendar
  integration (`calendar.get_events`), plus an external GTS API poller
  for gardeners.

## Requirements

- Home Assistant 2024.1 or newer.
- A display client: the reference implementation
  (`display-client/main_mp.py`) targets a Linux-hosted MicroPython+LVGL
  build (framebuffer + evdev touch) - see
  [`display-client/README.md`](display-client/README.md) for hardware
  and deployment notes. The wire protocol is plain JSON over WebSocket,
  so any client capable of that (including a future ESP32/bare-metal
  build) can implement it instead.

## Installation

1. Copy `custom_components/infohub` into your Home Assistant
   `config/custom_components/` directory (or install via HACS as a
   custom repository, once added there).
2. Restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> **InfoHub**.
   The only thing asked at setup is the WebSocket port the display
   clients will connect to (default `8765`).
4. A new **InfoHub** entry appears in the sidebar. Use it to create one
   or more Panels: pick the entities each panel should track, and lay
   out widgets on the grid editor.
5. Point your display client at `ws://<home-assistant-host>:<ws_port>`.

Further per-instance options (GTS postcode/country, the Google Calendar
entity to poll, poll intervals) are under the integration's own
**Configure** dialog.

## Wire protocol (short version)

Every connecting client may send a `hello` message to identify itself:

```json
{"type": "hello", "device_id": "infopanel1"}
```

The server resolves that device ID to an assigned panel (or the default
panel if none is assigned / no hello was sent) and sends that panel's
layout:

```json
{"type": "layout_update", "screens": [...]}
```

Live data then streams as `full_update` (initial snapshot / bulk
changes) and `entity_update` (single-entity changes), grouped by the
same group keys (`wetter`, `strom`, `abfall`, `raumklima`, `kalender`,
plus `custom` and `aktoren` for the Info Tile and Switches widgets)
used in the layout's `data_source` fields. Switches also accept an
`action` message from the client to toggle an entity - see
`websocket_server.py`.

## License

MIT - see [LICENSE](LICENSE).
