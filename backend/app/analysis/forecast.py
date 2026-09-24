"""Next-hour outlook per zone. Deliberately simple and explainable:
  1. Trend: pulse now vs 15 minutes ago, carried forward one step (capped at +/-25).
  2. Weather: if the next hour's forecast is heavy rain or extreme heat, the zone is expected to fall
     to the MEDIAN pulse it reached under that condition in the 3-day history (only if that is lower).
     If bad weather is forecast to end, it is expected to recover halfway to its normal median.
It is an estimate, labelled as one. No hidden model."""
from collections import defaultdict
from datetime import timedelta
from statistics import median

HEAVY_RAIN, HEAT = 7.6, 42.0


def condition(rain, temp):
    if rain >= HEAVY_RAIN:
        return "heavy_rain"
    if temp >= HEAT:
        return "heat"
    return "normal"


def build_profile(pulse_at, cond_at, start, end, step_min=60):
    """pulse_at(t) -> {zone: score}; cond_at(t) -> condition. Returns {zone: {cond: median score}}."""
    samples = defaultdict(lambda: defaultdict(list))
    t = start + timedelta(hours=3)
    while t <= end:
        c = cond_at(t)
        for zid, score in pulse_at(t).items():
            samples[zid][c].append(score)
        t += timedelta(minutes=step_min)
    return {z: {c: round(median(v)) for c, v in conds.items() if len(v) >= 2} for z, conds in samples.items()}


def outlook(zones, prev_scores, rain_now, temp_now, rain_next, temp_next, profile):
    cond_now, cond_next = condition(rain_now, temp_now), condition(rain_next, temp_next)
    out = []
    for z in zones:
        zid, score = z["id"], z["score"]
        trend = score - prev_scores.get(zid, score)
        proj = score + max(-25, min(25, trend))
        med = profile.get(zid, {}).get(cond_next)
        reason_en, reason_hi = [], []
        if cond_next != "normal" and med is not None and med < proj:
            proj = med
            if cond_next == "heavy_rain":
                reason_en.append(f"heavy rain forecast ({rain_next} mm/h); in past storms this area fell to about {med}")
                reason_hi.append(f"भारी बारिश का पूर्वानुमान ({rain_next} मिमी/घंटा); पिछली बारिश में यहाँ पल्स लगभग {med} तक गिरा था")
            else:
                reason_en.append(f"extreme heat forecast ({temp_next} C); past heat took this area to about {med}")
                reason_hi.append(f"भीषण गर्मी का पूर्वानुमान ({temp_next}°C); पिछली गर्मी में यहाँ पल्स लगभग {med} तक गया था")
        elif cond_next == "normal" and cond_now != "normal" and med is not None and med > proj:
            proj = (score + med) / 2
            reason_en.append("the bad weather is forecast to ease")
            reason_hi.append("खराब मौसम के थमने का पूर्वानुमान है")
        if trend <= -8:
            reason_en.append("things got worse over the last 15 minutes")
            reason_hi.append("पिछले 15 मिनट में हालात बिगड़े हैं")
        elif trend >= 8:
            reason_en.append("things improved over the last 15 minutes")
            reason_hi.append("पिछले 15 मिनट में हालात सुधरे हैं")
        proj = int(round(max(0, min(100, proj))))
        direction = "worse" if proj <= score - 8 else ("better" if proj >= score + 8 else "steady")
        out.append({"zone_id": zid, "now": score, "next_hour": proj, "direction": direction,
                    "reason_en": "; ".join(reason_en) or "no change expected",
                    "reason_hi": "; ".join(reason_hi) or "कोई बदलाव अपेक्षित नहीं"})
    return out, {"rain_next_hour": rain_next, "temp_next_hour": temp_next, "condition_next": cond_next}
