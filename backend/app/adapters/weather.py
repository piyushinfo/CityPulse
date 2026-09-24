"""Real weather from Open-Meteo (free, no key). Falls back to synthetic if the call fails."""
from datetime import datetime, timezone, timedelta

from .. import config
from .simulators import synthetic_weather_raw

URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_weather_raw():
    """Returns an Open-Meteo shaped dict, or None on failure."""
    if not config.USE_REAL_APIS:
        return None
    try:
        import httpx
        params = {"latitude": config.CITY_LAT, "longitude": config.CITY_LON, "timezone": "Asia/Kolkata",
                  "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
                  "hourly": "precipitation,temperature_2m", "forecast_days": 2}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(URL, params=params)
            r.raise_for_status()
            data = r.json()
            data["_source"] = "open-meteo"
            return data
    except Exception as e:  # network down, rate-limited, bad JSON ...
        print(f"[weather] real fetch failed, using fallback: {e}")
        return None


def fallback_weather_raw(world):
    return synthetic_weather_raw(datetime.now(timezone.utc), world.rain_mm, world.temp_c, "synthetic-fallback")


def next_hour_from_raw(raw):
    """(rain mm/h, temp C) forecast for the next hour from Open-Meteo 'hourly', else the current values."""
    cur = raw["current"]
    fallback = (float(cur.get("precipitation") or 0), float(cur.get("temperature_2m") or 31))
    hourly = raw.get("hourly")
    if not hourly:
        return fallback
    try:
        now_local = datetime.strptime(cur["time"], "%Y-%m-%dT%H:%M")
        target = (now_local.replace(minute=0) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        i = hourly["time"].index(target)
        return float(hourly["precipitation"][i] or 0), float(hourly["temperature_2m"][i])
    except (KeyError, ValueError, IndexError, TypeError):
        return fallback
