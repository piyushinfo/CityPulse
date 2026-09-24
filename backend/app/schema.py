"""The common data model. Every feed becomes a CivicEvent before anything else touches it.
FROZEN after hour 2 of the hackathon."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class CivicEvent:
    id: str                 # "<source>:<source-specific id>"
    source: str             # open-meteo | sim-air | sim-transit | sim-complaints | sim-power
    category: str           # weather | air | transit | complaint | power
    subtype: str            # heavy_rain, pm25, bus_delay, waterlogging, feeder_trip ...
    zone_id: str            # z1..z8, or "city" for city-wide events
    ts_utc: datetime        # when it happened (UTC, tz-aware)
    ingested_at: datetime   # when we received it (UTC)
    value: Optional[float]  # mm/h, ug/m3, minutes, count ...
    unit: Optional[str]
    severity: float         # 0..1, normalized per category
    raw: dict = field(default_factory=dict)   # original payload (privacy-scrubbed)
    tags: list = field(default_factory=list)  # e.g. ["scenario"], ["history"]

    def to_dict(self):
        d = asdict(self)
        d["ts_utc"] = self.ts_utc.isoformat()
        d["ingested_at"] = self.ingested_at.isoformat()
        return d


@dataclass
class Anomaly:
    id: str
    zone_id: str
    category: str
    kind: str               # "spike" (z-score) or "threshold"
    label: str              # human words: "Waterlogging complaints spiking"
    severity: float         # 0..1
    start: datetime         # when it began (used to order links)
    observed: float         # e.g. 9 complaints in 30 min
    expected: Optional[float]  # baseline, for spikes
    z: Optional[float]
    evidence: list          # event ids

    def to_dict(self):
        d = asdict(self)
        d["start"] = self.start.isoformat()
        return d


@dataclass
class Link:
    id: str
    zone_id: str
    first: dict             # anomaly summary (category, label, start)
    second: dict
    gap_min: float
    lift: Optional[float]   # from history; None = not enough history
    confidence: str         # "strong pattern" | "some pattern" | "new, unverified"
    text: str               # always says "possibly linked"

    def to_dict(self):
        return asdict(self)
