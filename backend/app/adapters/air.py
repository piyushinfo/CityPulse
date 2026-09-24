"""Real air quality.
1) CPCB station readings for the city via data.gov.in (dataset 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69).
   Each station is mapped to the nearest zone; zones with a live station use it instead of the simulation.
2) Open-Meteo city PM2.5, which sets the baseline for the simulated sensors in zones without a station.
Both fail soft: on error the app keeps the last value / the simulation."""
from .. import config

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
CPCB_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"


async def fetch_city_pm25():
    if not config.USE_REAL_APIS:
        return None
    try:
        import httpx
        params = {"latitude": config.CITY_LAT, "longitude": config.CITY_LON, "current": "pm2_5,pm10"}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(OPEN_METEO_URL, params=params)
            r.raise_for_status()
            return float(r.json()["current"]["pm2_5"])
    except Exception as e:
        print(f"[air] Open-Meteo fetch failed, keeping last value: {e}")
        return None


async def fetch_cpcb_records():
    """Returns raw CPCB records (PM2.5 only) for the city, or None."""
    if not (config.USE_REAL_APIS and config.DATAGOVIN_API_KEY):
        return None
    try:
        import httpx
        params = {"api-key": config.DATAGOVIN_API_KEY, "format": "json", "limit": 100,
                  "filters[city]": config.CPCB_CITY, "filters[pollutant_id]": "PM2.5"}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(CPCB_URL, params=params)
            r.raise_for_status()
            recs = r.json().get("records", [])
            return recs or None
    except Exception as e:
        print(f"[air] CPCB fetch failed, using simulated sensors: {e}")
        return None
