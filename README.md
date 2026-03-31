# CrisisShield

CrisisShield is a local-first crisis monitoring dashboard focused on Lebanon.

It includes:

- a React + Vite frontend
- a FastAPI backend with seeded local data
- a live incident/news layer
- a separate "Official Feeds" section for outlet Telegram accounts
- a local chat API used by the in-app chatbot

The project is set up to run on localhost without needing a Supabase deployment.

## Local URLs

When the app is running locally:

- Frontend: `http://127.0.0.1:8080`
- Backend API: `http://127.0.0.1:8000`
- Backend health: `http://127.0.0.1:8000/health`
- Official feeds page: `http://127.0.0.1:8080/official-feeds`

## Project Structure

```text
.
|- src/                     Frontend app
|- backend/                 FastAPI backend
|- supabase/                Older Supabase functions kept in the repo
|- local-api-server.mjs     Local chat API for the chatbot
|- run-local.ps1            Starts the frontend, local chat API, and backend
|- run-backend.ps1          Starts only the FastAPI backend
`- docker-compose.yml       Optional infra stack for backend services
```

## Quick Start

Important:

- the downloaded folder contains another `snuggle-buddy-build-main` folder inside it
- you must run commands from the inner folder, the one that contains `package.json` and `run-local.ps1`

Correct project root:

```text
C:\Users\MahdiMortada\Downloads\snuggle-buddy-build-main\snuggle-buddy-build-main
```

Run the full local stack from the project root:

```powershell
.\run-local.ps1
```

What this does:

- uses the portable Node runtime stored in `.tools`
- starts the local chat API if it is not already running
- starts the FastAPI backend if it is not already running
- starts the Vite frontend on `127.0.0.1:8080`

If you only want the backend:

```powershell
.\run-backend.ps1
```

If you are starting from the outer folder, use these exact commands:

```powershell
cd C:\Users\MahdiMortada\Downloads\snuggle-buddy-build-main
cd .\snuggle-buddy-build-main
dir package.json
dir run-local.ps1
.\run-local.ps1
```

## Environment Files

Frontend env example:

- `.env.example`

Backend env example:

- `backend/.env.example`

Important frontend variables:

```env
VITE_BACKEND_URL="http://127.0.0.1:8000"
VITE_BACKEND_WS_URL="ws://127.0.0.1:8000/ws/live-feed"
VITE_BACKEND_DEV_EMAIL="admin@crisisshield.dev"
VITE_BACKEND_DEV_PASSWORD="admin12345"
```

Important backend variables:

```env
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
LIVE_NEWS_ENABLED=true
LIVE_NEWS_WINDOW_HOURS=24
LIVE_NEWS_LIMIT=25
OFFICIAL_FEEDS_ENABLED=true
OFFICIAL_FEED_LIMIT=24
OFFICIAL_FEED_EXTRA_CHANNELS_JSON=
```

## Default Local Login

The backend seeds a local admin user for development:

- Email: `admin@crisisshield.dev`
- Password: `admin12345`

## Main Features

### 1. Situation Dashboard

The dashboard shows:

- incidents
- alerts
- regional risk scores
- trend charts
- live backend connection status

### 2. Live News / Incidents

The backend fetches current Lebanon-related stories and exposes them through:

- `GET /api/v1/incidents/live`

The frontend uses those live incidents when available and falls back to seeded local data if needed.

### 3. Official Feeds

The app has a separate page for direct outlet-account posts:

- route: `/official-feeds`
- backend endpoint: `GET /api/v1/official-feeds`

Current built-in Telegram sources include:

- `LBCI`
- `MTV Lebanon`
- `Al Jadeed`
- `Al Manar`

Extra channels can be added without code changes by setting:

```env
OFFICIAL_FEED_EXTRA_CHANNELS_JSON=[
  {
    "publisher_name": "Example Source",
    "publisher_type": "social_media",
    "credibility": "high",
    "credibility_score": 70,
    "initials": "ES",
    "platform": "telegram",
    "handle": "example_handle",
    "account_label": "Example Source Channel"
  }
]
```

Notes:

- the official-feeds system currently uses public Telegram channels
- some Telegram channels may mirror X posts
- direct X API integration is not required for local use

### 4. Crisis Chat

The chatbot runs through the local Node API in `local-api-server.mjs`.

If chat responses fail, check:

- your `OPENAI_API_KEY`
- local API health/logs
- the browser/network console

## Backend API

Useful endpoints:

- `GET /health`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/dashboard/trends`
- `GET /api/v1/incidents`
- `GET /api/v1/incidents/live`
- `GET /api/v1/incidents/geo`
- `GET /api/v1/risk/current`
- `GET /api/v1/alerts`
- `GET /api/v1/official-feeds`
- `WS /ws/live-feed`

## Development Commands

Install frontend dependencies:

```powershell
npm install
```

Build the frontend:

```powershell
npm run build
```

Run backend tests:

```powershell
cd backend
python -m pytest
```

## Troubleshooting

### `.\run-local.ps1` is not recognized

You are probably in the outer folder instead of the real project root.

Use:

```powershell
cd C:\Users\MahdiMortada\Downloads\snuggle-buddy-build-main\snuggle-buddy-build-main
.\run-local.ps1
```

### `package.json` could not be found

You are in the wrong folder.

Check that these files exist before running anything:

```powershell
dir package.json
dir run-local.ps1
```

### `Port 8080 is already in use`

That usually means the app is already running on the correct port.

Open:

```text
http://127.0.0.1:8080/
```

If you want to stop the old process and restart:

```powershell
netstat -ano | findstr :8080
taskkill /PID <PID> /F
.\run-local.ps1
```

### The browser shows the wrong version

Use the correct URL:

```text
http://127.0.0.1:8080/
```

Then:

- close tabs using old ports like `8082`
- open a fresh tab on `8080`
- hard refresh with `Ctrl+F5`

## Docker

`docker-compose.yml` is included for optional development infrastructure such as:

- PostgreSQL/PostGIS
- MongoDB
- Elasticsearch
- Redis
- Kafka + Zookeeper

The local seeded backend can still run without those services.

## Current Local Status

This repository has already been verified locally with:

- frontend production build
- backend tests
- live localhost frontend
- live localhost backend
- working official-feeds endpoint

## Notes

- The repo still contains Supabase functions, but the local development flow no longer depends on deploying them.
- The backend is designed for local development first and uses a seeded JSON store while preserving a real API shape.
- Public feed availability depends on the source channels being reachable at runtime.
