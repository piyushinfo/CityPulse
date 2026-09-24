"""Pulse score per zone: 100 = calm. Each active anomaly adds stress by category weight x severity.
stress = 1 - product(1 - weight * severity)      score = 100 * (1 - stress)
bpm = 60 + (100 - score) * 0.6   -> 60 bpm calm ... 120 bpm critical"""
from ..zones import ZONE_IDS, ZONE_INFO

WEIGHTS = {"weather": 0.5, "air": 0.5, "power": 0.8, "transit": 0.6, "complaint": 0.7, "traffic": 0.5}


def status_of(score):
    return "calm" if score >= 75 else ("watch" if score >= 50 else "alert")


def zone_pulses(anomalies, partial_feeds):
    zones = []
    for zid in ZONE_IDS:
        active = [a for a in anomalies if a.zone_id in (zid, "city")]
        keep = 1.0
        for a in active:
            keep *= 1 - WEIGHTS.get(a.category, 0.5) * a.severity
        score = round(100 * keep)
        zones.append({"id": zid, "name": ZONE_INFO[zid]["name"], "score": score,
                      "bpm": round(60 + (100 - score) * 0.6), "status": status_of(score),
                      "active": [a.id for a in active], "partial": bool(partial_feeds)})
    avg = round(sum(z["score"] for z in zones) / len(zones))
    worst = min(zones, key=lambda z: z["score"])
    city = {"score": avg, "bpm": round(60 + (100 - avg) * 0.6), "status": status_of(worst["score"]),
            "worst_zone": worst["id"], "partial": bool(partial_feeds)}
    return city, zones
