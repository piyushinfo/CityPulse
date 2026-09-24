"""Plain-language summary. Template is always computed; LLM (Groq) is tried on top and only
accepted if it passes the grounding validator. Never shows unvalidated LLM text."""
import json
import re

from .. import config
from ..analysis.anomaly import describe
from ..zones import zone_name

BANNED = ["caused by", "because of", "due to", "led to", "results in", "resulted in"]


def build_facts(city, zones, anomalies, links, feeds):
    return {
        "city": config.CITY_NAME,
        "city_score": city["score"],
        "worst_zone": zone_name(city["worst_zone"]),
        "zones_not_calm": sorted([{"zone": z["name"], "score": z["score"], "status": z["status"]}
                                  for z in zones if z["status"] != "calm"], key=lambda z: z["score"]),
        "calm_zone_count": sum(1 for z in zones if z["status"] == "calm"),
        "anomalies": [describe(a) for a in sorted(
            anomalies, key=lambda a: (a.zone_id != city["worst_zone"], a.zone_id == "city", -a.severity))][:8],
        "possible_links": [l.text for l in sorted(links, key=lambda l: l.zone_id != city["worst_zone"])][:3],
        "feeds_down": [f["name"] for f in feeds if f["status"] != "live" and not f.get("optional")],
    }


def template_summary(facts):
    if not facts["anomalies"]:
        s = f"All {facts['calm_zone_count']} zones in {facts['city']} are calm right now. Nothing unusual in weather, roads, buses, complaints, power or air."
    else:
        bad = facts["zones_not_calm"]
        head = (f"{bad[0]['zone']} needs attention (pulse {bad[0]['score']}/100). " if bad
                else "Some unusual readings, but no zone is under stress. ")
        s = head + "; ".join(facts["anomalies"][:2]) + "."
        if facts["possible_links"]:
            s += " " + facts["possible_links"][0].split(". ")[0] + "."
        calm = facts["calm_zone_count"]
        s += f" {calm} other zones are calm." if calm else " No zone is fully calm right now."
    if facts["feeds_down"]:
        s += f" Note: {', '.join(facts['feeds_down'])} data is delayed, so this picture is partial."
    return s


def _numbers(text):
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)}


def validate(text, facts, max_len=420):
    """Reject if the LLM invents numbers, claims causation, or is too long.
    `facts` must be exactly what the LLM was shown, so every number it may quote is allowed."""
    if not text or len(text) > max_len:
        return False, "empty or too long"
    low = text.lower()
    for b in BANNED:
        if b in low:
            return False, f"causal wording '{b}'"
    allowed = _numbers(json.dumps(facts)) | {100.0}   # 100 = the pulse scale ("7/100"), always allowed
    extra = [n for n in _numbers(text) if n not in allowed]
    if extra:
        return False, f"numbers not in data: {extra}"
    return True, "ok"


SYSTEM = ("You write a 2-sentence status update for residents of a city. Use ONLY facts in the JSON. "
          "Do not add numbers that are not in the JSON. For possible links say 'possibly linked', never "
          "'caused by', 'because of' or 'due to'. Mention the most affected zone first. Plain words, no jargon, "
          "no emoji, under 60 words.")


GROQ_URL = "https://api.groq.com/openai/v1"
_model_in_use = {"id": None}   # remembers a working model after a fallback


async def _pick_available_model(client):
    """Ask Groq which models this key can use and pick a sensible chat model."""
    r = await client.get(f"{GROQ_URL}/models", headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"})
    r.raise_for_status()
    ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True)]
    skip = ("whisper", "tts", "guard", "embed", "vision", "playai")
    chat = [i for i in ids if not any(k in i.lower() for k in skip)]
    for pref in ("llama-3.3-70b", "llama", "gpt-oss", "qwen", "gemma", "mixtral"):
        for i in chat:
            if pref in i.lower():
                return i
    return chat[0] if chat else None


async def groq_chat(messages, max_tokens, temperature, timeout=15):
    """POST a chat completion. If the configured model is unknown/retired (404/400 'model'),
    switch automatically to a model the key can use. Errors carry Groq's own message."""
    import httpx
    async with httpx.AsyncClient(timeout=timeout) as client:
        model = _model_in_use["id"] or config.GROQ_MODEL
        for attempt in range(2):
            r = await client.post(f"{GROQ_URL}/chat/completions",
                                  headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                                  json={"model": model, "temperature": temperature, "max_tokens": max_tokens,
                                        "messages": messages})
            if r.status_code == 200:
                _model_in_use["id"] = model
                return r.json()["choices"][0]["message"]["content"].strip()
            try:
                detail = r.json().get("error", {}).get("message", r.text[:200])
            except ValueError:
                detail = r.text[:200]
            model_problem = r.status_code in (400, 404) and "model" in detail.lower()
            if attempt == 0 and model_problem:
                fallback = await _pick_available_model(client)
                if fallback and fallback != model:
                    print(f"[groq] model '{model}' unavailable ({detail}); switching to '{fallback}'")
                    model = fallback
                    continue
            raise RuntimeError(f"Groq {r.status_code}: {detail}")


async def llm_summary(facts):
    if not config.GROQ_API_KEY:
        return None, "no GROQ_API_KEY"
    try:
        text = await groq_chat([{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": json.dumps(facts)}], max_tokens=150, temperature=0.2,
                               timeout=12)
    except Exception as e:
        return None, f"llm error: {e}"
    ok, why = validate(text, facts)
    return (text, "ok") if ok else (None, f"rejected: {why}")


COPILOT_SYSTEM = (
    "You are CityPulse AI Copilot. Answer questions only from the supplied JSON facts/state. "
    "Do not invent events, values, times, zones, or numbers. Never claim causation; describe associations "
    "as possible links. Keep answers concise (under 90 words), practical, and clear. If the requested fact is "
    "not in the data, say that it is not available. Do not give emergency commands; recommend official sources "
    "for urgent action."
)


def _fallback_copilot(question, facts, state):
    q = question.lower()
    if "why" in q and ("pulse" in q or "score" in q):
        anomalies = facts.get("anomalies", [])
        head = anomalies[0] if anomalies else "no active anomalies"
        return f"CityPulse is using the current anomaly signals to explain the pulse. The strongest current signal is: {head}. The score is a composite indicator, not an official safety rating."
    if "worst" in q or "affected" in q:
        z = sorted(state["zones"], key=lambda x: x["score"])[:3]
        return "Most affected zones right now: " + "; ".join(f"{x['name']} ({x['score']}/100)" for x in z) + "."
    if "link" in q or "related" in q or "correlation" in q:
        ls = state.get("links", [])[:3]
        return "Current possible links: " + ("; ".join(f"{l['first']['label']} → {l['second']['label']} ({l['confidence']})" for l in ls) if ls else "none detected right now") + ". These are associations, not confirmed causes."
    if "next hour" in q or "forecast" in q:
        w = [f for f in state.get("forecast", []) if f["direction"] == "worse"][:3]
        return "Next-hour outlook: " + ("; ".join(f"{f['zone_id']} {f['now']}→{f['next_hour']}" for f in w) if w else "no zone is currently expected to worsen significantly") + "."
    if "feed" in q or "data" in q:
        down = [f["name"] for f in state.get("feeds", []) if f["status"] != "live" and not f.get("optional")]
        return "Feed health: " + (", ".join(down) + " need attention." if down else "all required feeds are currently live.")
    return facts.get("anomalies", ["CityPulse has no additional matching insight right now."])[0] if facts.get("anomalies") else "CityPulse has no active anomalies to explain right now."


async def copilot_answer(question, facts, state):
    fallback = _fallback_copilot(question, facts, state)
    if not config.GROQ_API_KEY:
        return fallback, "template", "GROQ_API_KEY not configured"
    payload = {"question": question, "facts": facts, "state": {
        "city": state.get("city"), "zones": state.get("zones"), "forecast": state.get("forecast"),
        "links": state.get("links"), "feeds": state.get("feeds")
    }}
    try:
        text = await groq_chat([{"role": "system", "content": COPILOT_SYSTEM},
                                {"role": "user", "content": json.dumps(payload)}], max_tokens=220, temperature=0.15)
        # validate against the SAME payload the model saw (facts + state), not facts alone;
        # 90 words is roughly 600 characters, so allow up to 700
        # (the question itself is excluded, so a number typed by the user can't "validate" itself)
        ok, why = validate(text, {"facts": payload["facts"], "state": payload["state"]}, max_len=700)
        if not ok:
            return fallback, "template", f"AI response rejected: {why}"
        return text, "llm", "grounded + validated"
    except Exception as e:
        return fallback, "template", f"LLM unavailable: {e}"
