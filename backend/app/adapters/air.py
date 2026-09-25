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
    data.gov.in is slow, and some hosts silently drop requests from cloud-provider IP ranges
    (Render/AWS/GCP included) rather than rejecting them -- that shows up as a timeout with no
    message. If the direct call times out, we retry once, then try a public read-only proxy as
    a different network path before giving up."""
    if not (config.USE_REAL_APIS and config.DATAGOVIN_API_KEY):
        return None
    import httpx
    from urllib.parse import urlencode, quote

    key = config.DATAGOVIN_API_KEY
    key_hint = f"{key[:6]}...len={len(key)}"
    params = {"api-key": key, "format": "json", "limit": 100,
              "filters[city]": config.CPCB_CITY, "filters[pollutant_id]": "PM2.5"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
               "Accept": "application/json"}
    full_url = f"{CPCB_URL}?{urlencode(params)}"

    def parse(data, via):
        recs = data.get("records", [])
        if not recs:
            total = data.get("total") or data.get("count")
            print(f"[air] CPCB returned 0 records for city={config.CPCB_CITY!r} via={via} "
                  f"key={key_hint} (reported total={total}); using simulated sensors")
            return None
        return recs

    last_err = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r = await client.get(CPCB_URL, params=params, headers=headers)
                if r.status_code != 200:
                    last_err = f"direct HTTP {r.status_code}: {r.text[:200]!r}"
                    continue
                return parse(r.json(), "direct")
        except Exception as e:
            last_err = f"direct {type(e).__name__}: {e!r}"

    try:
        proxied = "https://api.allorigins.win/raw?url=" + quote(full_url, safe="")
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.get(proxied, headers=headers)
            if r.status_code == 200:
                print(f"[air] CPCB succeeded via proxy (direct calls from Render are being blocked)")
                return parse(r.json(), "proxy")
            last_err = f"proxy HTTP {r.status_code}: {r.text[:200]!r}"
    except Exception as e:
        last_err = f"proxy {type(e).__name__}: {e!r}"

    print(f"[air] CPCB fetch failed on all paths, using simulated sensors -- key={key_hint} -- {last_err}")
    return None