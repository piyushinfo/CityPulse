"""Raw payload -> CivicEvent, one function per feed. Each feed has a DIFFERENT raw format on purpose:
  weather    Open-Meteo JSON, local IST time string without offset "2026-09-24T18:00"
  air        IoT sensor JSON, epoch milliseconds, sensor id -> zone
  transit    bus delay report, "24/09/2026 18:42:10 IST" string, stop code -> lat/lon -> zone
  complaints 311-style ticket, epoch seconds, lat/lng -> zone (point-in-polygon)
  power      utility feeder status, ISO-8601 UTC with "Z", area name -> zone
  cpcb       REAL CPCB station record (data.gov.in), "24-09-2026 14:00:00" IST, strings for numbers,
             station lat/lon -> nearest zone
  traffic    TomTom flowSegmentData (real or simulated), speeds -> congestion ratio, segment point -> zone
"""
from datetime import datetime, timezone, timedelta
import hashlib

from .schema import CivicEvent
from .zones import zone_for_point, STOPS, SENSORS, FEEDERS, NAME_TO_ID

IST = timezone(timedelta(hours=5, minutes=30))


def _now():
    return datetime.now(timezone.utc)


def _h(*parts):
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:10]


def _clamp(x):
    return max(0.0, min(1.0, x))


# ---------- weather (Open-Meteo) ----------
def rain_subtype(mm):
    # IMD-style hourly bands: light < 2.5, moderate 2.5-7.6, heavy >= 7.6 mm/h
    if mm >= 7.6:
        return "heavy_rain"
    if mm >= 2.5:
        return "moderate_rain"
    if mm > 0:
        return "light_rain"
    return "no_rain"


def normalize_weather(raw, tags=()):
    cur = raw["current"]
    local = datetime.strptime(cur["time"], "%Y-%m-%dT%H:%M")
    tz = IST if raw.get("timezone", "Asia/Kolkata") == "Asia/Kolkata" else timezone.utc
    ts = local.replace(tzinfo=tz).astimezone(timezone.utc)
    rain = float(cur.get("precipitation") or 0)
    temp = float(cur.get("temperature_2m") or 0)
    events = [CivicEvent(
        id=f"open-meteo:rain:{_h(cur['time'], rain, tags)}", source=raw.get("_source", "open-meteo"),
        category="weather", subtype=rain_subtype(rain), zone_id="city", ts_utc=ts, ingested_at=_now(),
        value=round(rain, 1), unit="mm/h", severity=_clamp(rain / 20.0), raw=raw, tags=list(tags))]
    if temp >= 42:
        events.append(CivicEvent(
            id=f"open-meteo:heat:{_h(cur['time'], temp, tags)}", source=raw.get("_source", "open-meteo"),
            category="weather", subtype="heatwave", zone_id="city", ts_utc=ts, ingested_at=_now(),
            value=round(temp, 1), unit="C", severity=_clamp((temp - 40) / 7), raw=raw, tags=list(tags)))
    return events


# ---------- air quality (IoT sensors) ----------
def normalize_air(raw, tags=()):
    zid = SENSORS.get(raw["sensor"])
    if not zid:
        return []
    pm = float(raw["reading"]["pm25"])
    ts = datetime.fromtimestamp(raw["epoch_ms"] / 1000, tz=timezone.utc)
    # CPCB PM2.5 bands: 61-90 moderate, 91-120 poor, 121-250 very poor
    return [CivicEvent(
        id=f"sim-air:{raw['sensor']}:{raw['epoch_ms']}", source="sim-air", category="air", subtype="pm25",
        zone_id=zid, ts_utc=ts, ingested_at=_now(), value=round(pm, 1), unit="ug/m3",
        severity=_clamp((pm - 60) / 150), raw=raw, tags=list(tags))]


# ---------- transit (bus delay reports) ----------
def normalize_transit(raw, tags=()):
    stop = STOPS.get(raw["stop_code"])
    if not stop:
        return []
    zid = zone_for_point(*stop)
    local = datetime.strptime(raw["reported_at"].replace(" IST", ""), "%d/%m/%Y %H:%M:%S")
    ts = local.replace(tzinfo=IST).astimezone(timezone.utc)
    mins = raw["delay_sec"] / 60
    return [CivicEvent(
        id=f"sim-transit:{_h(raw['route'], raw['stop_code'], raw['reported_at'], raw['delay_sec'])}",
        source="sim-transit", category="transit", subtype="bus_delay", zone_id=zid, ts_utc=ts,
        ingested_at=_now(), value=round(mins, 1), unit="min", severity=_clamp(mins / 30), raw=raw,
        tags=list(tags))]


# ---------- complaints (311-style) ----------
COMPLAINT_SEVERITY = {"waterlogging": 0.7, "power_cut": 0.6, "streetlight": 0.3, "pothole": 0.4,
                      "garbage": 0.3, "noise": 0.2, "traffic_signal": 0.6}


def normalize_complaint(raw, tags=()):
    zid = zone_for_point(raw["lat"], raw["lng"])
    if not zid:
        return []
    sub = raw["category"].strip().lower().replace(" ", "_")
    ts = datetime.fromtimestamp(raw["created"], tz=timezone.utc)
    # privacy: keep only ticket, category, time and coordinates rounded to ~100 m. No text, no names.
    safe = {"ticket": raw["ticket"], "category": raw["category"], "created": raw["created"],
            "lat": round(raw["lat"], 3), "lng": round(raw["lng"], 3)}
    return [CivicEvent(
        id=f"sim-complaints:{raw['ticket']}", source="sim-complaints", category="complaint", subtype=sub,
        zone_id=zid, ts_utc=ts, ingested_at=_now(), value=1, unit="report",
        severity=COMPLAINT_SEVERITY.get(sub, 0.3), raw=safe, tags=list(tags))]


# ---------- power (feeder status) ----------
def normalize_power(raw, tags=()):
    zid = NAME_TO_ID.get(raw["area"].lower()) or FEEDERS.get(raw["feeder"])
    if not zid:
        return []
    ts = datetime.strptime(raw["since"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    tripped = raw["status"].upper() == "TRIPPED"
    return [CivicEvent(
        id=f"sim-power:{raw['feeder']}:{raw['status']}:{raw['since']}", source="sim-power", category="power",
        subtype="feeder_trip" if tripped else "feeder_restored", zone_id=zid, ts_utc=ts, ingested_at=_now(),
        value=1 if tripped else 0, unit="feeder", severity=0.7 if tripped else 0.0, raw=raw, tags=list(tags))]


# ---------- real CPCB station (data.gov.in) ----------
def normalize_cpcb(raw, tags=()):
    val = raw.get("avg_value", raw.get("pollutant_avg"))
    if val in (None, "", "NA"):
        return []
    zid = zone_for_point(float(raw["latitude"]), float(raw["longitude"]))
    if not zid:
        return []
    local = datetime.strptime(raw["last_update"], "%d-%m-%Y %H:%M:%S")
    ts = local.replace(tzinfo=IST).astimezone(timezone.utc)
    pm = float(val)
    return [CivicEvent(
        id=f"cpcb:{_h(raw['station'], raw['last_update'])}", source="cpcb", category="air", subtype="pm25",
        zone_id=zid, ts_utc=ts, ingested_at=_now(), value=round(pm, 1), unit="ug/m3",
        severity=_clamp((pm - 60) / 150), raw=raw, tags=list(tags))]


# ---------- traffic (TomTom flowSegmentData, real or simulated) ----------
def normalize_traffic(raw, tags=()):
    f = raw["flowSegmentData"]
    pt = f["coordinates"]["coordinate"][0]
    zid = zone_for_point(pt["latitude"], pt["longitude"])
    if not zid or not f.get("freeFlowSpeed"):
        return []
    congestion = max(0.0, 1 - f["currentSpeed"] / f["freeFlowSpeed"])
    ts = datetime.strptime(raw["_fetched_at"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    src = raw.get("_source", "tomtom")
    return [CivicEvent(
        id=f"{src}:{zid}:{raw['_fetched_at']}", source=src, category="traffic", subtype="congestion",
        zone_id=zid, ts_utc=ts, ingested_at=_now(), value=round(congestion, 2), unit="ratio",
        severity=_clamp((congestion - 0.2) / 0.6), raw=raw, tags=list(tags))]


NORMALIZERS = {"weather": normalize_weather, "air": normalize_air, "transit": normalize_transit,
               "complaints": normalize_complaint, "power": normalize_power, "cpcb": normalize_cpcb,
               "traffic": normalize_traffic}


def normalize(feed, raw, tags=()):
    try:
        return NORMALIZERS[feed](raw, tags)
    except (KeyError, ValueError, TypeError) as e:
        print(f"[normalizer] dropped bad {feed} payload: {e}")
        return []
