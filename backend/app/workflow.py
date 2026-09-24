"""Officer workflow: every anomaly becomes an incident card that officers can
acknowledge -> assign -> resolve. The board tracks response times, which is the
operational metric a city actually cares about ("how fast did we react?")."""
from datetime import timedelta

# Which department usually owns which signal (real Jaipur bodies; edit to your city)
DEPARTMENTS = {
    "complaint:waterlogging": "JMC Drainage",
    "weather:heavy_rain": "JMC Drainage",
    "power:outage": "JVVNL (Power)",
    "complaint:power_cut": "JVVNL (Power)",
    "weather:heatwave": "District Disaster Cell",
    "traffic:congestion": "Jaipur Traffic Police",
    "complaint:traffic_signal": "Jaipur Traffic Police",
    "transit:delays": "JCTSL (City Buses)",
    "air:pm25": "RSPCB (Pollution Board)",
    "complaint:garbage": "JMC Sanitation",
    "complaint:streetlight": "JMC Electrical",
    "complaint:pothole": "JMC Roads",
    "complaint:noise": "Jaipur Police",
}
TEAMS = sorted(set(DEPARTMENTS.values()))
ACTIONS = {  # action -> (allowed from, new status)
    "acknowledge": ({"open", "cleared"}, "acknowledged"),
    "assign": ({"open", "acknowledged", "assigned", "cleared"}, "assigned"),
    "resolve": ({"open", "acknowledged", "assigned", "cleared"}, "resolved"),
    "reopen": ({"resolved"}, "open"),
}


def _signal(a):
    """anomaly dict -> signal key, e.g. 'z1:complaint:waterlogging' -> 'complaint:waterlogging'."""
    parts = a["id"].split(":")
    return ":".join(parts[1:]) if parts[0] != "city" else ":".join(parts[1:])


class IncidentBoard:
    def __init__(self):
        self.items = {}

    def sync(self, now, anomalies):
        """Open a card for each new anomaly; mark cards whose signal has ended."""
        seen = set()
        for a in anomalies:
            key = f"{a['id']}@{a['start'][:16]}"
            seen.add(key)
            card = self.items.get(key)
            if card is None:
                sig = _signal(a)
                self.items[key] = {
                    "id": key, "anomaly_id": a["id"], "zone_id": a["zone_id"], "zone_name": a["zone_name"],
                    "category": a["category"], "label": a["label"], "text": a["text"],
                    "severity": a["severity"], "peak_severity": a["severity"],
                    "suggested_team": DEPARTMENTS.get(sig, "JMC Control Room"),
                    "status": "open", "assignee": None, "active": True,
                    "opened_at": now.isoformat(), "acknowledged_at": None, "resolved_at": None,
                    "history": [{"ts": now.isoformat(), "action": "opened", "by": "CityPulse"}],
                }
            else:
                card.update(text=a["text"], severity=a["severity"], active=True,
                            peak_severity=max(card["peak_severity"], a["severity"]))
        for key, card in self.items.items():
            if key not in seen and card["active"]:
                card["active"] = False
                card["history"].append({"ts": now.isoformat(), "action": "signal ended", "by": "CityPulse"})
                if card["status"] == "open":          # nobody touched it: close it quietly
                    card["status"] = "cleared"

    def act(self, key, action, now, assignee=None, note=None, by="officer"):
        card = self.items.get(key)
        if card is None:
            raise KeyError(key)
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action}")
        allowed, new = ACTIONS[action]
        if card["status"] not in allowed:
            raise ValueError(f"cannot {action} an incident that is {card['status']}")
        if action == "assign":
            card["assignee"] = assignee or card["suggested_team"]
        card["status"] = new
        if new in ("acknowledged", "assigned") and not card["acknowledged_at"]:
            card["acknowledged_at"] = now.isoformat()
        if new == "resolved":
            card["resolved_at"] = now.isoformat()
        if action == "reopen":
            card["resolved_at"] = None
        entry = {"ts": now.isoformat(), "action": action, "by": by}
        if assignee:
            entry["assignee"] = card["assignee"]
        if note:
            entry["note"] = note[:280]
        card["history"].append(entry)
        return card

    def board(self, include_cleared=False):
        cards = [c for c in self.items.values() if include_cleared or c["status"] != "cleared"]
        cards.sort(key=lambda c: (c["status"] == "resolved", not c["active"], -c["peak_severity"]))
        return {"cards": cards[:200], "teams": TEAMS, "metrics": self.metrics()}

    def metrics(self):
        from datetime import datetime

        def mins(a, b):
            return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60

        ack = [mins(c["opened_at"], c["acknowledged_at"]) for c in self.items.values() if c["acknowledged_at"]]
        res = [mins(c["opened_at"], c["resolved_at"]) for c in self.items.values() if c["resolved_at"]]
        counts = {}
        for c in self.items.values():
            counts[c["status"]] = counts.get(c["status"], 0) + 1
        return {"counts": counts,
                "open_active": sum(1 for c in self.items.values() if c["active"] and c["status"] != "resolved"),
                "mean_minutes_to_acknowledge": round(sum(ack) / len(ack), 1) if ack else None,
                "mean_minutes_to_resolve": round(sum(res) / len(res), 1) if res else None}

    def clear(self):
        self.items.clear()
