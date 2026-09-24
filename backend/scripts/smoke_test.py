"""Run from backend/:  python -m scripts.smoke_test
Checks history, baseline, lift, a replayed storm, and the monsoon scenario without starting the server."""
from datetime import timedelta
from app.engine import Engine, utcnow
from app.adapters.simulators import SIMULATORS, synthetic_weather_raw

E = Engine()
now = utcnow()
E.bootstrap(now)
assert len(E.store) > 10000, "history too small"
assert E.lift, "lift table empty"
start, _ = E.history_range
storm = E.compute_state(start + timedelta(hours=18.7), mode="replay")
assert storm["city"]["status"] == "alert", "replayed storm should be an alert"
print("replay storm:", storm["summary"]["text"][:120], "...")

E.start_scenario("monsoon")
E.runner.started = now
for i in range(90):
    t = now + timedelta(seconds=i)
    if E.runner.tick(t):
        E.ingest("weather", [synthetic_weather_raw(t, E.world.rain_mm, E.world.temp_c, "scenario")], t)
    for f, fn in SIMULATORS.items():
        E.ingest(f, fn(E.world, t, 1.0), t)
s = E.compute_state(now + timedelta(seconds=90))
z1 = next(z for z in s["zones"] if z["id"] == "z1")
assert z1["status"] == "alert", "Walled City should be in alert during monsoon"
assert s["links"], "monsoon should produce possible links"
print("monsoon: Walled City pulse", z1["score"], "| links:", len(s["links"]))
print("top link:", s["links"][0]["text"])
assert s["forecast"] and z1["resident"]["hi"], "forecast and Hindi resident text expected"
before = E.compute_state(start + timedelta(hours=16.8), mode="replay")
fz1 = next(f for f in before["forecast"] if f["zone_id"] == "z1")
assert fz1["direction"] == "worse", "forecast should warn before the replayed storm"
print("forecast 40 min before storm:", fz1["now"], "->", fz1["next_hour"], "|", fz1["reason_en"])
print("resident (hi):", z1["resident"]["hi"])

# ---------- product APIs (analytics, zone, incidents) ----------
an = E.analytics(6, 15)
assert an["points"] and "worst_zones" in an, "analytics shape"
zd = E.zone_detail("z1")
assert zd and zd["zone"]["id"] == "z1" and zd["history"], "zone detail shape"
assert E.zone_detail("nope") is None
assert "events" in E.incidents(6, "z1")
print("analytics / zone / incidents: ok")

# ---------- copilot grounding: numbers the model SAW must pass, invented ones must fail ----------
from app.ai.summarizer import validate
state = {"zones": s["zones"], "forecast": s["forecast"]}
real = next(z for z in s["zones"] if z["id"] == "z3")["score"]
ok, _ = validate(f"Mansarovar is at {real}/100.", {"facts": s["_facts"], "state": state}, max_len=700)
assert ok, "a zone score from state must validate"
bad, why = validate("Mansarovar is at 123.45/100.", {"facts": s["_facts"], "state": state}, max_len=700)
assert not bad and "numbers" in why
bad, why = validate("Flooding was caused by rain.", {"facts": s["_facts"], "state": state}, max_len=700)
assert not bad and "causal" in why
print("copilot validator: ok")

# ---------- officer workflow ----------
t = now + timedelta(seconds=90)
E.board.sync(t, s["anomalies"])
card = E.board.board()["cards"][0]
E.board.act(card["id"], "acknowledge", t + timedelta(minutes=2))
E.board.act(card["id"], "assign", t + timedelta(minutes=3))
assert E.board.items[card["id"]]["assignee"] == card["suggested_team"]
try:
    E.board.act(card["id"], "reopen", t)
    raise AssertionError("reopen of an unresolved card must fail")
except ValueError:
    pass
E.board.act(card["id"], "resolve", t + timedelta(minutes=12), note="drain cleared")
m = E.board.metrics()
assert m["mean_minutes_to_acknowledge"] == 2.0 and m["mean_minutes_to_resolve"] == 12.0, m
print("workflow:", card["label"], "->", card["suggested_team"], "| ack 2 min, resolve 12 min: ok")

# ---------- resident reports: one per person/zone/category per 30 min ----------
r = E.resident_report("1.2.3.4", "z2", "pothole", now=t)
assert r["ticket"].startswith("RES-")
try:
    E.resident_report("1.2.3.4", "z2", "pothole", now=t + timedelta(minutes=5))
    raise AssertionError("rate limit expected")
except PermissionError:
    pass
E.resident_report("5.6.7.8", "z2", "pothole", now=t)      # a different person is fine
for bad_input in (("x", "z99", "pothole"), ("x", "z2", "bomb")):
    try:
        E.resident_report(*bad_input, now=t)
        raise AssertionError("invalid input accepted")
    except ValueError:
        pass
print("resident reports: ok")

# ---------- backtest ----------
bt = E.backtest()["summary"]
assert bt["events_detected"] == "3/3", bt
assert bt["forecast_mae"] < bt["naive_mae"], "forecast must beat 'no change'"
print("backtest:", bt)
print("ALL CHECKS PASSED")
