"""Event store: one time-sorted list in memory (history + live). Fine for ~100k events."""
import bisect
import threading


class EventStore:
    def __init__(self):
        self._events = []   # sorted by ts_utc
        self._keys = []     # parallel list of timestamps for bisect
        self._ids = set()
        self._lock = threading.Lock()

    def add(self, ev):
        with self._lock:
            if ev.id in self._ids:
                return False
            k = ev.ts_utc.timestamp()
            i = bisect.bisect_right(self._keys, k)
            self._keys.insert(i, k)
            self._events.insert(i, ev)
            self._ids.add(ev.id)
            return True

    def add_many(self, evs):
        for e in evs:
            self.add(e)

    def window(self, start, end):
        with self._lock:
            i = bisect.bisect_left(self._keys, start.timestamp())
            j = bisect.bisect_right(self._keys, end.timestamp())
            return self._events[i:j]

    def latest(self, n=50, predicate=None):
        with self._lock:
            out = []
            for e in reversed(self._events):
                if predicate is None or predicate(e):
                    out.append(e)
                    if len(out) >= n:
                        break
            return out

    def remove_tagged(self, tag):
        with self._lock:
            keep = [e for e in self._events if tag not in e.tags]
            self._events = keep
            self._keys = [e.ts_utc.timestamp() for e in keep]
            self._ids = {e.id for e in keep}

    def range(self):
        with self._lock:
            if not self._events:
                return None, None
            return self._events[0].ts_utc, self._events[-1].ts_utc

    def __len__(self):
        return len(self._events)
