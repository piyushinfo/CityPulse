# CityPulse upgraded UI — local setup

## Backend

```powershell
cd D:\citypulse\backend
venv\Scripts\activate
python -m scripts.smoke_test
uvicorn app.main:app --reload --port 8000
```

## Frontend

The upgraded UI adds `@deck.gl/extensions` and `@deck.gl/mesh-layers` because the 9.x Deck.gl geo-layers package imports them.

```powershell
cd D:\citypulse\frontend
npm install --legacy-peer-deps
npm run dev
```

Open http://localhost:3000.

## Environment variables

Backend: copy `.env.example` to `.env`. Add real values locally for:

- `GROQ_API_KEY`
- `DATAGOVIN_API_KEY`
- `TOMTOM_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Frontend: `.env.local` should contain:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Never commit real keys to GitHub or put them in frontend source code.

## Added API endpoints

- `GET /api/analytics?hours=6&interval_min=15`
- `GET /api/zone/{zone_id}`
- `GET /api/incidents?hours=6&zone=z1`
- `POST /api/copilot` with `{ "question": "..." }`

## Main UI additions

- Dark smart-city command center
- Responsive sidebar navigation
- Command search (Ctrl/Cmd + K)
- Live KPI strip
- Rich 2D/3D map presentation
- Clickable zone intelligence drawer
- Incident Center
- Zone Explorer
- Analytics & trend charts
- Correlation Lab
- Forecast center
- Historical Replay
- Data Feed Monitor + kill/revive controls
- Grounded AI Copilot
- Resident View redesign
- Explainability / raw-to-normalized evidence view
- Scenario Lab redesign

## Round 3 additions (review fixes + 4 features)

First, format the frontend (it was minified into one-line files):

```powershell
cd D:\citypulse\frontend
npm install --legacy-peer-deps
npm run format
```

Then run the tests. They now cover every endpoint and feature:

```powershell
cd D:\citypulse\backend
python -m scripts.smoke_test      # must end with ALL CHECKS PASSED
```

### Fixes
- Copilot: answers are now validated against the same data the model was shown (facts + zone scores + forecast),
  not facts alone. The user's own question is excluded, so a typed number can't "validate" itself. The limit is
  700 characters, and "/100" is always allowed. Before this, most correct answers fell back to the template.
- `/api/copilot` computes the city state once instead of three times.

### New pages
- `/operations`: officer board. Every anomaly becomes a card routed to its likely department
  (JMC Drainage, JVVNL, Traffic Police, JCTSL, RSPCB, ...). Acknowledge, assign and resolve, with
  mean time-to-acknowledge and time-to-resolve. Cards nobody touched close as "cleared".
- `/backtest`: replays the 3-day history through the live code and scores it: events detected,
  early-warning lead, forecast error vs a "no change" forecast, and calm-weather alerts per day. It has an honest caveat.
- `/resident` now has: Report an issue (7 categories, no text, no personal location), Alerts for my area
  (browser notification on turning red or forecast worse, while the page is open), and Read aloud (Hindi/English).

### New API
- `GET  /api/backtest`
- `GET  /api/workflow` · `POST /api/workflow/{id}` with `{ "action": "acknowledge|assign|resolve|reopen", "assignee": "...", "note": "..." }`
- `GET  /api/report/categories` · `POST /api/report` with `{ "zone_id": "z1", "category": "waterlogging" }`
  (one report per person, zone and category per 30 min, so a spike needs at least 3 different people)

### Per-zone Telegram alerts (optional)
Create one Telegram group per area, add your bot, and set
`TELEGRAM_ZONE_CHATS=z1:-1001234567890,z3:-1009876543210`. When a zone turns red, its group gets the plain
English + Hindi resident message with tips. The officer chat still gets the officer alert.
