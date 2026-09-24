"""Possible links between anomalies of DIFFERENT categories in the same zone (city-wide counts
for every zone) that started within LINK_WINDOW_MIN of each other.
Lift from history = P(A and B in the same zone-window) / (P(A) * P(B)).
Lift > 1 means they co-occur more than chance. It is evidence of association, never proof of cause."""
from collections import Counter
from datetime import timedelta
from itertools import combinations

from .. import config
from ..schema import Link
from ..zones import ZONE_IDS, zone_name
from .anomaly import detect, signal_key, zones_of


def compute_lift(events, start, end, baseline, step_min=None):
    step = timedelta(minutes=step_min or config.WINDOW_MIN)
    single, pair, n = Counter(), Counter(), 0
    # index events by time for fast slicing
    t = start + timedelta(hours=3)
    i0 = 0
    while t <= end:
        lo = t - timedelta(hours=3)
        while i0 < len(events) and events[i0].ts_utc < lo:
            i0 += 1
        j = i0
        while j < len(events) and events[j].ts_utc <= t:
            j += 1
        anoms = detect(events[i0:j], t, baseline)
        per_zone = {z: set() for z in ZONE_IDS}
        for a in anoms:
            for z in zones_of(a):
                per_zone[z].add(signal_key(a))
        for z, sigs in per_zone.items():
            n += 1
            for s in sigs:
                single[s] += 1
            for a, b in combinations(sorted(sigs), 2):
                pair[(a, b)] += 1
        t += step
    lift = {}
    for (a, b), c in pair.items():
        if c >= 2:
            lift[(a, b)] = round(c * n / (single[a] * single[b]), 1)
    return lift, {"windows": n, "signals": dict(single)}


def get_lift(table, s1, s2):
    return table.get(tuple(sorted((s1, s2))))


def find_links(anomalies, lift_table):
    links = []
    max_gap = timedelta(minutes=config.LINK_WINDOW_MIN)
    for a, b in combinations(anomalies, 2):
        if a.category == b.category:
            continue
        if a.zone_id != "city" and b.zone_id != "city" and a.zone_id != b.zone_id:
            continue
        if a.zone_id == "city" and b.zone_id == "city":
            continue
        if abs(a.start - b.start) > max_gap:
            continue
        first, second = (a, b) if a.start <= b.start else (b, a)
        zid = b.zone_id if a.zone_id == "city" else a.zone_id
        lift = get_lift(lift_table, signal_key(a), signal_key(b))
        if lift is not None and lift < 1.5:
            continue  # history says they usually do NOT go together: don't claim a link
        conf = "new, unverified" if lift is None else ("strong pattern" if lift >= 3 else "some pattern")
        gap = round(abs((second.start - first.start).total_seconds()) / 60, 1)
        text = (f"{first.label} and {second.label.lower()} in {zone_name(zid)} are possibly linked "
                f"(not confirmed). {first.label} started first; the second followed {gap} min later.")
        if lift is not None:
            text += f" In the past {config.HISTORY_DAYS} days they happened together {lift}x more often than chance."
        links.append(Link(
            id=f"{first.id}~{second.id}", zone_id=zid,
            first={"id": first.id, "label": first.label, "category": first.category, "start": first.start.isoformat()},
            second={"id": second.id, "label": second.label, "category": second.category, "start": second.start.isoformat()},
            gap_min=gap, lift=lift, confidence=conf, text=text))
    rank = {"strong pattern": 0, "some pattern": 1, "new, unverified": 2}
    links.sort(key=lambda l: (rank[l.confidence], -(l.lift or 0)))
    # keep at most 3 links per zone so the screen stays readable
    per_zone, kept = {}, []
    for l in links:
        per_zone[l.zone_id] = per_zone.get(l.zone_id, 0) + 1
        if per_zone[l.zone_id] <= 3:
            kept.append(l)
    return kept
