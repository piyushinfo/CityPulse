"""Backtest: replay the 3-day history through the SAME live code and score it.
Answers the judge question "how do you know it works?" with numbers:
  - detection delay: minutes from storm/heat start until an affected zone turns red
  - early warning: minutes BEFORE the event the forecast first said "worse"
  - false alarms: zone alerts during quiet weather, per day
  - forecast error: next-hour estimate vs what actually happened, compared with a
    naive "no change" forecast (the baseline any forecast must beat)
Honest caveat, shown in the UI: history is simulated, so this validates the pipeline,
not real-world accuracy."""
from datetime import timedelta

from ..history import EPISODES
from ..zones import ZONE_INFO

HEAVY_RAIN, HEAT = 7.6, 42.0


def _episodes(start):
    out = []
    for h0, dur, rain, temp in EPISODES:
        if rain >= HEAVY_RAIN:
            kind = "heavy_rain"
        elif temp is not None and temp >= HEAT:
            kind = "heat"
        else:
            continue  # light rain is not an event we should alert on
        out.append({"kind": kind, "start": start + timedelta(hours=h0), "end": start + timedelta(hours=h0 + dur),
                    "label": f"{'Storm' if kind == 'heavy_rain' else 'Heatwave'} ({rain or temp} {'mm/h' if kind == 'heavy_rain' else 'C'})"})
    return out


def run_backtest(engine):
    start, end = engine.history_range
    eps = _episodes(start)
    events_out = []

    for ep in eps:
        # which zones should react: flood-prone for rain, all for heat
        target = [z for z, i in ZONE_INFO.items() if i["flood_prone"]] if ep["kind"] == "heavy_rain" else list(ZONE_INFO)
        # detection: first 5-min step after start where a target zone is in alert
        detected, t = None, ep["start"]
        while t <= ep["end"] + timedelta(minutes=30):
            s = engine.compute_state(t, mode="replay")
            if any(z["status"] == "alert" for z in s["zones"] if z["id"] in target):
                detected = t
                break
            t += timedelta(minutes=5)
        # early warning: first 10-min step in the 2 h before start where the forecast says "worse" for a target zone
        warned, t = None, ep["start"] - timedelta(hours=2)
        while t < ep["start"]:
            s = engine.compute_state(t, mode="replay")
            if any(f["direction"] == "worse" for f in s["forecast"] if f["zone_id"] in target):
                warned = t
                break
            t += timedelta(minutes=10)
        peak = min(engine.compute_state(ep["start"] + (ep["end"] - ep["start"]) / 2, mode="replay")["zones"],
                   key=lambda z: z["score"])
        events_out.append({
            "label": ep["label"], "kind": ep["kind"], "start": ep["start"].isoformat(),
            "detected_after_min": None if detected is None else round((detected - ep["start"]).total_seconds() / 60),
            "warned_before_min": None if warned is None else round((ep["start"] - warned).total_seconds() / 60),
            "worst_zone": peak["name"], "worst_score": peak["score"],
        })

    # quiet periods = not in an episode and not within 2 h after one (recovery is not a false alarm)
    def quiet(t):
        return all(not (ep["start"] - timedelta(minutes=30) <= t <= ep["end"] + timedelta(hours=2)) for ep in eps)

    # sample every 30 min: false alarms + forecast accuracy
    t = start + timedelta(hours=4)
    quiet_samples, quiet_alert_zone_samples = 0, 0
    err_model, err_naive, n = 0.0, 0.0, 0
    series = []
    while t <= end - timedelta(hours=1):
        s = engine.compute_state(t, mode="replay")
        actual = engine.pulse_at(t + timedelta(hours=1))
        for f in s["forecast"]:
            err_model += abs(f["next_hour"] - actual[f["zone_id"]])
            err_naive += abs(f["now"] - actual[f["zone_id"]])
            n += 1
        if quiet(t):
            quiet_samples += 1
            quiet_alert_zone_samples += sum(1 for z in s["zones"] if z["status"] == "alert")
        series.append({"ts": t.isoformat(), "city": s["city"]["score"],
                       "worst": min(z["score"] for z in s["zones"])})
        t += timedelta(minutes=30)

    quiet_hours = quiet_samples * 0.5
    mae_model = round(err_model / n, 1) if n else None
    mae_naive = round(err_naive / n, 1) if n else None
    detected = [e for e in events_out if e["detected_after_min"] is not None]
    warned = [e for e in events_out if e["warned_before_min"] is not None]
    return {
        "history_start": start.isoformat(), "history_end": end.isoformat(),
        "events": events_out,
        "summary": {
            "events_detected": f"{len(detected)}/{len(events_out)}",
            "mean_detection_min": round(sum(e["detected_after_min"] for e in detected) / len(detected)) if detected else None,
            "events_warned_early": f"{len(warned)}/{len(events_out)}",
            "mean_warning_lead_min": round(sum(e["warned_before_min"] for e in warned) / len(warned)) if warned else None,
            # zone-alerts seen per 30-min check during quiet weather, scaled to a day across 8 zones
            "quiet_alerts_per_day": round(quiet_alert_zone_samples / max(quiet_hours, 1) * 24 / 2, 1),
            "quiet_hours_checked": quiet_hours,
            "forecast_mae": mae_model, "naive_mae": mae_naive,
            "forecast_improvement_pct": round((1 - mae_model / mae_naive) * 100) if mae_naive else None,
        },
        "series": series,
        "caveat": "Scored on the simulated 3-day history: it validates the detection and forecast pipeline, "
                  "not real-world accuracy. The early-warning lead assumes the weather forecast was right "
                  "(in replay it is the real next hour); real forecasts miss sometimes. With real feeds, "
                  "the same code produces real scores.",
    }
