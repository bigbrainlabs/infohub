# InfoHub Display Client (MicroPython + LVGL)

Reference display client for [InfoHub](../README.md). A single
MicroPython script that renders whatever `layout_update` it receives
from the InfoHub Home Assistant integration - no hardcoded screens, no
local configuration of what to show.

## Hardware (reference setup)

- Raspberry Pi Zero 2W
- 10" HDMI touch display, 1920x1200 (adjust `DISPLAY_WIDTH` /
  `DISPLAY_HEIGHT` at the top of `main_mp.py` for a different panel)
- A MicroPython build with LVGL built in ([lvgl/lv_micropython](https://github.com/lvgl/lv_micropython),
  see "Building the MicroPython + LVGL runtime" below) for Linux,
  drawing to the framebuffer (`/dev/fb0`) with `evdev` touch input -
  this is **not** a bare-metal ESP32 target, it runs on top of a full
  Linux userland.

The protocol is plain JSON over WebSocket, so any client that can speak
it works - this file is one reference implementation, not the only
possible one.

## Building the MicroPython + LVGL runtime

`main_mp.py` needs a MicroPython binary with LVGL built in - it's
**not** something `pip install`s or runs under stock MicroPython. This
section wasn't captured when the reference setup was first built, so
it's reconstructed here from the actual running binary (version string,
compiled-in modules) plus [LVGL's own docs](https://docs.lvgl.io/) -
treat it as a solid starting point, not a guaranteed-exact transcript.
Verify each step against the current upstream repo before relying on it.

The deployed binary identifies as `MicroPython v1.24.1`, unix port, with
`lvgl`, `lv_timer`, `lv_utils`, `display_driver`, `display_driver_utils`,
`fs_driver`, `evdev` and `framebuf` built in - i.e. it comes from
[lvgl/lv_micropython](https://github.com/lvgl/lv_micropython) (the
MicroPython fork with LVGL's binding already wired in), built for
Linux framebuffer output + evdev touch input rather than the SDL
demo driver most of its own docs default to. LVGL's docs confirm this
exact combination (unix port + framebuffer + evdev) is the documented
way to run it on a Raspberry Pi Zero 2 - see their
[Linux framebuffer driver](https://docs.lvgl.io/master/integration/embedded_linux/drivers/fbdev.html)
and [evdev driver](https://docs.lvgl.io/master/integration/embedded_linux/drivers/evdev.html) pages.

Starting point, per [lv_micropython's README-LVGL.md](https://github.com/lvgl/lv_micropython/blob/master/README-LVGL.md):

```bash
# On a fresh Raspberry Pi OS (64-bit) install, via Raspberry Pi Imager:
sudo apt-get install build-essential libreadline-dev libffi-dev git \
  pkg-config libsdl2-2.0-0 libsdl2-dev python3 parallel

git clone https://github.com/lvgl/lv_micropython.git
cd lv_micropython
make -C mpy-cross
make -C ports/unix submodules
make -C ports/unix
# -> ports/unix/build-standard/micropython (rename/copy to
#    micropython-lvgl, or point the systemd unit at it directly)
```

That base build defaults to the SDL display/input drivers (for
developing on a desktop without real hardware). Swapping in the
framebuffer + evdev drivers for real hardware is exactly what the two
LVGL docs pages linked above walk through - `display_driver`/
`fs_driver`/`lv_utils` in the module list above are the pure-Python
helper modules those pages have you wire up. This is the one part that
couldn't be verified against the original build log, so budget time to
work through it interactively rather than expecting it to be a single
copy-paste.

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
scp display-client/main_mp.py <user>@<display-host>:/home/<user>/display-client/main_mp.py
```

Run it under systemd so it restarts automatically - this is the actual
unit used on the reference Zero 2W (`micropython-lvgl` being the
binary built in the previous section, copied alongside `main_mp.py`):

```ini
[Unit]
Description=InfoHub LVGL Display Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<user>
Group=<user>
WorkingDirectory=/home/<user>/display-client
ExecStart=/home/<user>/display-client/micropython-lvgl /home/<user>/display-client/main_mp.py
Restart=always
RestartSec=5
SupplementaryGroups=video input
StandardOutput=journal
StandardError=journal
SyslogIdentifier=display-client

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
