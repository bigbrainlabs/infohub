# InfoHub Display Client (MicroPython + LVGL)

Reference display client for [InfoHub](../README.md). A single
MicroPython script that renders whatever `layout_update` it receives
from the InfoHub Home Assistant integration - no hardcoded screens, no
local configuration of what to show.

## Hardware (reference setup)

- Raspberry Pi Zero 2W
- 10" HDMI touch display, 1920x1200 (adjust `DISPLAY_WIDTH` /
  `DISPLAY_HEIGHT` at the top of `main_mp.py` for a different panel)
- A MicroPython build with the [LVGL binding](https://github.com/lvgl/lv_binding_micropython)
  for Linux, drawing to the framebuffer (`/dev/fb0`) with `evdev` touch
  input - this is **not** a bare-metal ESP32 target, it runs on top of a
  full Linux userland.

The protocol is plain JSON over WebSocket, so any client that can speak
it works - this file is one reference implementation, not the only
possible one.

## Configuration

There is no config file - the handful of settings a deployment needs
are constants at the top of `main_mp.py`:

```python
INFOHUB_HOST = "192.168.2.49"   # Home Assistant host
INFOHUB_PORT = 8765             # matches the integration's ws_port
DISPLAY_WIDTH = 1920
DISPLAY_HEIGHT = 1200
```

`DEVICE_ID` is derived automatically from `os.uname().nodename` (the
device's hostname) and sent as part of the client's `hello` message on
connect - this is what lets you assign a specific panel layout to this
device from the InfoHub sidebar panel's device dropdown. Set the
hostname you want before deploying, or edit the hardcoded fallback in
`main_mp.py` if `os.uname()` isn't available on your MicroPython build.

## Deployment

```bash
scp display-client/main_mp.py pi@<display-host>:/home/pi/display-client/main_mp.py
```

Run it under whatever supervises MicroPython on your image (systemd,
an init script, etc.) so it restarts automatically - e.g. a systemd
unit along these lines, adjusted for your MicroPython binary's actual
path and any framebuffer/input group requirements your image needs:

```ini
[Unit]
Description=InfoHub Display Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/display-client
ExecStart=/usr/bin/micropython main_mp.py
Restart=always
RestartSec=5
SupplementaryGroups=video input
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

- **Blank screen / no connection**: check `INFOHUB_HOST`/`INFOHUB_PORT`
  match the integration's configured `ws_port`, and that the display
  can reach that host/port.
- **Touch not working**: confirm the evdev touch device path your LVGL
  build is configured to read from matches the actual device (see
  `/proc/bus/input/devices` on the display host).
- **Framebuffer access denied**: the user running the client needs
  access to `/dev/fb0` (typically the `video` group).
