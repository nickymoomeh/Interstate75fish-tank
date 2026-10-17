"""Local RTC clock. No timezone, network, files or automatic DST changes."""

class Clock:
    def __init__(self, rtc, log=print):
        self.rtc = rtc
        self.log = log
        self.source = "RTC" if rtc.datetime()[0] >= 2025 else "unset"

    def local(self):
        year, month, day, weekday, hour, minute, second, _ = self.rtc.datetime()
        return (year, month, day, hour, minute, second, weekday, 0)

    def set_hm(self, hour, minute):
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("Invalid hours/minutes")
        parts = self.rtc.datetime()
        # A nominal date enables RTC rollover; it does not claim today's date.
        date = parts[:4] if parts[0] >= 2025 else (2025, 1, 1, 2)
        self.rtc.datetime(tuple(date) + (hour, minute, 0, 0))
        self.source = "manual local time"
        self.log("Clock set: %02d:%02d local" % (hour, minute))

    def night(self):
        if self.source == "unset":
            return True
        parts = self.local()
        minutes = parts[3] * 60 + parts[4]
        return minutes >= 20 * 60 or minutes < 7 * 60


class FeedingSchedule:
    """Trigger once per local :15/:45 slot; animate using monotonic seconds."""
    def __init__(self, log=None):
        self.log = log
        self.last_slot = None
        self.started = None

    def poll(self, local, seconds):
        if local[4] in (15, 45) and local[5] < 28:
            slot = tuple(local[:5])
            if slot != self.last_slot:
                self.last_slot = slot
                self.started = seconds - local[5]
                if self.log is not None:
                    self.log("Feeding: %02d:%02d local" % (local[3], local[4]))
        if self.started is not None:
            age = seconds - self.started
            if 0 <= age < 28:
                return age
        return None

