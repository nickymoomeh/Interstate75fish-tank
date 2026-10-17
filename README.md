# Fish Tank Offline

An animated 128 × 64 aquarium for Pimoroni Interstate 75 W (RP2350), driving two 64 × 64 HUB75 panels side by side. Runs without internet access, accounts, credentials, or network packages.

The shared aquarium renderer is preserved: resident fish and visitors, jellyfish, night anglerfish and ghost, submarine variants, bubbles, animated foliage/coral, snail, hermit crab, oyster/pearl, treasure chest, day/night palettes and feeding animations. Cached backgrounds retain the existing repeating foliage loop. Feeding starts at local :15 and :45 for 28 seconds. Target frame rate is 15 FPS; actual board performance has not been measured for this variant.

## Installation

1. Use Pimoroni MicroPython firmware for your exact Interstate 75 W RP2350 board, including `interstate75`, PicoGraphics and HUB75 support. The source runtime targeted firmware v0.0.5; this variant still requires physical acceptance testing. See [firmware releases](https://github.com/pimoroni/interstate75/releases) and [Pimoroni's setup guide](https://learn.pimoroni.com/article/getting-started-with-interstate-75). Generic Pico firmware is insufficient.
2. Back up the board's current files over USB. Use a clean filesystem for this standalone project; an existing connected installation may leave network startup code or credentials behind. Keep Pimoroni's supplied `boot.py`, which configures the firmware heap. Inspect any custom `boot.py` for old application/network startup code.
3. With Thonny's MicroPython USB connection, stop the running application and copy these six files to the board root: `main.py`, `runtime.py`, `aquarium.py`, `tank_clock.py`, `tank_controls.py`, `backgrounds.bin`. Copy `main.py` last. No other project files are needed on the board.
4. Reset the board. Hold A to set local time. Reset the clock after a complete power loss.

Use the correct panel wiring and a suitable regulated 5V supply per Pimoroni's guide. `BRIGHTNESS = 0.8` in `runtime.py` scales colours; it is not a current limiter. Size power and wiring for the panels and avoid backfeeding between supplies.

## Board controls

| Action | Aquarium | Clock editor |
| --- | --- | --- |
| Tap A | Launch submarine; alternate direction and cycle colours | Advance hour, wrapping 23 → 00 |
| Tap B | Cycle automatic → day → night → automatic | Advance minute, wrapping 59 → 00 |
| Hold A for 1.2 seconds | Open clock editor | Save hours/minutes, reset seconds to zero, return |
| Hold B for 1.2 seconds | No action | Cancel edits and return |

Holds do not emit an extra tap. The buttons use 40 ms debounce. Release between actions. Animations are hidden during editing and resume at elapsed animation time. Automatic night hours are 20:00–06:59; an unset clock starts in night mode. Manual palette overrides remain until cycled back to automatic or reset.

The RTC stores local wall time. There is no timezone conversion or automatic daylight-saving adjustment; use the buttons when clocks change. Setting an unset RTC supplies a nominal date solely for midnight rollover. No accurate calendar date is claimed. The clock should survive a normal soft reset while powered; no battery-backed retention is assumed. After loss of power, set it again. No flash writes are used for clock settings, and saved hours/minutes are not replayed as if time had stopped during an outage.

## Desktop preview and checks

Python 3 with Tkinter and Pillow can run `python3 emulator.py`. Install Pillow with `python3 -m pip install Pillow` if needed. Preview keys: Space pause, N day/night, A automatic, S submarine, F feed, P performance, Esc quit. The preview uses the same scene engine; it does not emulate the physical clock editor or board performance.

Run `python3 -m unittest discover -s tests -v` from this directory. Rebuild the included background asset using `python3 bake_backgrounds.py`; it is generated from the renderer, with palette and payload integrity checks. A damaged or absent asset triggers the procedural background fallback.

See [RELEASE.md](RELEASE.md) for licensing and release gates and [VALIDATION.md](VALIDATION.md) for test scope. Licensed under MIT; see LICENSE. This is a release candidate pending board checks and final provenance review.
