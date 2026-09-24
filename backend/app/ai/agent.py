"""Monitoring agent: watches every snapshot, raises an alert when a zone ENTERS 'alert' status or
a strong-pattern link appears. 10-minute cooldown per key. Optional Telegram delivery."""
from collections import deque
from datetime import timedelta

from .. import config


class MonitorAgent:
    def __init__(self):
        self.prev_status = {}
        self.cooldown = {}
        self.alerts = deque(maxlen=30)

    def _fire(self, key, now, message, zone):
        last = self.cooldown.get(key)
        if last and now - last < timedelta(minutes=10):
            return None
        self.cooldown[key] = now
        alert = {"ts": now.isoformat(), "zone": zone, "message": message}
        self.alerts.appendleft(alert)
        return alert

    def review(self, now, zones, links):
        new = []
        for z in zones:
            before = self.prev_status.get(z["id"], "calm")
            if z["status"] == "alert" and before != "alert":
                a = self._fire(f"zone:{z['id']}", now, f"ALERT {z['name']}: pulse {z['score']}/100 "
                               f"({len(z['active'])} active issues).", z["id"])
                if a:
                    new.append(a)
            self.prev_status[z["id"]] = z["status"]
        seen_zones = set()
        for l in links:                      # only the strongest link per zone
            if l.zone_id in seen_zones:
                continue
            seen_zones.add(l.zone_id)
            if l.confidence == "strong pattern":
                a = self._fire(f"link:{l.id}", now, l.text, l.zone_id)
                if a:
                    new.append(a)
        return new


async def send_telegram(text, chat_id=None, prefix="CityPulse: "):
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if not (config.TELEGRAM_BOT_TOKEN and chat_id):
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                              json={"chat_id": chat_id, "text": prefix + text})
    except Exception as e:
        print(f"[agent] telegram failed: {e}")
