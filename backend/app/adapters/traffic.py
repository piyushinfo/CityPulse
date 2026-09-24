"""Real road congestion from TomTom Traffic Flow (free tier, needs TOMTOM_API_KEY).
One request per zone center every 10 minutes (8 zones x 144/day = well under the free daily limit).
Without a key, sim_traffic in simulators.py produces the same shape."""
from datetime import datetime, timezone

from .. import config
from ..zones import ZONE_INFO

URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


async def fetch_traffic_raws():
    """Returns a list of TomTom-shaped dicts (one per zone), or None if no key / all failed."""
    if not (config.USE_REAL_APIS and config.TOMTOM_API_KEY):
        return None
    out = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            for zid, info in ZONE_INFO.items():
                lat, lon = info["center"]
                r = await client.get(URL, params={"point": f"{lat},{lon}", "key": config.TOMTOM_API_KEY})
                if r.status_code != 200:
                    continue
                data = r.json()
                data["_fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                data["_source"] = "tomtom"
                out.append(data)
    except Exception as e:
        print(f"[traffic] TomTom fetch failed, using simulation: {e}")
        return None
    return out or None
