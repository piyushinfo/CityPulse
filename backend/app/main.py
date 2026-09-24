"""FastAPI app: REST + WebSocket. Run: uvicorn app.main:app --reload --port 8000"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .engine import ENGINE, SCENARIO_LIST, FEED_TTL, utcnow
from .zones import ZONE_INFO


@asynccontextmanager
async def lifespan(app):
    ENGINE.bootstrap()
    ENGINE.snapshot = ENGINE.compute_state(utcnow())
    tasks = [asyncio.create_task(c) for c in (ENGINE.sim_loop(), ENGINE.weather_loop(), ENGINE.air_loop(),
                                               ENGINE.cpcb_loop(), ENGINE.traffic_loop(),
                                               ENGINE.engine_loop(), ENGINE.summary_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="CityPulse API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS + ["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True, "events": len(ENGINE.store), "time": utcnow().isoformat()}


@app.get("/api/zones")
def zones():
    return {"city": config.CITY_NAME, "center": [config.CITY_LAT, config.CITY_LON],
            "zones": list(ZONE_INFO.values())}


@app.get("/api/state")
def state():
    return ENGINE.public(ENGINE.snapshot or ENGINE.compute_state(utcnow()))


@app.get("/api/events")
def events(limit: int = 50, zone: str | None = None, category: str | None = None):
    evs = ENGINE.store.latest(min(limit, 500), lambda e: (zone is None or e.zone_id == zone)
                              and (category is None or e.category == category))
    return [e.to_dict() for e in evs]


@app.get("/api/raw-vs-normalized")
def raw_vs_normalized(per_feed: int = 2):
    return ENGINE.raw_vs_normalized(per_feed)


@app.get("/api/replay/range")
def replay_range():
    start, end = ENGINE.history_range
    return {"start": start.isoformat(), "end": end.isoformat()}


@app.get("/api/replay")
def replay(t: str):
    try:
        ts = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "t must be ISO-8601")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ENGINE.public(ENGINE.compute_state(ts, mode="replay"))


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": SCENARIO_LIST, "active": ENGINE.runner.status()}


@app.post("/api/scenario/reset")
def scenario_reset():
    ENGINE.reset_scenario()
    return {"ok": True}


@app.post("/api/scenario/{name}")
def scenario_start(name: str):
    try:
        ENGINE.start_scenario(name)
    except KeyError:
        raise HTTPException(404, f"unknown scenario {name}")
    return {"ok": True, "scenario": ENGINE.runner.status()}


@app.post("/api/feeds/{name}/{action}")
def feed_control(name: str, action: str):
    if name not in FEED_TTL or action not in ("kill", "revive"):
        raise HTTPException(404, "feed or action not found")
    (ENGINE.kill_feed if action == "kill" else ENGINE.revive_feed)(name)
    return {"ok": True, "killed": sorted(ENGINE.world.killed)}


@app.get("/api/alerts")
def alerts():
    return list(ENGINE.agent.alerts)


class CopilotRequest(BaseModel):
    question: str


@app.get("/api/analytics")
def analytics(hours: int = 6, interval_min: int = 15):
    return ENGINE.analytics(hours, interval_min)


@app.get("/api/zone/{zone_id}")
def zone_detail(zone_id: str):
    result = ENGINE.zone_detail(zone_id)
    if result is None:
        raise HTTPException(404, "zone not found")
    return result


@app.get("/api/incidents")
def incidents(hours: int = 6, zone: str | None = None):
    return ENGINE.incidents(hours, zone)


@app.post("/api/copilot")
async def copilot(req: CopilotRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "question is required")
    # one fresh internal state (it still has the private _facts key the public snapshot strips)
    internal = ENGINE.compute_state(utcnow())
    facts = internal["_facts"]
    from .ai.summarizer import copilot_answer
    answer, source, note = await copilot_answer(question, facts, internal)
    return {"question": question, "answer": answer, "source": source, "note": note}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    q = asyncio.Queue()
    ENGINE.listeners.add(q)
    try:
        if ENGINE.snapshot:
            await websocket.send_json(ENGINE.public(ENGINE.snapshot))
        while True:
            await websocket.send_json(await q.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ENGINE.listeners.discard(q)


# ---------- backtest ----------
@app.get("/api/backtest")
def backtest():
    return ENGINE.backtest()


# ---------- officer workflow ----------
class WorkflowAction(BaseModel):
    action: str                 # acknowledge | assign | resolve | reopen
    assignee: str | None = None
    note: str | None = None
    by: str | None = None


@app.get("/api/workflow")
def workflow(include_cleared: bool = False):
    return ENGINE.board.board(include_cleared)


@app.post("/api/workflow/{incident_id:path}")
def workflow_action(incident_id: str, body: WorkflowAction):
    try:
        card = ENGINE.board.act(incident_id, body.action, utcnow(), body.assignee, body.note, body.by or "officer")
    except KeyError:
        raise HTTPException(404, "incident not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return card


# ---------- resident reports ----------
class ResidentReport(BaseModel):
    zone_id: str
    category: str


@app.get("/api/report/categories")
def report_categories():
    return {"categories": ENGINE.REPORT_CATEGORIES}


@app.post("/api/report")
def resident_report(body: ResidentReport, request: Request):
    client = request.headers.get("x-forwarded-for", request.client.host if request.client else "anon").split(",")[0]
    try:
        return ENGINE.resident_report(client, body.zone_id, body.category)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError as e:
        raise HTTPException(429, str(e))
