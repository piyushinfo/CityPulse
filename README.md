# CityPulse — live civic health dashboard (AmiHacks Track B)

Five civic feeds (weather, air quality, transit, 311-style complaints, power) are normalized into one
`CivicEvent` schema, checked for anomalies against a 3-day baseline, linked when they co-occur, and shown as a
"heartbeat" per zone with a plain-language summary. Links are always labelled *possible*, never causes.

## Run locally
Backend (Python 3.10+):
    cd backend
    python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env                                  # optional: add GROQ_API_KEY
    python -m scripts.smoke_test                          # should end with ALL CHECKS PASSED
    uvicorn app.main:app --reload --port 8000             # docs at http://localhost:8000/docs

Frontend (Node 18+):
    cd frontend
    npm install
    cp .env.example .env.local
    npm run dev                                           # http://localhost:3000

## Demo
Click the gear icon (top right) → "Monsoon storm over the Walled City". Within ~30 s the Walled City turns red,
possible links appear, and the agent raises alerts. "Reset" returns to calm. Kill a feed to show graceful
degradation. "Replay last 3 days" replays the simulated history.

Other pages: `/resident` (mobile, Hindi + English, "my area" view) and `/explain` (raw vs normalized).
The map has a 2D/3D toggle; each zone's "Next hour" arrow is a transparent estimate (trend + weather forecast).

## Data
Real: Open-Meteo weather + hourly forecast + city air quality (no key); CPCB station PM2.5 via data.gov.in
(`DATAGOVIN_API_KEY`, sample key built in); TomTom traffic flow (optional `TOMTOM_API_KEY`).
Simulated (same shapes as the real APIs): buses, complaints, power feeders, per-zone air sensors, traffic.
City: Jaipur, 8 approximate zones. Change `backend/app/zones.py` and `.env` to use another city.
