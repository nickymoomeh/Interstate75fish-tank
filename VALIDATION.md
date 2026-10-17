# Validation

47 host tests pass using Python 3.14.8. Coverage includes scene palette bounds, deterministic and clipped visitors, fish species/colours, day/night colours, submarine directions and lights, cached sprites, background reference frames, display row changes, palette transitions, foliage composition, reproducible baked assets, corrupted-asset fallback, clock validation and schedule boundaries, feeding once per slot across midnight, soft-reset RTC reading, button debounce/hold suppression/tick wrap, and prohibited connectivity imports.

`aquarium.py` is byte-identical to the inspected renderer. The background file is rebuilt from its procedural artwork rather than downloaded. Connected updater tests were excluded because that subsystem is removed. Python syntax checks cover all shipped Python files. These checks do not execute MicroPython native/viper compilation or establish physical display performance.

## Physical acceptance (pending; no board available)

- Boot with no access point available; verify that the aquarium starts and USB remains accessible.
- Check panel order, colours, dimensions and power arrangement. Observe frame rate, free memory and a sustained run, including the procedural fallback with backgrounds.bin temporarily absent.
- Tap A and B; confirm submarine variants and automatic/day/night cycling. Confirm fish, visitors, ornaments and foliage in both palettes.
- Hold A; verify hour and minute wrap, save with hold A, cancel with hold B, and no extra submarine/palette action after a hold. Verify return from settings redraws the complete aquarium without stale text.
- Set 06:59 and 19:59; verify 07:00 day and 20:00 night in automatic mode. Set 23:59 and verify midnight rollover.
- Set just before :15 and :45; observe each feeding animation once, including across midnight.
- Soft reset while powered and verify continued time. Disconnect all power and verify clock setting is available after reboot; set time again.
- Check USB interruption/recovery and reinstall a known-good local snapshot if needed. There is no remote updater or rollback layer.

API reference checked against Pimoroni's Interstate75 documentation:
https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/modules_py/interstate75.md
