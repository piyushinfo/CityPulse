"""Simulated feeds. They react to the shared World (rain, heat, outages, scenario boosts),
which is what creates REAL, explainable correlations between feeds."""
import math
import random
from collections import deque
from datetime import datetime, timezone, timedelta

from ..zones import ZONE_INFO, ZONE_IDS, STOPS, ROUTES, SENSORS, FEEDERS, zone_for_point

IST = timezone(timedelta(hours=5, minutes=30))
STOP_ZONE = {s: zone_for_point(*ll) for s, ll in STOPS.items()}
STOP_ROUTE = {s: r for r, stops in ROUTES.items() for s in stops}

# baseline complaint rates, per zone, per second (e.g. 1/3600 = one per hour)
BASE_COMPLAINTS = {"garbage": 1 / 3000, "streetlight": 1 / 6000, "noise": 1 / 5000, "pothole": 1 / 7000,
                   "waterlogging": 1 / 20000, "power_cut": 1 / 30000, "traffic_signal": 1 / 30000}
ZONE_PM_FACTOR = {"z1": 1.15, "z2": 0.95, "z3": 1.0, "z4": 0.95, "z5": 1.1, "z6": 1.25, "z7": 1.0, "z8": 0.9}


def poisson(rng, lam):
    if lam <= 0:
        return 0
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


class World:
    """Current conditions shared by all simulators."""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.rain_mm = 0.0
        self.temp_c = 31.0
        self.pm_base = 55.0
        self.outages = {}                 # feeder -> restore datetime
        self.boosts = []                  # dicts: {feed, zone, subtype?, rate, until}
        self.pending_trips = []           # zones to trip now (scenario)
        self.delay_times = {z: deque() for z in ZONE_IDS}
        self.next_air = None
        self.killed = set()               # feeds switched off (degradation demo)
        self.weather_override = None      # (rain, temp) while a scenario runs
        self.rain_next_hour = 0.0         # forecast, from Open-Meteo hourly (or scenario)
        self.temp_next_hour = 31.0
        self.next_traffic = None
        self.real_traffic = False         # True when TomTom supplies traffic; sim then stays quiet
        self.cpcb_zones = {}              # zone -> time of last real CPCB reading
        self.tags = ()

    def zone_has_outage(self, zid):
        return any(FEEDERS[f] == zid for f in self.outages)

    def boost_rate(self, feed, zid, subtype=None, now=None):
        return sum(b["rate"] for b in self.boosts
                   if b["feed"] == feed and b["zone"] == zid and (subtype is None or b.get("subtype") == subtype)
                   and (b["until"] is None or now is None or now <= b["until"]))


def _jitter(now, dt, rng):
    return now - timedelta(seconds=rng.random() * dt)


def sim_complaints(world, now, dt):
    out, rng = [], world.rng
    for zid in ZONE_IDS:
        info = ZONE_INFO[zid]
        for sub, base in BASE_COMPLAINTS.items():
            rate = base
            if sub == "waterlogging" and world.rain_mm > 0:
                rate += (world.rain_mm / 7.6) * (1 / 200 if info["flood_prone"] else 1 / 1500)
            if sub in ("power_cut", "traffic_signal") and world.zone_has_outage(zid):
                rate += 1 / 120 if sub == "power_cut" else 1 / 400
            if sub == "power_cut" and world.temp_c >= 42:
                rate += 1 / 2400
            rate += world.boost_rate("complaints", zid, sub, now)
            for _ in range(poisson(rng, rate * dt)):
                t = _jitter(now, dt, rng)
                lat, lon = info["center"]
                out.append({"ticket": f"CMP-{rng.randint(10000, 99999)}{int(t.timestamp()) % 1000}",
                            "category": sub.replace("_", " ").title(),
                            "lat": lat + rng.uniform(-0.003, 0.003), "lng": lon + rng.uniform(-0.003, 0.003),
                            "created": int(t.timestamp())})
    return out


def sim_transit(world, now, dt):
    out, rng = [], world.rng
    for stop, zid in STOP_ZONE.items():
        if stop not in STOP_ROUTE or zid is None:
            continue
        rate = 1 / 1500
        if world.rain_mm > 0 and ZONE_INFO[zid]["flood_prone"]:
            rate *= 1 + 4 * world.rain_mm / 7.6
        elif world.rain_mm > 0:
            rate *= 1 + 0.5 * world.rain_mm / 7.6
        if world.zone_has_outage(zid):
            rate *= 3                       # traffic signals down
        rate += world.boost_rate("transit", zid, None, now)
        for _ in range(poisson(rng, rate * dt)):
            t = _jitter(now, dt, rng)
            delay = 300 + rng.expovariate(1 / 240) + world.rain_mm * 50 + (600 if world.zone_has_outage(zid) else 0)
            world.delay_times[zid].append(t)
            out.append({"route": STOP_ROUTE[stop], "stop_code": stop, "delay_sec": int(delay),
                        "reported_at": t.astimezone(IST).strftime("%d/%m/%Y %H:%M:%S") + " IST"})
    return out


def sim_power(world, now, dt):
    out, rng = [], world.rng
    # restorations
    for f, until in list(world.outages.items()):
        if now >= until:
            del world.outages[f]
            out.append({"feeder": f, "status": "RESTORED", "area": ZONE_INFO[FEEDERS[f]]["name"],
                        "since": until.strftime("%Y-%m-%dT%H:%M:%SZ")})
    trips = list(world.pending_trips)
    world.pending_trips.clear()
    for f, zid in FEEDERS.items():
        if f in world.outages:
            continue
        rate = 1 / (10 * 86400)
        if world.rain_mm > 0 and ZONE_INFO[zid]["flood_prone"]:
            rate += (world.rain_mm / 7.6) / 5000
        if world.temp_c >= 42:
            rate += 1 / 10000
        if poisson(rng, rate * dt) > 0:
            trips.append(f)
    for item in trips:
        f = item if item in FEEDERS else next((x for x, z in FEEDERS.items() if z == item and x not in world.outages), None)
        if not f or f in world.outages:
            continue
        t = _jitter(now, dt, rng)
        world.outages[f] = t + timedelta(minutes=rng.uniform(25, 60))
        out.append({"feeder": f, "status": "TRIPPED", "area": ZONE_INFO[FEEDERS[f]]["name"],
                    "since": t.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


def sim_air(world, now, dt):
    """Each zone sensor reports every 60 s. Rain washes PM out; traffic congestion adds PM."""
    if world.next_air and now < world.next_air:
        return []
    world.next_air = now + timedelta(seconds=60)
    out, rng = [], world.rng
    washout = 1 - min(0.5, world.rain_mm / 30)
    for sensor, zid in SENSORS.items():
        real = world.cpcb_zones.get(zid)
        if real and now - real < timedelta(minutes=90):
            continue                      # a real CPCB station covers this zone
        dq = world.delay_times[zid]
        while dq and dq[0] < now - timedelta(minutes=15):
            dq.popleft()
        pm = world.pm_base * ZONE_PM_FACTOR[zid] * washout + min(20, 1.5 * len(dq)) + world.boost_rate("air", zid, None, now)
        pm = max(5, pm + rng.gauss(0, 5))
        out.append({"sensor": sensor, "reading": {"pm25": round(pm, 1), "pm10": round(pm * 1.7, 1)},
                    "epoch_ms": int(now.timestamp() * 1000)})
    return out


def rush_hour_factor(now):
    """0..1, peaks around 9:30 and 18:30 IST."""
    h = now.astimezone(IST).hour + now.astimezone(IST).minute / 60
    return max(math.exp(-((h - 9.5) ** 2) / 2), math.exp(-((h - 18.5) ** 2) / 2))


def sim_traffic(world, now, dt):
    """Road congestion per zone every 5 min, in TomTom flowSegmentData shape.
    Congestion = 1 - currentSpeed / freeFlowSpeed. Rain, outages (signals down) and bus delays raise it."""
    if world.real_traffic:
        return []
    if world.next_traffic and now < world.next_traffic:
        return []
    world.next_traffic = now + timedelta(minutes=5)
    out, rng = [], world.rng
    for zid in ZONE_IDS:
        info = ZONE_INFO[zid]
        c = 0.15 + 0.22 * rush_hour_factor(now)
        c += (world.rain_mm / 7.6) * (0.14 if info["flood_prone"] else 0.07)
        c += 0.2 if world.zone_has_outage(zid) else 0.0
        c += min(0.12, 0.01 * len(world.delay_times[zid]))
        c += world.boost_rate("traffic", zid, None, now)
        c = min(0.8, max(0.0, c + rng.gauss(0, 0.04)))
        free = 45.0
        cur = round(free * (1 - c), 1)
        lat, lon = info["center"]
        out.append({"flowSegmentData": {"frc": "FRC2", "currentSpeed": cur, "freeFlowSpeed": free,
                                        "currentTravelTime": int(600 / max(cur, 1) * 6),
                                        "freeFlowTravelTime": int(600 / free * 6), "confidence": 0.9,
                                        "coordinates": {"coordinate": [{"latitude": lat, "longitude": lon}]}},
                    "_fetched_at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "_source": "sim-traffic"})
    return out


def synthetic_weather_raw(now, rain, temp, source="synthetic"):
    """Same shape as Open-Meteo's response, used for history and as fallback."""
    local = now.astimezone(IST)
    return {"_source": source, "timezone": "Asia/Kolkata",
            "current": {"time": local.strftime("%Y-%m-%dT%H:%M"), "temperature_2m": round(temp, 1),
                        "precipitation": round(rain, 1), "wind_speed_10m": 12 + rain,
                        "weather_code": 65 if rain >= 7.6 else (61 if rain > 0 else 1)}}


SIMULATORS = {"complaints": sim_complaints, "transit": sim_transit, "power": sim_power, "air": sim_air,
              "traffic": sim_traffic}
