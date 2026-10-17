"""Debounced tap/hold events; holds do not also emit a tap."""
import time


class Buttons:
    def __init__(self):
        self.raw = [False, False]
        self.stable = [False, False]
        self.changed = [0, 0]
        self.started = [0, 0]
        self.held = [False, False]

    def poll(self, states, now):
        events = []
        for i in range(2):
            down = bool(states[i])
            if down != self.raw[i]:
                self.raw[i] = down
                self.changed[i] = now
            if down != self.stable[i] and time.ticks_diff(now, self.changed[i]) >= 40:
                self.stable[i] = down
                if down:
                    self.started[i] = now
                    self.held[i] = False
                elif not self.held[i]:
                    events.append((i, "tap"))
            if self.stable[i] and down and not self.held[i] and time.ticks_diff(now, self.started[i]) >= 1200:
                self.held[i] = True
                events.append((i, "hold"))
        return events

