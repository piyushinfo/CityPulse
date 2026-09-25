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
    """Returns raw CPCB records (PM2.5 only) for the city, or None.
    data.gov.in is slow and occasionally flaky, so this allows more time and retries once."""
    if not (config.USE_REAL_APIS and config.DATAGOVIN_API_KEY):
        return None
    import httpx
    params = {"api-key": config.DATAGOVIN_API_KEY, "format": "json", "limit": 100,
              "filters[city]": config.CPCB_CITY, "filters[pollutant_id]": "PM2.5"}
    last_err = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r = await client.get(CPCB_URL, params=params)
                if r.status_code != 200:
                    last_err = f"HTTP {r.status_code}: {r.text[:200]!r}"
                    continue
                try:
                    data = r.json()
                except ValueError:
                    last_err = f"non-JSON response (first 200 chars): {r.text[:200]!r}"
                    continue
                recs = data.get("records", [])
                if not recs:
                    # not an error: the key and city are fine, there's just no live station right now
                    total = data.get("total") or data.get("count")
                    print(f"[air] CPCB returned 0 records for city={config.CPCB_CITY!r} "
                          f"(reported total={total}); using simulated sensors")
                    return None
                return recs
        except Exception as e:
            last_err = f"{type(e).__name__}: {e!r}"
    print(f"[air] CPCB fetch failed after retry, using simulated sensors -- {last_err}")
    return None