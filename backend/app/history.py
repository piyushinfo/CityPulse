"""Generates a realistic multi-day history (default 3 days) by running the SAME simulators
over past time, with scripted weather episodes. Used for: baselines, lift table, and replay."""
import math
from datetime import timedelta

from .adapters.simulators import World, SIMULATORS, synthetic_weather_raw
from .normalizer import normalize

# (hours after history start, duration hours, rain mm/h, temp C or None)
EPISODES = [
    (17.5, 2.0, 14.0, None),   # evening storm, day 1
    (30.0, 1.0, 3.0, None),    # light rain
    (43.0, 1.5, 10.0, None),   # second storm, day 2
    (56.0, 4.0, 0.0, 44.5),    # heatwave afternoon, day 3
]


def conditions_at(hours, start):
    local_hour = (start + timedelta(hours=hours)).hour + 5.5
    temp = 31 + 5 * math.sin((local_hour - 9) / 24 * 2 * math.pi)
    rain = 0.0
    for h0, dur, r, t in EPISODES:
        if h0 <= hours < h0 + dur:
            rain = r
            if t is not None:
                temp = t
    pm = 52 + 18 * math.cos((local_hour - 8) / 24 * 2 * math.pi)  # worse at morning/night
    return rain, temp, pm


def generate_history(end, days=3, seed=42, step_s=60):
    start = end - timedelta(days=days)
    world = World(seed=seed)
    events = []
    t = start
    last_weather = None
    while t < end:
        hours = (t - start).total_seconds() / 3600
        world.rain_mm, world.temp_c, world.pm_base = conditions_at(hours, start)
        if last_weather is None or (t - last_weather) >= timedelta(minutes=15):
            events += normalize("weather", synthetic_weather_raw(t, world.rain_mm, world.temp_c, "history"), ("history",))
            last_weather = t
        for feed, fn in SIMULATORS.items():
            for raw in fn(world, t, step_s):
                events += normalize(feed, raw, ("history",))
        t += timedelta(seconds=step_s)
    events.sort(key=lambda e: e.ts_utc)
    return events, start, dict(world.outages)   # outages still open at the end continue into live mode
