"""Fish Tank Mk I on Interstate 75 W RP2350 (v0.0.5).

RTC stores local wall time; the buttons set hours and minutes.
Brightness is RGB scaling, not a current limiter. No Wi-Fi credentials required.
"""
import gc
import time
import aquarium
from tank_clock import FeedingSchedule

TARGET_FPS = 15
BRIGHTNESS = 0.8
REPORT_MS = 10000

try:
    import micropython
except ImportError:
    class micropython:
        @staticmethod
        def native(function):
            return function
        viper = native

    def ptr8(buffer):
        return buffer

NIGHT_START = 20 * 60
NIGHT_END = 7 * 60


def scheduled_night(wall_time):
    # MicroPython's unset RTC commonly starts in 2021 (or 2000).
    if wall_time[0] < 2025:
        return True
    minutes = wall_time[3] * 60 + wall_time[4]
    return minutes >= NIGHT_START or minutes < NIGHT_END


def make_pens(graphics, brightness=BRIGHTNESS):
    """Cache both palettes and all four lantern phases; no per-frame pens."""
    if not 0 < brightness <= 1.0:
        raise ValueError("Hardware brightness must be in (0, 1.0]")
    return tuple(tuple(tuple(graphics.create_pen(
        int(r * brightness), int(g * brightness), int(b * brightness))
        for r, g, b in aquarium.palette_at(phase / 1.8 + 0.01, night))
        for phase in range(4)) for night in (False, True))


@micropython.viper
def changed_runs(current, previous, palette_dirty, commands, offset: int, full: int) -> int:
    """Scan one 128-pixel row; output compact (x, width, index) commands.

    Buffers are owned by IndexedDisplay: two 8192-byte frames, a 256-byte
    palette mask, and 384 bytes of commands (128 worst-case runs).
    """
    pixels = ptr8(current)
    old = ptr8(previous)
    dirty = ptr8(palette_dirty)
    out = ptr8(commands)
    x = 0
    count = 0
    while x < 128:
        index = int(pixels[offset + x])
        if full == 0 and index == int(old[offset + x]) and int(dirty[index]) == 0:
            x += 1
            continue
        end = x + 1
        while end < 128 and int(pixels[offset + end]) == index:
            end += 1
        out[count] = x
        out[count + 1] = end - x
        out[count + 2] = index
        count += 3
        x = end
    return count


@micropython.viper
def overlay_foliage(frame, foliage):
    target = ptr8(frame)
    source = ptr8(foliage)
    for offset in range(8192):
        index = int(source[offset])
        if index != 255:
            target[offset] = index


@micropython.viper
def overlay_sprite(frame, commands, length: int):
    target = ptr8(frame)
    source = ptr8(commands)
    for at in range(0, length, 3):
        offset = int(source[at + 1]) * 128 + int(source[at])
        target[offset] = source[at + 2]


class IndexedDisplay:
    def __init__(self, graphics):
        self.graphics = graphics
        self.buffer = bytearray(aquarium.WIDTH * aquarium.HEIGHT)
        self.previous = bytearray(len(self.buffer))
        self.previous_pens = None
        self.palette_dirty = bytearray(256)
        self.commands = bytearray(128 * 3)

    @micropython.native
    def pixel(self, x, y, index):
        self.buffer[y * aquarium.WIDTH + x] = index

    @micropython.native
    def draw(self, pens):
        # Most of a cached backdrop is unchanged. Repaint only changed
        # indices or pixels whose palette colour changed (lantern/night).
        previous = self.previous
        previous_pens = self.previous_pens
        dirty = self.palette_dirty
        full = previous_pens is None
        for index in range(len(pens)):
            dirty[index] = full or pens[index] != previous_pens[index]
        buffer = self.buffer
        set_pen = self.graphics.set_pen
        rectangle = self.graphics.rectangle
        width = aquarium.WIDTH
        last_pen = None
        for y in range(aquarium.HEIGHT):
            offset = y * width
            commands = self.commands
            count = changed_runs(buffer, previous, dirty, commands, offset, int(full))
            for at in range(0, count, 3):
                pen = pens[commands[at + 2]]
                if pen != last_pen:
                    set_pen(pen)
                    last_pen = pen
                rectangle(commands[at], y, commands[at + 1], 1)
        previous[:] = buffer
        self.previous_pens = pens


class BackgroundCache:
    """Build the next complete scenery frame without a long frame stall."""
    def __init__(self):
        self.front = bytearray(aquarium.WIDTH * aquarium.HEIGHT)
        self.back = bytearray(len(self.front))
        self.steps = None

    @micropython.native
    def pixel(self, x, y, index):
        self.back[y * aquarium.WIDTH + x] = index

    def water_row(self, y, row):
        offset = y * aquarium.WIDTH
        self.back[offset:offset + aquarium.WIDTH] = row

    def initialise(self, seconds, night):
        for _ in aquarium.background_steps(seconds, self.pixel, night, self.water_row, plants=False, ornaments=False):
            pass
        self.front, self.back = self.back, self.front

    def advance(self, seconds, night):
        if self.steps is None:
            self.steps = aquarium.background_steps(seconds, self.pixel, night, self.water_row, plants=False, ornaments=False)
        # One bounded scenery unit each foreground frame. The generator
        # owns a fixed timestamp, avoiding seams in the completed backdrop.
        try:
            next(self.steps)
        except StopIteration:
            self.front, self.back = self.back, self.front
            self.steps = None


def draw_settings(graphics, board, hour, minute):
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    graphics.set_pen(graphics.create_pen(85, 100, 110))
    graphics.text("SET LOCAL TIME", 2, 0, scale=1)
    graphics.text("%02d:%02d" % (hour, minute), 12, 13, scale=2)
    graphics.text("A hours B minutes", 2, 36, scale=1)
    graphics.text("Hold A save", 2, 46, scale=1)
    graphics.text("Hold B cancel", 2, 55, scale=1)
    board.update()


def main():
    from interstate75 import Interstate75, DISPLAY_INTERSTATE75_128X64, SWITCH_A, SWITCH_B

    import machine
    from tank_clock import Clock
    from tank_controls import Buttons

    clock = Clock(machine.RTC(), print)
    feeding = FeedingSchedule(print)
    controls = Buttons()
    board = Interstate75(display=DISPLAY_INTERSTATE75_128X64)
    graphics = board.display
    if graphics.get_bounds() != (aquarium.WIDTH, aquarium.HEIGHT):
        raise ValueError("Expected 128x64 display")
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    board.update()
    pens = make_pens(graphics)
    indexed = IndexedDisplay(graphics)
    if aquarium.load_backgrounds():
        background = None
        print("Background: 4 pre-rendered frames, 32 KiB RAM")
    else:
        print("Background fallback: " + str(aquarium._BAKED_ERROR))
        background = BackgroundCache()
        background.initialise(0, clock.night())
    pixel = indexed.pixel
    render = aquarium.render
    ticks_ms, ticks_us, ticks_diff = time.ticks_ms, time.ticks_us, time.ticks_diff
    previous = report_start = ticks_ms()
    elapsed_ms = 0
    frames = render_us = draw_us = update_us = 0
    override = None
    submarine_at = None
    submarine_direction = -1
    submarine_colour = -1
    clock_edit = False
    edit_hour = edit_minute = 0
    screen_dirty = True
    was_screen = False
    print("Fish Tank: 128x64, RGB brightness 80%, target 15 FPS")
    print("Tap A: submarine; tap B: auto/day/night")
    print("Hold A: clock settings; hold B in editor: cancel")
    print("Clock source: " + clock.source)
    gc.collect()
    try:
        while True:
            start = ticks_ms()
            elapsed_ms += ticks_diff(start, previous)
            previous = start
            seconds = elapsed_ms / 1000
            events = controls.poll((board.switch_pressed(SWITCH_A),
                                    board.switch_pressed(SWITCH_B)), start)
            for i, action in events:
                if i == 0 and action == "hold":
                    if clock_edit:
                        try:
                            clock.set_hm(edit_hour, edit_minute)
                            clock_edit = False
                        except ValueError as error:
                            print(str(error))
                    else:
                        local = clock.local()
                        edit_hour, edit_minute = local[3], local[4]
                        clock_edit = True
                    screen_dirty = True
                elif clock_edit:
                    if i == 1 and action == "hold":
                        clock_edit = False
                        screen_dirty = True
                    elif action == "tap":
                        if i == 0:
                            edit_hour = (edit_hour + 1) % 24
                        else:
                            edit_minute = (edit_minute + 1) % 60
                        screen_dirty = True
                elif action == "tap":
                    if i == 0:
                        submarine_at = seconds
                        submarine_direction = -submarine_direction
                        submarine_colour = (submarine_colour + 1) % 8
                    else:
                        override = False if override is None else (True if override is False else None)
                        print("Palette: " + ("auto" if override is None else ("night" if override else "day")))
            if clock_edit:
                if screen_dirty:
                    draw_settings(graphics, board, edit_hour, edit_minute)
                    screen_dirty = False
                was_screen = True
                time.sleep_ms(10)
                continue
            if was_screen:
                indexed.previous_pens = None  # Settings overwrote the display.
                was_screen = False
                frames = render_us = draw_us = update_us = 0
                report_start = start
            night = clock.night() if override is None else override
            t0 = ticks_us()
            if background is None:
                indexed.buffer[:] = aquarium.background_frame(seconds)
            else:
                scenery_start = ticks_us()
                while True:
                    background.advance(seconds, night)
                    if ticks_diff(ticks_us(), scenery_start) >= 3000:
                        break
                indexed.buffer[:] = background.front
                overlay_foliage(indexed.buffer, aquarium.foliage_buffer(seconds))
            coral = aquarium.coral_commands(seconds, night)
            overlay_sprite(indexed.buffer, coral, len(coral))
            chest = aquarium.chest_commands(seconds)
            overlay_sprite(indexed.buffer, chest, len(chest))
            render(seconds, pixel, night=night, submarine_at=submarine_at,
                   submarine_direction=submarine_direction, submarine_colour=submarine_colour, feeding_age=feeding.poll(clock.local(), seconds),
                   background=False, plants=False, ornaments=False)
            t1 = ticks_us()
            indexed.draw(pens[int(night)][int(seconds * 1.8) % 4])
            t2 = ticks_us()
            board.update()
            t3 = ticks_us()
            render_us += ticks_diff(t1, t0)
            draw_us += ticks_diff(t2, t1)
            update_us += ticks_diff(t3, t2)
            frames += 1
            now = ticks_ms()
            report_elapsed = ticks_diff(now, report_start)
            if report_elapsed >= REPORT_MS:
                print("FPS %.2f | render %.2f ms | draw %.2f ms | update %.2f ms | free %d" %
                      (frames * 1000 / report_elapsed, render_us / frames / 1000,
                       draw_us / frames / 1000, update_us / frames / 1000, gc.mem_free()))
                frames = render_us = draw_us = update_us = 0
                gc.collect()
                report_start = ticks_ms()
            remaining = 1000 // TARGET_FPS - ticks_diff(ticks_ms(), start)
            if remaining > 0:
                time.sleep_ms(remaining)
    finally:
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        board.update()


if __name__ == "__main__":
    main()

