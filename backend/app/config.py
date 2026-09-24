"""All settings in one place, read from environment / .env."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get(name, default):
    return os.getenv(name, default) or default


GROQ_API_KEY = _get("GROQ_API_KEY", "")
GROQ_MODEL = _get("GROQ_MODEL", "llama-3.3-70b-versatile")
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID", "")
CITY_NAME = _get("CITY_NAME", "Jaipur")
CITY_LAT = float(_get("CITY_LAT", "26.8800"))
CITY_LON = float(_get("CITY_LON", "75.8000"))
# data.gov.in (CPCB real-time air quality). Default = public sample key (rate-limited); register for your own.
DATAGOVIN_API_KEY = _get("DATAGOVIN_API_KEY", "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b")
CPCB_CITY = _get("CPCB_CITY", "Jaipur")
TOMTOM_API_KEY = _get("TOMTOM_API_KEY", "")   # optional: real traffic flow; simulated when empty
CORS_ORIGINS = [o.strip() for o in _get("CORS_ORIGINS", "http://localhost:3000").split(",")]
HISTORY_DAYS = int(_get("HISTORY_DAYS", "3"))
TICK_SECONDS = float(_get("TICK_SECONDS", "5"))
WINDOW_MIN = int(_get("WINDOW_MIN", "30"))          # anomaly window
LINK_WINDOW_MIN = int(_get("LINK_WINDOW_MIN", "45"))  # max gap between linked anomalies
USE_REAL_APIS = _get("USE_REAL_APIS", "true").lower() == "true"

# Per-zone resident alert channels, e.g. "z1:-1001234567890,z3:-1009876543210" (Telegram group/channel ids)
TELEGRAM_ZONE_CHATS = dict(p.split(":", 1) for p in _get("TELEGRAM_ZONE_CHATS", "").split(",") if ":" in p)
