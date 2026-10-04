import threading
import time


class RaceClock:
    """UTC mapping to monotonic time. Never restore an anchor across process restarts."""
    def __init__(self, mono=time.monotonic_ns, wall=time.time_ns):
        self.mono, self.wall = mono, wall
        self.lock = threading.RLock()
        self.anchor_mono = mono()
        self.anchor_ms = wall() / 1_000_000
        self.last_sync = None
        self.uncertainty_ms = None
        self.rate = 1.0
        self.flag = "unverified"

    def _now(self, mono):
        return self.anchor_ms + (mono - self.anchor_mono) / 1_000_000 * self.rate

    def discipline(self, server_ms, mono_ns, uncertainty_ms):
        with self.lock:
            predicted = self._now(mono_ns)
            delta = server_ms - predicted
            if self.last_sync is None:
                self.anchor_ms = server_ms
                self.rate = 1.0
            elif abs(delta) > 2000:
                self.flag = "jump"
                return False
            else:
                # Phase continuity: correction changes rate, never steps timestamps backwards.
                self.anchor_ms = predicted
                self.rate = 1 + max(-0.001, min(0.001, delta / 60_000))
            self.anchor_mono = mono_ns
            self.last_sync = mono_ns
            self.uncertainty_ms = uncertainty_ms + (abs(delta) if self.flag != "unverified" else 0)
            self.flag = "synced"
            return True

    def stamp(self):
        with self.lock:
            m = self.mono()
            age = (m - self.last_sync) / 1e9 if self.last_sync is not None else None
            quality = self.flag
            if quality == "synced" and age is not None:
                if age > 3600:
                    quality = "stale"
                elif age > 120:
                    quality = "holdover"
            # Operational estimate only, not a hardware-calibrated accuracy guarantee.
            uncertainty = None if age is None else int(self.uncertainty_ms + age * 0.1)
            return {"captured_ms": int(self._now(m)), "monotonic_ns": m,
                    "clock_quality": quality, "uncertainty_ms": uncertainty,
                    "sync_age_s": None if age is None else round(age, 2)}
