"""Scripted demo scenarios. Each step fires at `at` seconds after start.
Actions: weather(rain, temp) | boost(feed, zone, subtype, rate, for_s) | trip(zone) | air(zone, add, for_s)"""
from datetime import timedelta

SCENARIOS = {
    "monsoon": {
        "title": "Monsoon storm over the Walled City",
        "steps": [
            {"at": 0, "do": "weather", "rain": 18.0, "temp": 27.0},
            {"at": 5, "do": "boost", "feed": "complaints", "zone": "z1", "subtype": "waterlogging", "rate": 1 / 3, "for_s": 90},
            {"at": 12, "do": "boost", "feed": "complaints", "zone": "z3", "subtype": "waterlogging", "rate": 1 / 6, "for_s": 70},
            {"at": 18, "do": "boost", "feed": "transit", "zone": "z1", "rate": 1 / 2, "for_s": 90},
            {"at": 20, "do": "boost", "feed": "traffic", "zone": "z1", "rate": 0.25, "for_s": 120},
            {"at": 30, "do": "trip", "zone": "z1"},
            {"at": 33, "do": "boost", "feed": "complaints", "zone": "z1", "subtype": "traffic_signal", "rate": 1 / 5, "for_s": 60},
            {"at": 50, "do": "trip", "zone": "z3"},
        ],
    },
    "heatwave": {
        "title": "Heatwave and grid stress",
        "steps": [
            {"at": 0, "do": "weather", "rain": 0.0, "temp": 46.0},
            {"at": 10, "do": "trip", "zone": "z8"},
            {"at": 20, "do": "trip", "zone": "z5"},
            {"at": 12, "do": "boost", "feed": "complaints", "zone": "z8", "subtype": "power_cut", "rate": 1 / 3, "for_s": 80},
            {"at": 22, "do": "boost", "feed": "complaints", "zone": "z5", "subtype": "power_cut", "rate": 1 / 4, "for_s": 70},
            {"at": 30, "do": "air", "zone": "z6", "add": 90, "for_s": 120},
        ],
    },
}


class ScenarioRunner:
    def __init__(self, world):
        self.world = world
        self.name = None
        self.started = None
        self.done = set()

    def start(self, name, now):
        if name not in SCENARIOS:
            raise KeyError(name)
        self.name, self.started, self.done = name, now, set()
        self.world.tags = ("scenario",)

    def reset(self):
        self.name, self.started, self.done = None, None, set()
        w = self.world
        w.boosts.clear()
        w.pending_trips.clear()
        w.outages.clear()
        w.weather_override = None
        w.tags = ()

    def tick(self, now):
        """Apply due steps. Returns True if weather changed (so the engine emits a weather event)."""
        if not self.name:
            return False
        weather_changed = False
        elapsed = (now - self.started).total_seconds()
        for i, s in enumerate(SCENARIOS[self.name]["steps"]):
            if i in self.done or elapsed < s["at"]:
                continue
            self.done.add(i)
            w = self.world
            if s["do"] == "weather":
                w.weather_override = (s["rain"], s["temp"])
                w.rain_mm, w.temp_c = s["rain"], s["temp"]
                w.rain_next_hour, w.temp_next_hour = s["rain"], s["temp"]   # the storm is forecast to continue
                weather_changed = True
            elif s["do"] == "boost":
                w.boosts.append({"feed": s["feed"], "zone": s["zone"], "subtype": s.get("subtype"),
                                 "rate": s["rate"], "until": now + timedelta(seconds=s["for_s"])})
                if s["feed"] == "traffic":
                    w.next_traffic = None     # take a traffic reading now instead of waiting 5 min
            elif s["do"] == "air":
                w.boosts.append({"feed": "air", "zone": s["zone"], "subtype": None, "rate": s["add"],
                                 "until": now + timedelta(seconds=s["for_s"])})
            elif s["do"] == "trip":
                w.pending_trips.append(s["zone"])
        return weather_changed

    def status(self):
        if not self.name:
            return None
        return {"name": self.name, "title": SCENARIOS[self.name]["title"], "started": self.started.isoformat(),
                "steps_done": len(self.done), "steps_total": len(SCENARIOS[self.name]["steps"])}
