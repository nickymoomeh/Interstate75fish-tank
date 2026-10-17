"""Desktop aquarium preview. Run: python3 emulator.py

Requires Pillow: python3 -m pip install Pillow
"""
import argparse
import datetime
import time
import tkinter as tk
from PIL import Image, ImageTk

from aquarium import WIDTH, HEIGHT, FPS, palette_at, render


def make_frame(seconds, night=False, submarine_at=None, submarine_direction=None,
               feeding_age=None, submarine_colour=None):
    """Return an RGB Pillow image at the exact physical panel resolution."""
    indices = bytearray(WIDTH * HEIGHT)

    def pixel(x, y, colour):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            indices[y * WIDTH + x] = colour

    render(seconds, pixel, night=night, submarine_at=submarine_at,
           submarine_direction=submarine_direction, feeding_age=feeding_age,
           submarine_colour=submarine_colour)
    palette = palette_at(seconds, night=night)
    rgb = bytearray(WIDTH * HEIGHT * 3)
    for i, index in enumerate(indices):
        j = i * 3
        rgb[j:j + 3] = bytes(palette[index])
    return Image.frombytes("RGB", (WIDTH, HEIGHT), bytes(rgb))


def main():
    parser = argparse.ArgumentParser(description="Fish Tank Mk I emulator")
    parser.add_argument("--scale", type=int, default=6, help="Integer pixel scale")
    parser.add_argument("--night", action="store_true", help="Force night mode at startup")
    parser.add_argument("--uncapped", action="store_true", help="Benchmark without the 15 FPS frame limiter")
    args = parser.parse_args()
    scale = max(1, args.scale)
    target_label = "uncapped" if args.uncapped else str(FPS)
    root = tk.Tk()
    root.title("Fish Tank Mk I | 128 x 64")
    label = tk.Label(root, bg="black")
    label.pack(padx=10, pady=10)
    status = tk.Label(root, text="Space: pause  |  N: night/day  |  A: auto  |  S: submarine  |  F: feed  |  Esc: quit")
    status.pack(pady=(0, 3))
    performance = tk.Label(root, text="FPS: measuring...", fg="#555555")
    performance.pack(pady=(0, 8))
    state = {"night_override": True if args.night else None,
             "paused": False, "elapsed": 0.0,
             "last": time.monotonic(), "submarine_at": None,
             "submarine_direction": -1, "submarine_colour": -1,
             "feed_at": None, "fps_start": time.monotonic(), "fps_frames": 0,
             "fps_visible": True, "next_frame": time.monotonic(),
             "render_total": 0.0, "display_total": 0.0}

    def toggle_pause(_event=None):
        state["paused"] = not state["paused"]

    def toggle_night(_event=None):
        automatic = (datetime.datetime.now().hour * 60 +
                     datetime.datetime.now().minute >= 20 * 60 or
                     datetime.datetime.now().hour < 7)
        current = automatic if state["night_override"] is None else state["night_override"]
        state["night_override"] = not current

    def summon_submarine(_event=None):
        # Do not restart a submarine already travelling across the screen.
        previous = state["submarine_at"]
        if previous is not None and 0 <= state["elapsed"] - previous < 18:
            return
        automatic_phase = (state["elapsed"] - 45) % 180
        if previous is None and automatic_phase < 18:
            return
        state["submarine_at"] = state["elapsed"]
        state["submarine_direction"] *= -1
        state["submarine_colour"] = (state["submarine_colour"] + 1) % 4

    def feed_fish(_event=None):
        state["feed_at"] = state["elapsed"]

    root.bind("<space>", toggle_pause)
    root.bind("f", feed_fish)
    root.bind("s", summon_submarine)
    root.bind("n", toggle_night)
    root.bind("a", lambda _event: state.update(night_override=None))
    root.bind("p", lambda _event: toggle_fps())

    def toggle_fps():
        state["fps_visible"] = not state["fps_visible"]
        if state["fps_visible"]:
            performance.pack(pady=(0, 8))
        else:
            performance.pack_forget()
    root.bind("<Escape>", lambda _event: root.destroy())

    def tick():
        now = time.monotonic()
        if not state["paused"]:
            state["elapsed"] += min(now - state["last"], 0.25)
        state["last"] = now
        local = datetime.datetime.now()
        minutes_now = local.hour * 60 + local.minute
        automatic_night = minutes_now >= 20 * 60 or minutes_now < 7 * 60
        night = (automatic_night if state["night_override"] is None
                 else state["night_override"])
        seconds_in_hour = local.minute * 60 + local.second + local.microsecond / 1e6
        scheduled_feed = (seconds_in_hour - 900 if 900 <= seconds_in_hour < 928
                          else seconds_in_hour - 2700 if 2700 <= seconds_in_hour < 2728
                          else None)
        manual_feed = (state["elapsed"] - state["feed_at"]
                       if state["feed_at"] is not None else None)
        feeding_age = (manual_feed if manual_feed is not None and 0 <= manual_feed < 28
                       else scheduled_feed)
        render_start = time.monotonic()
        image = make_frame(state["elapsed"], night, state["submarine_at"],
                           state["submarine_direction"], feeding_age,
                           state["submarine_colour"])
        render_end = time.monotonic()
        image = image.resize((WIDTH * scale, HEIGHT * scale), Image.Resampling.NEAREST)
        photo = ImageTk.PhotoImage(image)
        label.configure(image=photo)
        label.image = photo
        state["render_total"] += render_end - render_start
        state["display_total"] += time.monotonic() - render_end
        state["fps_frames"] += 1
        fps_period = time.monotonic() - state["fps_start"]
        if fps_period >= 1.5:
            measured = state["fps_frames"] / fps_period
            render_ms = 1000 * state["render_total"] / state["fps_frames"]
            display_ms = 1000 * state["display_total"] / state["fps_frames"]
            performance.configure(text="FPS: {:.1f}/{}  |  Render: {:.1f} ms  |  Display: {:.1f} ms  |  P: toggle".format(measured, target_label, render_ms, display_ms))
            state["render_total"] = 0.0
            state["display_total"] = 0.0
            state["fps_frames"] = 0
            state["fps_start"] = time.monotonic()
        # Schedule to a fixed cadence instead of waiting a full frame
        # interval AFTER rendering (which capped actual FPS below target).
        if args.uncapped:
            # Yield to Tk events but do not impose the animation FPS cap.
            root.after(1, tick)
        else:
            interval = 1.0 / FPS
            state["next_frame"] += interval
            now = time.monotonic()
            if state["next_frame"] < now:
                state["next_frame"] = now
            root.after(max(1, int((state["next_frame"] - now) * 1000)), tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()

