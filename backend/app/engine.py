"""The heart of CityPulse: owns the store, world, feeds, and computes the state snapshot."""
import asyncio
from datetime import datetime, timezone, timedelta

from . import config
from .adapters.simulators import World, SIMULATORS, synthetic_weather_raw
from .adapters.weather import fetch_weather_raw, fallback_weather_raw, next_hour_from_raw
from .adapters.air import fetch_city_pm25, fetch_cpcb_records
from .adapters.traffic import fetch_traffic_raws
from .ai.agent import MonitorAgent, send_telegram
from .ai.summarizer import build_facts, template_summary, llm_summary, validate
from .ai.resident import resident_message
from .analysis.anomaly import detect, compute_baseline, describe
from .analysis.correlation import compute_lift, find_links
from .analysis.pulse import zone_pulses
from .analysis.forecast import build_profile, outlook, condition
from .history import generate_history, conditions_at
from .normalizer import normalize
from .scenarios import ScenarioRunner, SCENARIOS
from .store import EventStore
from .workflow import IncidentBoard
from .analysis.backtest import run_backtest
from .normalizer import normalize_complaint
from .zones import zone_name, ZONE_INFO, FEEDERS

# how long a feed may be silent before it counts as stale
FEED_TTL = {"weather": 1500, "air": 180, "transit": 120, "complaints": 120, "power": 300, "traffic": 900,
            "cpcb": 7200}
OPTIONAL_FEEDS = {"cpcb"}   # nice to have: never makes the picture "partial" when missing


def utcnow():
    return datetime.now(timezone.utc)


class Engine:
    def __init__(self):
        self.store = EventStore()
        self.world = World()
        self.runner = ScenarioRunner(self.world)
        self.agent = MonitorAgent()
        self.feeds = {f: {"name": f, "last_ok": None, "source": "sim"} for f in FEED_TTL}
        self.feeds["weather"]["source"] = "open-meteo"
        self.feeds["air"]["source"] = "open-meteo + sim sensors"
        self.feeds["traffic"]["source"] = "sim (TomTom if key)"
        self.feeds["cpcb"]["source"] = "CPCB via data.gov.in"
        self.profile = {}
        self.history_start = None
        self.baseline, self.lift, self.lift_meta = {}, {}, {}
        self.history_range = (None, None)
        self.snapshot = None
        self.llm_cache = {"text": None, "sig": None, "note": "not run yet"}
        self.listeners = set()   # asyncio.Queue per websocket
        self.force_weather = False
        self.board = IncidentBoard()
        self.backtest_cache = None
        self.report_log = {}      # (client, zone, category) -> last report time, for rate limiting

    # ---------- setup ----------
    def bootstrap(self, now=None):
        now = now or utcnow()
        events, start, open_outages = generate_history(now, days=config.HISTORY_DAYS)
        self.world.outages.update(open_outages)   # live sim_power will restore them on schedule
        self.store.add_many(events)
        self.history_range = (start, now)
        self.history_start = start
        self.baseline = compute_baseline(events, start, now)
        self.lift, self.lift_meta = compute_lift(events, start, now, self.baseline)
        self.profile = build_profile(self.pulse_at, lambda t: condition(*self.weather_at(t)[:2]), start, now)
        # continue from history's final conditions
        last_w = [e for e in events if e.category == "weather"][-1:]
        if last_w:
            self.world.rain_mm = last_w[0].value if last_w[0].subtype.endswith("rain") else 0.0
        print(f"[engine] history: {len(events)} events, {len(self.baseline)} baselines, lift pairs: {self.lift}")

    # ---------- ingestion ----------
    def ingest(self, feed, raws, now):
        if feed in self.world.killed:
            return 0
        n = 0
        for raw in raws:
            for ev in normalize(feed, raw, self.world.tags):
                n += self.store.add(ev)
        self.feeds[feed]["last_ok"] = now
        return n

    def feed_status(self, now):
        out = []
        for f, info in self.feeds.items():
            if f in self.world.killed:
                status = "offline"
            elif info["last_ok"] is None and f in OPTIONAL_FEEDS:
                status = "not connected"
            elif info["last_ok"] is None or (now - info["last_ok"]).total_seconds() > FEED_TTL[f]:
                status = "stale"
            else:
                status = "live"
            age = None if info["last_ok"] is None else int((now - info["last_ok"]).total_seconds())
            out.append({"name": f, "status": status, "age_s": age, "source": info["source"],
                        "optional": f in OPTIONAL_FEEDS})
        return out

    def pulse_at(self, t):
        """Zone scores at time t (no summary) - used for trends and the forecast profile."""
        anomalies = detect(self.store.window(t - timedelta(hours=3), t), t, self.baseline)
        _, zones = zone_pulses(anomalies, [])
        return {z["id"]: z["score"] for z in zones}

    def weather_at(self, t):
        """(rain, temp, rain_next_hour, temp_next_hour). Live: world state. Past: the history's weather."""
        if self.history_start and t < self.history_range[1] - timedelta(minutes=1):
            hours = (t - self.history_start).total_seconds() / 3600
            r, tc, _ = conditions_at(hours, self.history_start)
            rn, tn, _ = conditions_at(hours + 1, self.history_start)
            return r, tc, rn, tn
        w = self.world
        return w.rain_mm, w.temp_c, w.rain_next_hour, w.temp_next_hour

    # ---------- the pure computation ----------
    def compute_state(self, now, mode="live"):
        events = self.store.window(now - timedelta(hours=3), now)
        feeds = self.feed_status(now) if mode == "live" else \
            [{"name": f, "status": "live", "age_s": 0, "source": "history"} for f in FEED_TTL]
        partial = [f["name"] for f in feeds if f["status"] != "live" and f["name"] not in OPTIONAL_FEEDS]
        anomalies = detect(events, now, self.baseline)
        # offline feeds keep their last known events; the pulse is flagged partial instead
        links = find_links(anomalies, self.lift)
        city, zones = zone_pulses(anomalies, partial)
        rain, temp, rain_next, temp_next = self.weather_at(now)
        fc, fc_meta = outlook(zones, self.pulse_at(now - timedelta(minutes=15)), rain, temp, rain_next, temp_next,
                              self.profile)
        fc_by_zone = {f["zone_id"]: f for f in fc}
        for z in zones:
            z["resident"] = resident_message(z, anomalies, fc_by_zone.get(z["id"]))
        facts = build_facts(city, zones, anomalies, links, feeds)
        summary = {"text": template_summary(facts), "source": "template", "note": ""}
        if mode == "live" and self.llm_cache["text"]:
            ok, why = validate(self.llm_cache["text"], facts)
            if ok and self.llm_cache["sig"] == self._sig(anomalies, links):
                summary = {"text": self.llm_cache["text"], "source": "llm", "note": "grounded + validated"}
        ticker = [{"ts": e.ts_utc.isoformat(), "zone": zone_name(e.zone_id), "category": e.category,
                   "subtype": e.subtype, "value": e.value, "unit": e.unit}
                  for e in reversed(events) if e.category != "air" or e.severity > 0.2][:15]
        return {
            "ts": now.isoformat(), "mode": mode, "city_name": config.CITY_NAME, "city": city, "zones": zones,
            "anomalies": [dict(a.to_dict(), text=describe(a), zone_name=zone_name(a.zone_id)) for a in anomalies],
            "links": [l.to_dict() for l in links], "summary": summary, "feeds": feeds,
            "forecast": fc, "forecast_meta": fc_meta,
            "alerts": list(self.agent.alerts) if mode == "live" else [], "ticker": ticker,
            "scenario": self.runner.status() if mode == "live" else None,
            "_facts": facts, "_sig": self._sig(anomalies, links), "_links": links,
        }

    @staticmethod
    def _sig(anomalies, links):
        return "|".join(sorted(a.id for a in anomalies)) + "#" + "|".join(sorted(l.id for l in links))

    def public(self, snap):
        return {k: v for k, v in snap.items() if not k.startswith("_")}

    # ---------- controls ----------
    def start_scenario(self, name):
        self.runner.start(name, utcnow())

    def reset_scenario(self):
        open_outages = list(self.world.outages)
        self.runner.reset()
        now = utcnow()
        # restore every feeder that is still down, so the city really returns to normal
        self.ingest("power", [{"feeder": f, "status": "RESTORED", "area": ZONE_INFO[FEEDERS[f]]["name"],
                               "since": now.strftime("%Y-%m-%dT%H:%M:%SZ")} for f in open_outages], now)
        self.store.remove_tagged("scenario")
        self.world.rain_mm, self.world.temp_c = 0.0, 31.0
        self.world.rain_next_hour, self.world.temp_next_hour = 0.0, 31.0
        self.agent.prev_status.clear()
        self.agent.cooldown.clear()
        self.agent.alerts.clear()
        self.board.clear()
        self.force_weather = True

    def kill_feed(self, name):
        self.world.killed.add(name)

    def revive_feed(self, name):
        self.world.killed.discard(name)
        if name == "weather":
            self.force_weather = True

    def raw_vs_normalized(self, per_feed=2):
        out = []
        feeds = [("weather", lambda e: e.category == "weather"),
                 ("air (CPCB, real)", lambda e: e.source == "cpcb"),
                 ("air (sensor)", lambda e: e.source == "sim-air"),
                 ("traffic", lambda e: e.category == "traffic"),
                 ("transit", lambda e: e.category == "transit"),
                 ("complaint", lambda e: e.category == "complaint"),
                 ("power", lambda e: e.category == "power")]
        for label, pred in feeds:
            for e in self.store.latest(per_feed, pred):
                d = e.to_dict()
                out.append({"feed": label, "raw": d.pop("raw"), "normalized": d})
        return out


    # ---------- backtest, workflow, resident reports ----------
    def backtest(self):
        if self.backtest_cache is None:
            self.backtest_cache = run_backtest(self)   # ~1 s, history is fixed so compute once
        return self.backtest_cache

    REPORT_CATEGORIES = ["waterlogging", "power_cut", "streetlight", "pothole", "garbage", "traffic_signal", "noise"]

    def resident_report(self, client, zone_id, category, now=None):
        """A resident report joins the complaints feed. Privacy: no text, no personal location
        (we place it near the zone center). Abuse guard: one report per person, zone and category
        per 30 min, so a spike (>= 3 reports) needs at least 3 different people."""
        import random
        now = now or utcnow()
        if zone_id not in ZONE_INFO:
            raise ValueError("unknown zone")
        if category not in self.REPORT_CATEGORIES:
            raise ValueError("unknown category")
        key = (client, zone_id, category)
        last = self.report_log.get(key)
        if last and now - last < timedelta(minutes=30):
            wait = 30 - int((now - last).total_seconds() // 60)
            raise PermissionError(f"already reported; try again in {wait} min")
        self.report_log[key] = now
        lat, lon = ZONE_INFO[zone_id]["center"]
        raw = {"ticket": f"RES-{int(now.timestamp())}{random.randint(100, 999)}",
               "category": category.replace("_", " ").title(),
               "lat": lat + random.uniform(-0.003, 0.003), "lng": lon + random.uniform(-0.003, 0.003),
               "created": int(now.timestamp())}
        evs = normalize_complaint(raw, ("resident",) + tuple(self.world.tags))
        for ev in evs:
            ev.source = "resident-report"
            self.store.add(ev)
        return {"ticket": raw["ticket"], "zone_id": zone_id, "category": category}

    # ---------- analytics / product APIs ----------
    def analytics(self, hours=6, interval_min=15):
        now = utcnow()
        hours = max(1, min(int(hours), 72))
        interval_min = max(5, min(int(interval_min), 60))
        start = max(self.history_start or (now - timedelta(hours=hours)), now - timedelta(hours=hours))
        # Do not sample before the history has enough context for a 3-hour detection window.
        floor = (self.history_start + timedelta(hours=3)) if self.history_start else start
        start = max(start, floor)
        points = []
        t = start
        while t <= now:
            snap = self.compute_state(t, mode="replay")
            points.append({
                "ts": t.isoformat(),
                "city_score": snap["city"]["score"],
                "city_bpm": snap["city"]["bpm"],
                "zones": {z["id"]: {"score": z["score"], "status": z["status"], "bpm": z["bpm"]} for z in snap["zones"]},
                "anomaly_count": len(snap["anomalies"]),
                "link_count": len(snap["links"]),
            })
            t += timedelta(minutes=interval_min)
        current = self.compute_state(now)
        category_breakdown = {}
        for a in current["anomalies"]:
            bucket = a["category"]
            category_breakdown[bucket] = category_breakdown.get(bucket, 0) + 1
        worst = sorted(current["zones"], key=lambda z: z["score"])[:3]
        return {
            "generated_at": now.isoformat(),
            "hours": hours,
            "interval_min": interval_min,
            "points": points,
            "category_breakdown": category_breakdown,
            "worst_zones": worst,
            "city": current["city"],
        }

    def zone_detail(self, zone_id):
        current = self.compute_state(utcnow())
        zone = next((z for z in current["zones"] if z["id"] == zone_id), None)
        if zone is None:
            return None
        series = self.analytics(hours=6, interval_min=15)
        trend = [{"ts": p["ts"], **p["zones"].get(zone_id, {})} for p in series["points"] if zone_id in p["zones"]]
        return {
            "zone": zone,
            "history": trend,
            "forecast": next((f for f in current["forecast"] if f["zone_id"] == zone_id), None),
            "anomalies": [a for a in current["anomalies"] if a["zone_id"] in (zone_id, "city")],
            "links": [l for l in current["links"] if l["zone_id"] == zone_id],
            "events": [e for e in current["ticker"] if e["zone"] == zone["name"]][:20],
        }

    def incidents(self, hours=6, zone_id=None):
        now = utcnow()
        events = self.store.window(now - timedelta(hours=max(1, min(int(hours), 24))), now)
        if zone_id:
            events = [e for e in events if e.zone_id in (zone_id, "city")]
        rows = [e.to_dict() | {"zone_name": zone_name(e.zone_id)} for e in reversed(events)]
        return {"generated_at": now.isoformat(), "hours": hours, "zone_id": zone_id, "events": rows[:250]}

    # ---------- async loops ----------
    async def sim_loop(self):
        while True:
            now = utcnow()
            if self.runner.tick(now):
                raw = synthetic_weather_raw(now, self.world.rain_mm, self.world.temp_c, "scenario")
                self.ingest("weather", [raw], now)
            for feed, fn in SIMULATORS.items():
                if feed in self.world.killed:
                    continue
                self.ingest(feed, fn(self.world, now, 1.0), now)
            await asyncio.sleep(1)

    async def weather_loop(self):
        next_fetch = utcnow()
        while True:
            now = utcnow()
            if now < next_fetch and not self.force_weather:
                await asyncio.sleep(5)
                continue
            self.force_weather = False
            next_fetch = now + timedelta(minutes=10)
            if self.world.weather_override is None and "weather" not in self.world.killed:
                raw = await fetch_weather_raw()
                self.feeds["weather"]["source"] = "open-meteo" if raw else "synthetic-fallback"
                raw = raw or fallback_weather_raw(self.world)
                cur = raw["current"]
                self.world.rain_mm = float(cur.get("precipitation") or 0)
                self.world.temp_c = float(cur.get("temperature_2m") or 31)
                self.world.rain_next_hour, self.world.temp_next_hour = next_hour_from_raw(raw)
                self.ingest("weather", [raw], now)
            elif self.world.weather_override is not None:
                self.feeds["weather"]["last_ok"] = now

    async def air_loop(self):
        while True:
            pm = await fetch_city_pm25()
            if pm is not None:
                self.world.pm_base = pm
            await asyncio.sleep(1800)

    async def cpcb_loop(self):
        """Real CPCB stations every 15 min. Zones with a live station stop using simulated air sensors."""
        while True:
            recs = None if "cpcb" in self.world.killed else await fetch_cpcb_records()
            if recs:
                now = utcnow()
                for raw in recs:
                    for ev in normalize("cpcb", raw):
                        self.store.add(ev)
                        self.world.cpcb_zones[ev.zone_id] = now
                self.feeds["cpcb"]["last_ok"] = now
            await asyncio.sleep(900)

    async def traffic_loop(self):
        """Real TomTom traffic every 10 min when a key is set; otherwise sim_traffic runs in sim_loop."""
        while True:
            raws = None if "traffic" in self.world.killed else await fetch_traffic_raws()
            self.world.real_traffic = bool(raws)
            self.feeds["traffic"]["source"] = "tomtom" if raws else "sim (TomTom if key)"
            if raws:
                self.ingest("traffic", raws, utcnow())
            await asyncio.sleep(600)

    async def summary_loop(self):
        while True:
            snap = self.snapshot
            if snap and snap["_sig"] != self.llm_cache["sig"]:
                text, note = await llm_summary(snap["_facts"])
                # remember the state we tried, so we only call the LLM again when the state changes
                self.llm_cache = {"text": text, "sig": snap["_sig"], "note": note}
                if not text:
                    print(f"[summary] using template ({note})")
            await asyncio.sleep(10)

    async def engine_loop(self):
        while True:
            now = utcnow()
            snap = self.compute_state(now)
            self.board.sync(now, snap["anomalies"])
            for alert in self.agent.review(now, snap["zones"], snap["_links"]):
                asyncio.create_task(send_telegram(alert["message"]))
                zone_chat = config.TELEGRAM_ZONE_CHATS.get(alert.get("zone"))
                zone = next((z for z in snap["zones"] if z["id"] == alert.get("zone")), None)
                if zone_chat and zone and alert["message"].startswith("ALERT"):
                    # residents get the plain bilingual message, not the officer text
                    r = zone["resident"]
                    tips = " ".join(r["tips_en"][:2])
                    asyncio.create_task(send_telegram(f"{r['en']} {tips}\n\n{r['hi']}", chat_id=zone_chat,
                                                      prefix="CityPulse alert: "))
            snap["alerts"] = list(self.agent.alerts)
            self.snapshot = snap
            payload = self.public(snap)
            for q in list(self.listeners):
                while q.qsize() >= 2:          # slow client: drop old snapshots, keep newest
                    q.get_nowait()
                q.put_nowait(payload)
            await asyncio.sleep(config.TICK_SECONDS)


ENGINE = Engine()
SCENARIO_LIST = [{"name": k, "title": v["title"]} for k, v in SCENARIOS.items()]
