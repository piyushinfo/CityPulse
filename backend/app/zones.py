"""City zones for Jaipur. Centers are approximate; each zone is a hexagon ~2.6 km across.
To use another city: change names/centers here and CITY_LAT/LON in .env."""
import math

ZONES = [
    # id, name, Hindi name, lat, lon, flood_prone
    ("z1", "Walled City", "परकोटा (पुराना शहर)", 26.9239, 75.8267, True),
    ("z2", "Vaishali Nagar", "वैशाली नगर", 26.9115, 75.7420, False),
    ("z3", "Mansarovar", "मानसरोवर", 26.8580, 75.7630, True),
    ("z4", "Malviya Nagar", "मालवीय नगर", 26.8540, 75.8150, False),
    ("z5", "Tonk Road / Sanganer", "टोंक रोड / सांगानेर", 26.8190, 75.7960, False),
    ("z6", "Sitapura Industrial", "सीतापुरा औद्योगिक क्षेत्र", 26.7780, 75.8430, False),
    ("z7", "Jagatpura", "जगतपुरा", 26.8260, 75.8660, True),
    ("z8", "Amer Road / Jal Mahal", "आमेर रोड / जल महल", 26.9540, 75.8460, False),
]

R_LAT = 0.012  # hexagon radius in degrees latitude (~1.3 km)


def _hexagon(lat, lon):
    r_lon = R_LAT / math.cos(math.radians(lat))
    return [[round(lat + R_LAT * math.sin(math.radians(a)), 6),
             round(lon + r_lon * math.cos(math.radians(a)), 6)] for a in range(0, 360, 60)]


ZONE_INFO = {
    zid: {"id": zid, "name": name, "name_hi": hi, "center": [lat, lon], "flood_prone": fp,
          "polygon": _hexagon(lat, lon)}
    for zid, name, hi, lat, lon, fp in ZONES
}
ZONE_IDS = [z[0] for z in ZONES]
NAME_TO_ID = {info["name"].lower(): zid for zid, info in ZONE_INFO.items()}
# the power utility uses short area names; map those too
NAME_TO_ID.update({"walled city": "z1", "pink city": "z1", "vaishali": "z2", "mansarovar": "z3",
                   "malviya nagar": "z4", "sanganer": "z5", "tonk road": "z5", "sitapura": "z6",
                   "jagatpura": "z7", "amer": "z8", "jal mahal": "z8"})


def point_in_polygon(lat, lon, poly):
    """Ray casting. poly = [[lat, lon], ...]."""
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def zone_for_point(lat, lon, max_km=3.0):
    """Zone containing the point, else the nearest zone within max_km, else None."""
    for zid, info in ZONE_INFO.items():
        if point_in_polygon(lat, lon, info["polygon"]):
            return zid
    best, best_d = None, 1e9
    for zid, info in ZONE_INFO.items():
        d = math.hypot(lat - info["center"][0], (lon - info["center"][1]) * math.cos(math.radians(lat))) * 111
        if d < best_d:
            best, best_d = zid, d
    return best if best_d <= max_km else None


def zone_name(zid, lang="en"):
    if zid == "city":
        return "City-wide" if lang == "en" else "पूरे शहर में"
    info = ZONE_INFO.get(zid, {})
    return info.get("name_hi" if lang == "hi" else "name", zid)


# Transit stops (synthetic) and air sensors, both mapped by location/id
STOPS = {}
for i, (zid, name, hi, lat, lon, fp) in enumerate(ZONES):
    STOPS[f"S{2*i+1:02d}"] = (lat + 0.003, lon - 0.004)
    STOPS[f"S{2*i+2:02d}"] = (lat - 0.003, lon + 0.004)
ROUTES = {
    "JB-1": ["S01", "S02", "S07", "S08", "S09", "S10"],     # Walled City - Malviya Nagar - Tonk Road
    "JB-2": ["S03", "S04", "S01", "S15", "S16"],            # Vaishali Nagar - Walled City - Amer Road
    "JB-3": ["S05", "S06", "S11", "S12", "S13", "S14"],     # Mansarovar - Sitapura - Jagatpura
}
SENSORS = {f"AQ-{i+1:02d}": zid for i, zid in enumerate(ZONE_IDS)}
FEEDERS = {f"FDR-{zid.upper()}-{k}": zid for zid in ZONE_IDS for k in (1, 2)}
