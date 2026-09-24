"""Anomaly detection. Two kinds:
  spike     = count in the last WINDOW_MIN is far above the historical baseline (z-score)
              used for complaints (per subtype) and transit delays
  threshold = a reading crosses a published limit
              heavy rain >= 7.6 mm/h, heat >= 42 C, PM2.5 > 90 ug/m3 (CPCB 'poor'), any tripped feeder,
              road congestion >= 0.5 (traffic moving at half its free-flow speed or slower)
"""
import math
from collections import defaultdict
from datetime import timedelta
from statistics import mean, pstdev

from .. import config
from ..schema import Anomaly
from ..zones import ZONE_IDS, zone_name

Z_THRESHOLD = 3.0
MIN_COUNT = 3
PM_LIMIT = 90.0
CONGESTION_LIMIT = 0.5

LABELS = {
    "transit:delays": "Bus delays piling up",
    "weather:heavy_rain": "Heavy rain",
    "weather:heatwave": "Extreme heat",
    "air:pm25": "Poor air quality",
    "power:outage": "Power outage",
    "traffic:congestion": "Heavy traffic",
}


def signal_of(e):
    """Map an event to the signal it contributes to (None = not a spike signal)."""
    if e.category == "complaint":
        return f"complaint:{e.subtype}"
    if e.category == "transit":
        return "transit:delays"
    return None


def label_for(signal):
    if signal in LABELS:
        return LABELS[signal]
    if signal.startswith("complaint:"):
        return signal.split(":", 1)[1].replace("_", " ").capitalize() + " complaints spiking"
    return signal


def compute_baseline(events, start, end, window_min=None):
    """Mean/std of per-window counts for every (zone, signal), over non-overlapping windows (trimmed)."""
    window_min = window_min or config.WINDOW_MIN
    step = timedelta(minutes=window_min)
    n_windows = max(1, int((end - start) / step))
    counts = defaultdict(lambda: [0] * n_windows)
    for e in events:
        s = signal_of(e)
        if not s:
            continue
        idx = int((e.ts_utc - start) / step)
        if 0 <= idx < n_windows:
            counts[(e.zone_id, s)][idx] += 1
    # robust baseline: ignore the busiest 10% of windows (past storms) so "normal" means normal
    out = {}
    for k, v in counts.items():
        trimmed = sorted(v)[: max(1, int(len(v) * 0.9))]
        out[k] = (mean(trimmed), pstdev(trimmed))
    return out


def _consecutive_start(readings, predicate):
    """readings sorted oldest->newest; return ts of the first reading of the latest run matching predicate."""
    start = None
    for e in reversed(readings):
        if predicate(e):
            start = e.ts_utc
        else:
            break
    return start


def detect(events, now, baseline, window_min=None):
    """events: everything from the last ~3 hours (sorted). Returns list[Anomaly]."""
    window_min = window_min or config.WINDOW_MIN
    w_start = now - timedelta(minutes=window_min)
    out = []

    # ---- spikes ----
    groups = defaultdict(list)
    for e in events:
        if e.ts_utc >= w_start and e.ts_utc <= now:
            s = signal_of(e)
            if s:
                groups[(e.zone_id, s)].append(e)
    for (zid, sig), evs in groups.items():
        mu, sd = baseline.get((zid, sig), (0.0, 0.0))
        n = len(evs)
        sd_eff = max(sd, math.sqrt(max(mu, 0.0)), 1.0)
        z = (n - mu) / sd_eff
        if z >= Z_THRESHOLD and n >= MIN_COUNT:
            evs.sort(key=lambda e: e.ts_utc)
            first_excess = evs[min(len(evs) - 1, int(math.ceil(mu)))]
            sev = min(1.0, 0.5 * min(1.0, z / 6) + 0.5 * mean(e.severity for e in evs))
            out.append(Anomaly(
                id=f"{zid}:{sig}", zone_id=zid, category=sig.split(":")[0], kind="spike", label=label_for(sig),
                severity=round(sev, 2), start=first_excess.ts_utc, observed=n, expected=round(mu, 2),
                z=round(z, 1), evidence=[e.id for e in evs[-12:]]))

    # ---- weather thresholds (city-wide) ----
    weather = [e for e in events if e.category == "weather" and e.ts_utc <= now
               and e.ts_utc >= now - timedelta(minutes=90)]
    rain = [e for e in weather if e.subtype.endswith("rain")]
    if rain and rain[-1].subtype == "heavy_rain":
        st = _consecutive_start(rain, lambda e: e.subtype == "heavy_rain")
        out.append(Anomaly(id="city:weather:heavy_rain", zone_id="city", category="weather", kind="threshold",
                           label=label_for("weather:heavy_rain"), severity=round(rain[-1].severity, 2), start=st,
                           observed=rain[-1].value, expected=7.6, z=None, evidence=[rain[-1].id]))
    heat = [e for e in weather if e.subtype == "heatwave" and e.ts_utc >= now - timedelta(minutes=70)]
    if heat:
        out.append(Anomaly(id="city:weather:heatwave", zone_id="city", category="weather", kind="threshold",
                           label=label_for("weather:heatwave"), severity=round(heat[-1].severity, 2),
                           start=heat[0].ts_utc, observed=heat[-1].value, expected=42, z=None,
                           evidence=[heat[-1].id]))

    # ---- air thresholds (per zone, latest reading in last 10 min) ----
    air = defaultdict(list)
    for e in events:
        if e.category == "air" and now - timedelta(minutes=60) <= e.ts_utc <= now:
            air[e.zone_id].append(e)
    for zid, rs in air.items():
        if rs[-1].ts_utc >= now - timedelta(minutes=10) and rs[-1].value > PM_LIMIT:
            st = _consecutive_start(rs, lambda e: e.value > PM_LIMIT)
            out.append(Anomaly(id=f"{zid}:air:pm25", zone_id=zid, category="air", kind="threshold",
                               label=label_for("air:pm25"), severity=round(rs[-1].severity, 2), start=st,
                               observed=rs[-1].value, expected=PM_LIMIT, z=None, evidence=[rs[-1].id]))

    # ---- traffic thresholds (per zone, latest reading in last 15 min) ----
    traffic = defaultdict(list)
    for e in events:
        if e.category == "traffic" and now - timedelta(minutes=60) <= e.ts_utc <= now:
            traffic[e.zone_id].append(e)
    for zid, rs in traffic.items():
        if rs[-1].ts_utc >= now - timedelta(minutes=15) and rs[-1].value >= CONGESTION_LIMIT:
            st = _consecutive_start(rs, lambda e: e.value >= CONGESTION_LIMIT)
            out.append(Anomaly(id=f"{zid}:traffic:congestion", zone_id=zid, category="traffic", kind="threshold",
                               label=label_for("traffic:congestion"), severity=round(rs[-1].severity, 2), start=st,
                               observed=rs[-1].value, expected=CONGESTION_LIMIT, z=None, evidence=[rs[-1].id]))

    # ---- power: feeders whose latest status is TRIPPED ----
    last_status = {}
    for e in events:
        if e.category == "power" and e.ts_utc <= now:
            last_status[e.raw.get("feeder")] = e
    active = defaultdict(list)
    for f, e in last_status.items():
        if e.subtype == "feeder_trip":
            active[e.zone_id].append(e)
    for zid, trips in active.items():
        out.append(Anomaly(id=f"{zid}:power:outage", zone_id=zid, category="power", kind="threshold",
                           label=label_for("power:outage") + (f" ({len(trips)} feeders)" if len(trips) > 1 else ""),
                           severity=min(1.0, 0.6 + 0.2 * (len(trips) - 1)), start=min(t.ts_utc for t in trips),
                           observed=len(trips), expected=0, z=None, evidence=[t.id for t in trips]))
    return out


def signal_key(a):
    """Anomaly -> signal name used by the lift table."""
    if a.kind == "spike":
        return a.id.split(":", 1)[1]
    return {"weather": "weather:" + a.id.split(":")[-1], "air": "air:pm25", "power": "power:outage",
            "traffic": "traffic:congestion"}[a.category]


def zones_of(a):
    return ZONE_IDS if a.zone_id == "city" else [a.zone_id]


def describe(a):
    where = zone_name(a.zone_id)
    if a.kind == "spike":
        return f"{a.label} in {where}: {int(a.observed)} reports in {config.WINDOW_MIN} min (usual about {a.expected})"
    if a.category == "weather" and "rain" in a.id:
        return f"{a.label} city-wide: {a.observed} mm/h"
    if a.category == "weather":
        return f"{a.label} city-wide: {a.observed} C"
    if a.category == "air":
        return f"{a.label} in {where}: PM2.5 {a.observed} ug/m3"
    if a.category == "traffic":
        return f"{a.label} in {where}: moving at {round((1 - a.observed) * 100)}% of normal speed"
    return f"{a.label} in {where}"
