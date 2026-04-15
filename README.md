# CrisisShield — AMAN Integrated Smart Security Tool

CrisisShield (internal name: **AMAN**) is a full-stack crisis monitoring and intelligence platform for Lebanon. It ingests real-time data from news, social media, and field reports; runs multilingual NLP analysis; computes regional risk scores; detects anomalies; forecasts escalation; and dispatches actionable alerts to security analysts and decision makers.

---

## Table of Contents

0. [Team Workflow](#0-team-workflow)
1. [Architecture Overview](#1-architecture-overview)
2. [Tech Stack](#2-tech-stack)
3. [Repository Layout](#3-repository-layout)
4. [Section 10: Infrastructure & Deployment](#4-section-10-infrastructure--deployment)
   - [10.1 Docker Compose Services](#41-docker-compose-services)
   - [10.2 Environment Variables](#42-environment-variables)
   - [10.3 Backend Dockerfile](#43-backend-dockerfile)
   - [10.4 Frontend Dockerfile](#44-frontend-dockerfile)
5. [Quick Start — Local Mode (No Docker)](#5-quick-start--local-mode-no-docker)
6. [Full Docker Stack](#6-full-docker-stack)
7. [Database Schema](#7-database-schema)
8. [NLP Pipeline](#8-nlp-pipeline)
9. [Risk Scoring Formula](#9-risk-scoring-formula)
10. [Alert System](#10-alert-system)
11. [API Reference](#11-api-reference)
12. [WebSocket Feed](#12-websocket-feed)
13. [Monitoring — Grafana & Prometheus](#13-monitoring--grafana--prometheus)
14. [Celery Task Schedule](#14-celery-task-schedule)
15. [Running Tests](#15-running-tests)
16. [Troubleshooting](#16-troubleshooting)
17. [Recent Updates](#17-recent-updates)

---

## 0. Team Workflow

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for branch, PR, commit, and conflict rules.

To block direct pushes to `main` locally, run once:

```bash
./scripts/setup-git-workflow.sh https://github.com/mahdi-mortada/snuggle-buddy-build.git
```

Also configure GitHub branch protection for `main`:

- Require pull requests before merging
- Require at least 1 approval
- Restrict direct pushes to `main`
- Require status checks to pass

---

## 1. Architecture Overview

```
External Sources (News RSS, Telegram, Social Media)
        │
        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Data Ingestion Layer                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ News Scraper │  │ Official     │  │ Manual Reports (API)     │  │
│  │ (RSS/httpx)  │  │ Feeds        │  │                          │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                 │                        │                │
│         └────────────────►Kafka: raw-incidents◄────┘                │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  NLP & Feature Engineering (kafka_consumer.py)                       │
│  Language Detection → Arabic Normalization → spaCy NER →            │
│  HuggingFace Sentiment → Zero-Shot Classification →                 │
│  Threat Keyword Scoring → Location Resolution → Feature Engineering  │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
                    ┌────────────────┼──────────────────┐
                    ▼                ▼                  ▼
             PostgreSQL         MongoDB           Elasticsearch
             (structured)     (raw_data)         (full-text search)
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Risk & Prediction Layer (Celery, every 15 min)                      │
│  Risk Scoring (5-component) → Isolation Forest (anomaly) →          │
│  Prophet (24h/48h/7d forecast) → XGBoost (escalation probability)   │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Alert & Recommendation Layer                                        │
│  Threshold Check (Redis) → Rate Limit (1/region/severity/hr) →      │
│  LangChain + Claude AI recommendation → Email/SMS/Webhook dispatch  │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  WebSocket Broadcast → React Frontend                                │
│  Dashboard │ Incident Map │ Analytics │ Alerts │ Official Feeds      │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

1. **Ingestion** — News scrapers and official feed collectors publish raw text to Kafka topic `raw-incidents`
2. **Processing** — `kafka_consumer.py` picks up each message, runs the full NLP pipeline, resolves a Lebanon region, and stores the enriched incident in PostgreSQL + Elasticsearch
3. **Risk scoring** — Celery recalculates per-region risk scores every 15 minutes using a 5-component weighted formula
4. **Anomaly & prediction** — Isolation Forest flags statistical outliers; Prophet forecasts the next 24 h / 48 h / 7 d
5. **Alerting** — `alert_service.py` compares scores against Redis-stored thresholds and dispatches alerts with AI-generated recommendations
6. **Frontend** — Receives live updates over WebSocket; falls back to REST polling

---

## 2. Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18 + TypeScript, Vite, Tailwind CSS, shadcn/ui, Leaflet.js (map), Recharts (charts) |
| **Backend API** | Python 3.11, FastAPI, Pydantic v2, Uvicorn, JWT auth (python-jose + passlib) |
| **Task Queue** | Celery 5 (worker + beat), Redis as broker |
| **Databases** | PostgreSQL 16 + PostGIS (structured + spatial), MongoDB 7 (raw documents), Elasticsearch 8.12 (full-text search) |
| **Caching** | Redis 7 — alert thresholds, risk weights, recommendation cache, rate limiting |
| **Streaming** | Apache Kafka 7.5 + Zookeeper — real-time incident ingestion pipeline |
| **NLP** | spaCy (`en_core_web_lg`, `xx_ent_wiki_sm`), HuggingFace Transformers (sentiment + zero-shot classification), langdetect |
| **ML / Prediction** | scikit-learn (Isolation Forest, GradientBoosting), Facebook Prophet (time-series), XGBoost, MLflow (experiment tracking) |
| **AI Recommendations** | LangChain + Anthropic Claude API (`claude-haiku-4-5-20251001`) |
| **Notifications** | FastAPI-Mail (SMTP email), Twilio (SMS), Webhook POST |
| **Infrastructure** | Docker + Docker Compose, Nginx (reverse proxy) |
| **Monitoring** | Prometheus (metrics), Grafana (dashboards) |

---

## 3. Repository Layout

```
snuggle-buddy-build-main/
├── src/                              # React frontend (Vite + TypeScript)
│   ├── pages/                        # Dashboard, IncidentMap, Analytics, Alerts, OfficialFeeds, Login
│   ├── components/
│   │   ├── layout/                   # DashboardLayout, AppSidebar, Header
│   │   ├── dashboard/                # StatCards, LiveIncidentFeed, RegionalRiskList, RiskGauge, TrendCharts
│   │   ├── alerts/                   # NotificationCenter (bell + dropdown)
│   │   ├── chat/                     # CrisisChat (in-app AI chatbot)
│   │   └── ui/                       # shadcn/ui components
│   ├── hooks/
│   │   ├── useLiveData.ts            # Main data aggregation hook
│   │   └── useBackendWebSocket.ts    # Auto-reconnect WebSocket hook
│   ├── services/
│   │   └── backendApi.ts             # All API calls + JWT auth + snake_case→camelCase
│   ├── data/
│   │   ├── lebanon_geojson.ts        # Lebanon Governorate + District GeoJSON (33 features)
│   │   └── mockData.ts               # Fallback data for demo mode
│   └── types/
│       └── crisis.ts                 # All TypeScript types
│
├── backend/                          # FastAPI backend (Python 3.11)
│   ├── app/
│   │   ├── main.py                   # FastAPI app, lifespan, WebSocket /ws/live-feed
│   │   ├── config.py                 # All settings via pydantic-settings
│   │   ├── api/v1/endpoints/
│   │   │   ├── auth.py               # POST /auth/login, GET /auth/me
│   │   │   ├── incidents.py          # CRUD + /live + /geo + /{id}/review
│   │   │   ├── risk_analysis.py      # /current, /region/{r}, /predictions, /history
│   │   │   ├── alerts.py             # list, stats, /{id}/acknowledge
│   │   │   ├── dashboard.py          # /overview, /trends, /hotspots
│   │   │   └── official_feeds.py
│   │   ├── db/
│   │   │   ├── orm.py                # SQLAlchemy ORM models
│   │   │   ├── postgres.py           # asyncpg engine + session_scope()
│   │   │   ├── mongodb.py            # Motor async client + TTL index (90 d)
│   │   │   ├── elasticsearch.py      # AsyncElasticsearch + Arabic index mapping
│   │   │   └── redis.py              # aioredis + risk weights / thresholds / keywords
│   │   ├── services/
│   │   │   ├── nlp_pipeline.py       # Full multilingual NLP pipeline
│   │   │   ├── feature_engineering.py # z-scores, velocity, behavior patterns
│   │   │   ├── location_resolver.py  # GPS → ST_Within, text → fuzzy alias match
│   │   │   ├── risk_scoring.py       # 5-component formula
│   │   │   ├── anomaly_detection.py  # Isolation Forest
│   │   │   ├── prediction_engine.py  # Facebook Prophet per-region
│   │   │   ├── escalation_model.py   # GradientBoosting + MLflow tracking
│   │   │   ├── alert_service.py      # Redis thresholds + rate limiting + triggers
│   │   │   ├── recommendation_engine.py # LangChain + Claude AI
│   │   │   ├── notification_service.py  # Email / SMS / Webhook
│   │   │   ├── local_store.py        # In-memory fallback store (STORAGE_MODE=local)
│   │   │   ├── seed_data.py          # 505 deterministic seed incidents (RNG seed=42)
│   │   │   └── auth_service.py       # JWT + bcrypt
│   │   ├── workers/
│   │   │   ├── kafka_consumer.py     # raw-incidents → NLP → store → ES → WebSocket
│   │   │   └── celery_tasks.py       # Periodic tasks (risk recalc, news, retrain)
│   │   └── tests/                    # 53 pytest tests across all endpoint groups
│   ├── alembic/versions/
│   │   └── 001_initial_schema.py     # Full PostgreSQL schema with PostGIS
│   ├── data/
│   │   └── lebanon_boundaries.geojson # 33 GeoJSON features (8 governorates + 25 districts)
│   ├── Dockerfile                    # python:3.11-slim, ML system deps
│   ├── requirements.txt              # Full ML stack
│   └── requirements.docker.txt       # Trimmed dependencies for Docker image
│
├── infrastructure/
│   ├── monitoring/
│   │   └── prometheus.yml            # Scrape config: backend, redis, kafka
│   ├── grafana/
│   │   ├── provisioning/             # Auto-datasource + dashboard provisioning
│   │   └── dashboards/
│   │       └── crisisshield.json     # 8-panel Grafana dashboard
│   └── nginx/
│       └── nginx.conf                # Production reverse proxy (API + WS + SPA)
│
├── ml-pipeline/
│   ├── models/                       # Trained artifacts (anomaly_detector.pkl, prophet/*.pkl)
│   ├── notebooks/                    # Exploratory notebooks
│   └── scripts/                      # Training scripts
│
├── docker-compose.yml                # All 13 services
├── Dockerfile.frontend               # node:20-alpine dev + nginx:alpine prod
├── .env.example                      # Frontend environment variable template
└── backend/.env.example              # Backend environment variable template
```

---

## 4. Section 10: Infrastructure & Deployment

### 4.1 Docker Compose Services

`docker-compose.yml` defines all infrastructure and application services. Every service has health checks so dependent services wait for readiness before starting.

| Service | Image | Host Port | Container Port | Purpose |
|---|---|---|---|---|
| `postgres` | `postgis/postgis:16-3.4` | 5433 | 5432 | Primary structured store + PostGIS spatial queries |
| `mongodb` | `mongo:7` | 27018 | 27017 | Raw unstructured documents (TTL 90 d) |
| `elasticsearch` | `elasticsearch:8.12.2` | 9201 | 9200 | Full-text search, Arabic analyzer, single-node |
| `redis` | `redis:7-alpine` | 6380 | 6379 | Cache + Celery broker + alert rate limiting |
| `zookeeper` | `cp-zookeeper:7.5.3` | 2182 | 2181 | Kafka coordination (required by Kafka) |
| `kafka` | `cp-kafka:7.5.3` | 9093, 29093 | 9092, 29092 | Real-time incident streaming pipeline |
| `backend` | `./backend` | 8010 | 8000 | FastAPI app with hot reload |
| `celery-worker` | `./backend` | — | — | Celery worker, concurrency=4 |
| `celery-beat` | `./backend` | — | — | Celery scheduler (PersistentScheduler) |
| `frontend` | `Dockerfile.frontend` | 3002 | 80 | Nginx serving built React app |
| `mlflow` | `python:3.11-slim` | 5001 | 5000 | MLflow experiment tracking UI |
| `prometheus` | `prom/prometheus:latest` | 9090 | 9090 | Metrics collection |
| `grafana` | `grafana/grafana:latest` | 3001 | 3000 | Monitoring dashboards (admin / crisisshield) |

**Kafka topics created automatically:**

| Topic | Partitions | Purpose |
|---|---|---|
| `raw-incidents` | 6 | Raw data from all collectors |
| `processed-incidents` | 6 | Enriched incidents after NLP |
| `risk-updates` | 3 | Recalculated risk scores |
| `alerts` | 3 | Generated alert events |

**Service startup order** (enforced by `depends_on` + `condition: service_healthy`):

```
postgres, mongodb, elasticsearch, redis (start in parallel)
        ↓
    kafka (after zookeeper)
        ↓
backend, celery-worker, celery-beat (after all DBs + kafka)
        ↓
        frontend, grafana (after backend / prometheus)
```

**Port note:** Ports are offset from the standard values (e.g., PostgreSQL on 5433 instead of 5432) to avoid conflicts with locally installed services. Override in `docker-compose.override.yml` if needed.

---

### 4.2 Environment Variables

Copy `.env.example` to the project root (frontend) and `backend/.env.example` to `backend/.env`. All variables have comments explaining their purpose and safe development defaults.

#### Frontend (`/.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_BACKEND_URL` | `http://127.0.0.1:8000` | Backend REST API base URL |
| `VITE_BACKEND_WS_URL` | `ws://127.0.0.1:8000/ws/live-feed` | WebSocket endpoint for live updates |
| `VITE_BACKEND_DEV_EMAIL` | `admin@crisisshield.dev` | Auto-filled on the login page in dev mode |
| `VITE_BACKEND_DEV_PASSWORD` | `admin12345` | Auto-filled on the login page in dev mode |

#### Backend (`/backend/.env`)

**Application**

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Controls log verbosity and SQLAlchemy echo |
| `STORAGE_MODE` | `postgres` | `local` = in-memory JSON (zero infrastructure); `postgres` = full DB stack |
| `BACKEND_HOST` | `127.0.0.1` | Uvicorn bind host |
| `BACKEND_PORT` | `8000` | Uvicorn bind port |

**Databases**

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/crisisshield` | asyncpg DSN for PostgreSQL + PostGIS |
| `MONGODB_URL` | `mongodb://localhost:27017/crisisshield` | Motor async MongoDB connection string |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch cluster URL |
| `REDIS_URL` | `redis://localhost:6379/0` | aioredis connection (also used as Celery broker) |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:29092` | Kafka broker. Use `kafka:9092` inside Docker Compose |

**Authentication**

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | `crisisshield-dev-secret-CHANGE-IN-PRODUCTION` | HS256 signing key. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime in minutes |

**Admin Seed Account**

| Variable | Default | Description |
|---|---|---|
| `ADMIN_EMAIL` | `admin@crisisshield.dev` | Email for the auto-seeded admin user |
| `ADMIN_PASSWORD` | `admin12345` | Password for the auto-seeded admin user |
| `ADMIN_FULL_NAME` | `CrisisShield Admin` | Display name |
| `ADMIN_ORGANIZATION` | `CrisisShield` | Organization field |

**AI / LLM**

| Variable | Default | Description |
|---|---|---|
| `CLAUDE_API_KEY` | *(empty)* | Anthropic API key for the LangChain recommendation engine. When absent, the system falls back to templated recommendations. Get from [console.anthropic.com](https://console.anthropic.com/) |

**Email Notifications (CRITICAL+ alerts)**

| Variable | Default | Description |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port (587 = STARTTLS) |
| `SMTP_USERNAME` | *(empty)* | SMTP login username |
| `SMTP_PASSWORD` | *(empty)* | SMTP login password or app password |
| `SMTP_FROM_EMAIL` | `alerts@crisisshield.dev` | Sender email address |
| `SMTP_FROM_NAME` | `CrisisShield Alerts` | Sender display name |
| `ALERT_EMAIL_RECIPIENTS` | `admin@crisisshield.dev` | Comma-separated list of recipient emails |

**SMS Notifications (EMERGENCY alerts only)**

| Variable | Default | Description |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | *(empty)* | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | *(empty)* | Twilio auth token |
| `TWILIO_FROM_PHONE` | `+1234567890` | Twilio outbound phone number |
| `ALERT_SMS_RECIPIENTS` | *(empty)* | Comma-separated E.164 phone numbers |

**Webhook Notifications**

| Variable | Default | Description |
|---|---|---|
| `ALERT_WEBHOOK_URLS` | *(empty)* | Comma-separated URLs. Each receives a POST with the full alert JSON when an alert is created |

**ML / MLflow**

| Variable | Default | Description |
|---|---|---|
| `MLFLOW_TRACKING_URI` | `http://localhost:5001` | MLflow tracking server. Use `http://mlflow:5000` inside Docker Compose |
| `MLFLOW_RISK_EXPERIMENT` | `crisisshield_risk_scoring` | MLflow experiment name for risk model runs |
| `MLFLOW_ESCALATION_EXPERIMENT` | `crisisshield_escalation` | MLflow experiment name for escalation model runs |

**Alert Thresholds** (stored in Redis on startup; tunable at runtime without restart)

| Variable | Default | Description |
|---|---|---|
| `ALERT_THRESHOLD_INFO` | `40` | Risk score that triggers an INFO alert |
| `ALERT_THRESHOLD_WARNING` | `60` | Risk score that triggers a WARNING alert |
| `ALERT_THRESHOLD_CRITICAL` | `80` | Risk score that triggers a CRITICAL alert |
| `ALERT_THRESHOLD_EMERGENCY` | `90` | Risk score that triggers an EMERGENCY alert |
| `ALERT_VELOCITY_THRESHOLD` | `20` | Points-per-hour rise that triggers a velocity alert |
| `ALERT_ESCALATION_PROBABILITY_THRESHOLD` | `0.8` | XGBoost probability above which an escalation alert fires |
| `ALERT_RATE_LIMIT_SECONDS` | `3600` | Minimum seconds between the same severity alert for the same region |

**Risk Scoring Weights** (must sum to 1.0; stored in Redis; tunable at runtime)

| Variable | Default | Description |
|---|---|---|
| `RISK_WEIGHT_SENTIMENT` | `0.25` | Weight of the sentiment component |
| `RISK_WEIGHT_VOLUME` | `0.25` | Weight of the incident volume component |
| `RISK_WEIGHT_KEYWORD` | `0.20` | Weight of the threat keyword component |
| `RISK_WEIGHT_BEHAVIOR` | `0.15` | Weight of the behavior anomaly component |
| `RISK_WEIGHT_GEOSPATIAL` | `0.15` | Weight of the geospatial density component |
| `RISK_RECALC_INTERVAL_MINUTES` | `15` | How often Celery recalculates all region scores |

**NLP Pipeline**

| Variable | Default | Description |
|---|---|---|
| `HF_HOME` | `/tmp/huggingface_cache` | HuggingFace model cache directory. Point to a persistent volume in production |
| `TOKENIZERS_PARALLELISM` | `false` | Suppresses HuggingFace tokenizer parallel warning in async context |

**Data Ingestion**

| Variable | Default | Description |
|---|---|---|
| `LIVE_NEWS_ENABLED` | `true` | Enable live news fetching |
| `LIVE_NEWS_WINDOW_HOURS` | `24` | How many hours back to pull news |
| `LIVE_NEWS_LIMIT` | `25` | Maximum number of live news stories to return |
| `OFFICIAL_FEEDS_ENABLED` | `true` | Enable official Telegram/social channel feeds |
| `OFFICIAL_FEED_LIMIT` | `24` | Maximum number of feed posts to return |
| `OFFICIAL_FEED_EXTRA_CHANNELS_JSON` | *(empty)* | JSON array of extra channel objects (see Official Feeds section) |

**CORS**

| Variable | Default | Description |
|---|---|---|
| `CORS_ORIGINS` | `["http://127.0.0.1:8080","http://localhost:8080","http://127.0.0.1:3000","http://localhost:3000"]` | JSON array of allowed frontend origins |

**Local Dev Fallback**

| Variable | Default | Description |
|---|---|---|
| `LOCAL_DATA_FILE` | `backend/data/local_state.json` | Path to the JSON state file used when `STORAGE_MODE=local` |

---

### 4.3 Backend Dockerfile

**File:** `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies:
#   build-essential  — compiles Python extensions (asyncpg, psycopg2, etc.)
#   libpq-dev        — PostgreSQL client library (required by asyncpg)
#   curl             — used by Docker HEALTHCHECK
#   git              — some pip packages install from git
#   libgomp1         — OpenMP (required by XGBoost and LightGBM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (maximises Docker layer cache reuse)
COPY requirements.docker.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.docker.txt

# Copy application source after dependencies (so code changes don't bust the pip cache)
COPY . .

# Development command — hot reload is ON.
# docker-compose overrides CMD for celery-worker and celery-beat services.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**`requirements.docker.txt` vs `requirements.txt`:**

| File | Purpose |
|---|---|
| `requirements.txt` | Full ML stack including spaCy, HuggingFace Transformers, Prophet, XGBoost. Used for local development and production deployments that need the complete NLP/ML pipeline |
| `requirements.docker.txt` | Trimmed set that excludes heavy ML packages. Services that do not need the NLP pipeline (e.g. celery-beat) use this to keep image size manageable. The application falls back gracefully if models are unavailable |

**spaCy model downloads** (run manually or add to Dockerfile for production):

```bash
python -m spacy download en_core_web_lg     # English NER
python -m spacy download xx_ent_wiki_sm     # Multilingual NER (covers Arabic)
```

**Celery overrides in docker-compose:**

```yaml
celery-worker:
  command: celery -A app.workers.celery_tasks worker --loglevel=info --concurrency=4

celery-beat:
  command: celery -A app.workers.celery_tasks beat --loglevel=info --scheduler celery.beat:PersistentScheduler
```

---

### 4.4 Frontend Dockerfile

**File:** `Dockerfile.frontend`

The frontend uses a multi-stage build with three stages:

#### Stage 1 — Development (`dev`)

```dockerfile
FROM node:20-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci                             # clean install, respects package-lock.json
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
```

Used for local hot-reload development inside Docker. Vite serves files with HMR on port 3000.

#### Stage 2 — Build (`build`)

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build                      # Vite production build → /app/dist
```

Compiles TypeScript, bundles all assets, and tree-shakes to the smallest possible output.

#### Stage 3 — Production (`prod`)

```dockerfile
FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY infrastructure/nginx/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Serves the static build through Nginx. All `/api/` and `/ws/` requests are reverse-proxied to the backend. All other routes serve `index.html` for client-side routing.

**Nginx proxy rules (infrastructure/nginx/nginx.conf):**

| Location | Proxied To | Notes |
|---|---|---|
| `/api/` | `backend:8000` | Standard HTTP proxy, 300 s read timeout |
| `/ws/` | `backend:8000` | WebSocket upgrade headers set |
| `/health` | `backend:8000` | Direct proxy for health checks |
| `/` (all else) | `dist/index.html` | SPA fallback for React Router |

**Production build commands:**

```bash
# Build for production (outputs to dist/)
npm run build

# Preview production build locally
npm run preview
```

---

## 5. Quick Start — Local Mode (No Docker)

This mode runs entirely without databases. The backend uses a JSON file as its data store and seeds 505 realistic incidents automatically on first run.

### Prerequisites

- Python 3.11+ or Python 3.12+
- Node.js 18+ (or use the portable runtime in `.tools/`)
- pip

### Step 1 — Install backend dependencies

```bash
cd backend
pip install fastapi uvicorn pydantic pydantic-settings python-jose[cryptography] "passlib[bcrypt]<1.8" "bcrypt<4" httpx python-multipart email-validator
```

### Step 2 — Configure backend

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set:
#   STORAGE_MODE=local
# All other variables are optional in local mode
```

### Step 3 — Start the backend

```bash
cd backend
STORAGE_MODE=local uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Startup output confirms local mode and seed counts:

```
PostgreSQL connection failed (non-fatal in local mode): ...
MongoDB connection failed (non-fatal in local mode): ...
...
Application startup complete.
Uvicorn running on http://127.0.0.1:8000
```

### Step 4 — Install and start the frontend

```bash
npm install
npm run dev
```

Or use the PowerShell convenience script from the project root:

```powershell
.\scripts\run-local.ps1
```

### Step 5 — Open the app

| Service | URL |
|---|---|
| Frontend | http://127.0.0.1:8080 |
| Backend API | http://127.0.0.1:8000 |
| API health | http://127.0.0.1:8000/health |
| API docs (Swagger) | http://127.0.0.1:8000/docs |

### Default credentials

| Field | Value |
|---|---|
| Email | `admin@crisisshield.dev` |
| Password | `admin12345` |

---

## 6. Full Docker Stack

Runs all 13 services including databases, Kafka, MLflow, Prometheus, and Grafana.

### Prerequisites

- Docker Desktop 4.x+ (or Docker Engine + Compose v2)
- At least 8 GB RAM allocated to Docker (Elasticsearch requires ~2 GB)

### Step 1 — Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env:
#   STORAGE_MODE=postgres
#   Add CLAUDE_API_KEY if you want AI recommendations
#   Add SMTP / Twilio credentials if you want notifications
```

### Step 2 — Build and start all services

```bash
docker-compose up --build
```

First run takes 5–10 minutes to pull images and build the backend (ML dependencies are large). Subsequent starts are fast because Docker caches layers.

### Step 3 — Run database migrations

After the `postgres` container is healthy, run Alembic to create all tables:

```bash
docker-compose exec backend alembic upgrade head
```

### Step 4 — Seed the database (optional)

The backend auto-seeds 505 incidents on startup when the incidents table is empty. To re-seed manually:

```bash
docker-compose exec backend python -c "
from app.services.seed_data import build_seed_incidents
print(f'Seed data: {len(build_seed_incidents())} incidents generated')
"
```

### Service URLs

| Service | URL | Credentials |
|---|---|---|
| Frontend | http://localhost:3002 | admin@crisisshield.dev / admin12345 |
| Backend API | http://localhost:8010 | JWT via `/api/v1/auth/login` |
| API docs | http://localhost:8010/docs | — |
| Grafana | http://localhost:3001 | admin / crisisshield |
| Prometheus | http://localhost:9090 | — |
| MLflow | http://localhost:5001 | — |
| Kafka | localhost:29093 (host access) | — |

### Stop all services

```bash
docker-compose down          # stop and remove containers
docker-compose down -v       # also remove all volumes (wipes all data)
```

### Rebuild a single service

```bash
docker-compose up --build backend
```

---

## 7. Database Schema

### PostgreSQL + PostGIS

All tables are created by Alembic migration `backend/alembic/versions/001_initial_schema.py`.

**`regions`** — Lebanon Governorate and District boundaries

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| name | TEXT UNIQUE | Canonical English name (e.g. "Beirut") |
| name_ar | TEXT | Arabic name (e.g. "بيروت") |
| region_type | TEXT | `governorate` or `district` |
| parent_id | TEXT | FK → parent governorate |
| geom | geometry(POLYGON,4326) | PostGIS polygon for ST_Within queries |
| centroid | geography(POINT,4326) | |
| centroid_lat / lng | FLOAT | Precomputed from centroid |

The 8 canonical governorate names used throughout the system:

| Governorate | Arabic | Centroid (lat, lng) |
|---|---|---|
| Beirut | بيروت | 33.8938, 35.5018 |
| Mount Lebanon | جبل لبنان | 33.8100, 35.6500 |
| North Lebanon | الشمال | 34.4367, 35.8497 |
| South Lebanon | الجنوب | 33.2721, 35.2033 |
| Nabatieh | النبطية | 33.3772, 35.4836 |
| Bekaa | البقاع | 33.8463, 35.9019 |
| Baalbek-Hermel | بعلبك الهرمل | 34.0047, 36.2110 |
| Akkar | عكار | 34.5331, 36.0781 |

**`incidents`** — Core incident records

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| source | TEXT | `news`, `manual`, `sensor` |
| title / description / raw_text | TEXT | |
| category | TEXT | Enum: see taxonomy below |
| severity | TEXT | `low`, `medium`, `high`, `critical` |
| location | geography(POINT,4326) | GPS coordinates |
| region | TEXT | Assigned Lebanon region name |
| sentiment_score | FLOAT | −1.0 to +1.0 |
| risk_score | FLOAT | 0–100 |
| entities | TEXT[] | spaCy-extracted named entities |
| keywords | TEXT[] | Matched threat keywords |
| status | TEXT | `new`, `processing`, `analyzed`, `escalated`, `resolved`, `false_alarm` |
| verification_status | TEXT | `unverified`, `reviewed`, `confirmed`, `rejected` |
| confidence_score | FLOAT | NLP classification confidence 0–1 |
| reviewed_by | UUID FK→users | Analyst who reviewed this incident |
| reviewed_at | TIMESTAMPTZ | |
| analyst_notes | TEXT | Free-text analyst comments |
| created_at / updated_at | TIMESTAMPTZ | |

**Incident category taxonomy (mandatory enum):**

`violence` · `protest` · `armed_conflict` · `terrorism` · `natural_disaster` · `infrastructure` · `health` · `cyber` · `other`

**`risk_scores`** — Per-region risk calculations

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| region | TEXT | Lebanon region name |
| overall_score | FLOAT | 0–100 composite score |
| sentiment_component | FLOAT | Weighted sentiment input |
| volume_component | FLOAT | Weighted volume z-score input |
| keyword_component | FLOAT | Weighted keyword score input |
| behavior_component | FLOAT | Weighted behavior pattern input |
| geospatial_component | FLOAT | Weighted density input |
| confidence | FLOAT | 0–1 based on incident count |
| is_anomalous | BOOL | Isolation Forest flag |
| anomaly_score | FLOAT | Raw anomaly score |
| escalation_probability | FLOAT | XGBoost escalation probability 0–1 |
| incident_count_24h | INT | |
| calculated_at | TIMESTAMPTZ | |

**`alerts`** — Generated alerts

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| alert_type | TEXT | `threshold_breach`, `escalation`, `anomaly`, `prediction`, `velocity` |
| severity | TEXT | `info`, `warning`, `critical`, `emergency` |
| title / message / recommendation | TEXT | |
| region | TEXT | |
| is_acknowledged | BOOL | |
| acknowledged_by | UUID FK→users | |
| acknowledged_at | TIMESTAMPTZ | |
| notification_channels | TEXT[] | `email`, `sms`, `webhook`, `dashboard` |
| created_at | TIMESTAMPTZ | |

### MongoDB

**Collection: `raw_data`** — Original unprocessed documents from all sources

- TTL index on `collected_at`: documents auto-expire after **90 days**
- Index on `{ source: 1, collected_at: -1 }` for source-time queries
- Index on `{ processed: 1 }` for pipeline pick-up

### Elasticsearch

**Index: `incidents`** with Arabic analyzer:

- Custom analyzer chain: `standard tokenizer → lowercase → arabic_normalization → arabic_stop → arabic_stemmer`
- Text fields (`title`, `description`) use `arabic_english_analyzer` for bilingual search
- Keyword fields (`category`, `severity`, `region`) for exact filtering
- `created_at` as `date` for time range queries

### Redis Key Schema

| Key Pattern | Type | Purpose |
|---|---|---|
| `config:risk_weights` | Hash | `{sentiment, volume, keyword, behavior, geospatial}` — float weights, sum to 1.0 |
| `config:alert_thresholds` | Hash | `{info, warning, critical, emergency}` — score thresholds |
| `config:threat_keywords` | Hash | keyword → float weight (40 Arabic + English terms) |
| `alert_rate:{region}:{severity}` | TTL key | Rate-limiting: expires after `ALERT_RATE_LIMIT_SECONDS` |
| `cache:recommendation:{region}:{severity}:{score}` | String | Cached AI recommendation text, TTL 3600 s |
| `cache:dashboard` | String | Cached overview JSON, TTL 60 s |
| `cache:risk:{region}` | String | Cached risk score, TTL 300 s |

---

## 8. NLP Pipeline

**File:** `backend/app/services/nlp_pipeline.py`

All models are **lazy-loaded once at application startup** via `nlp_pipeline.initialize()` called from `main.py` lifespan. Per-request loading is not used — model objects are reused.

### Pipeline Steps

| Step | Library | Description | Fallback |
|---|---|---|---|
| 1. Language detection | `langdetect` | Identifies `ar` (Arabic), `en` (English), or `other` | Default to `en` |
| 2. Arabic normalization | Custom | Strip tashkeel diacritics, normalize alef variants (أإآ→ا), ya (ي→ى), ta marbuta (ة→ه) | Skip if English |
| 3. Named Entity Recognition | `spaCy` | `en_core_web_lg` for English; `xx_ent_wiki_sm` for Arabic/multilingual. Extracts PERSON, ORG, GPE, EVENT, DATE | Return empty entities |
| 4. Sentiment analysis | HuggingFace | `cardiffnlp/twitter-roberta-base-sentiment-latest` (EN); `aubmindlab/bert-base-arabertv2` (AR). Returns score −1.0 to +1.0 | Keyword-based fallback score |
| 5. Topic classification | HuggingFace | `facebook/bart-large-mnli` zero-shot classification against the 9 incident categories | Keyword heuristic fallback |
| 6. Threat keyword scoring | Redis | Matches text against the `config:threat_keywords` hash. Returns sorted keyword list and weighted aggregate score 0–100 | Score = 0 |

### Location Resolution

**File:** `backend/app/services/location_resolver.py`

Resolves incident text or GPS coordinates to a canonical Lebanon region name:

1. **GPS path** — if `latitude` and `longitude` are present, use PostGIS `ST_Within(point, geom)` against the `regions` table
2. **NLP path** — extract GPE entities from step 3, fuzzy-match against ~80 Lebanon place aliases (Arabic and English variants of all regions and districts)
3. **Fallback** — assign `region = "unknown"`, `confidence = 0`

---

## 9. Risk Scoring Formula

**File:** `backend/app/services/risk_scoring.py`

Risk is computed **per region** every 15 minutes by Celery.

```
overall_score = (
    w_sentiment  * sentiment_component   +   # how negative is discourse
    w_volume     * volume_component      +   # activity vs. 30-day baseline
    w_keyword    * keyword_component     +   # threat keyword presence
    w_behavior   * behavior_component   +   # abnormal posting patterns
    w_geospatial * geospatial_component      # incident density (incidents/km²)
) × confidence
```

**Default weights** (Redis-configurable at runtime):

| Component | Weight | Computation |
|---|---|---|
| `sentiment` | 0.25 | Mean sentiment of incidents in last 30 min, inverted and scaled to 0–100 |
| `volume` | 0.25 | Z-score of incident count vs. 30-day rolling baseline, clamped to 0–100 |
| `keyword` | 0.20 | Max threat keyword score among incidents in last 6 h |
| `behavior` | 0.15 | Burst detection (≥3 incidents in 30 min) + escalation ratio + spam penalty |
| `geospatial` | 0.15 | Incident count / region area (km²), normalized |

**Confidence multiplier** — scales down scores from regions with few incidents:

| Incident count | Confidence |
|---|---|
| 0 | 0.50 |
| 5 | 0.75 |
| 10 | 0.90 |
| 20+ | 0.95 |

**Anomaly detection** — Isolation Forest (`n_estimators=100`, `contamination=0.1`) trained on the feature vector `[sentiment_mean, volume_zscore, keyword_score, behavior_score, geo_density]`. Retrained weekly via Celery.

**Escalation prediction** — `GradientBoostingClassifier` with 8 input features (current score, risk velocity, sentiment trend, volume trend, day of week, hour, historical escalation rate, anomaly score). Tracked in MLflow.

---

## 10. Alert System

**File:** `backend/app/services/alert_service.py`

### Alert Triggers

| Trigger | Condition |
|---|---|
| Threshold breach | `overall_score` exceeds INFO / WARNING / CRITICAL / EMERGENCY threshold |
| Velocity | Score rises more than `ALERT_VELOCITY_THRESHOLD` points in 1 hour |
| Anomaly | Isolation Forest flags `is_anomalous = True` |
| Escalation | XGBoost `escalation_probability` exceeds `ALERT_ESCALATION_PROBABILITY_THRESHOLD` |

### Rate Limiting

A maximum of **1 alert per region per severity level per hour** is generated. Redis TTL keys enforce this: `alert_rate:{region}:{severity}` expires after `ALERT_RATE_LIMIT_SECONDS` (default 3600).

### AI Recommendations

For `CRITICAL` and `EMERGENCY` alerts, LangChain constructs a prompt with:
- Alert details and risk component breakdown
- Last 10 incident summaries for the region
- Historical context

The Claude API generates a 2–3 sentence situation summary and 3–5 actionable recommendations. The response is cached in Redis for 1 hour per `(region, severity, rounded_score)` key to avoid redundant API calls.

### Notification Channels

| Channel | Triggered by | Implementation |
|---|---|---|
| Dashboard WebSocket | All alerts | Broadcast to all connected clients immediately |
| Email | CRITICAL and EMERGENCY | FastAPI-Mail via SMTP to `ALERT_EMAIL_RECIPIENTS` |
| SMS | EMERGENCY only | Twilio API to `ALERT_SMS_RECIPIENTS` |
| Webhook | All alerts | HTTP POST with full alert JSON to `ALERT_WEBHOOK_URLS` |

---

## 11. API Reference

All endpoints are under `/api/v1/`. All endpoints except `POST /auth/login` require a JWT Bearer token:

```
Authorization: Bearer <access_token>
```

### Authentication

#### `POST /api/v1/auth/login`

Authenticate and receive a JWT token.

**Request body:**
```json
{ "email": "admin@crisisshield.dev", "password": "admin12345" }
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "user": { "id": "...", "email": "...", "role": "admin", "full_name": "...", "organization": "..." }
  }
}
```

#### `GET /api/v1/auth/me`

Returns the profile of the currently authenticated user.

#### `POST /api/v1/auth/register` *(admin only)*

Register a new user. Body: `{ email, password, full_name, role, organization }`.

---

### Incidents

#### `GET /api/v1/incidents`

List incidents with filtering and pagination.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `page` | int | Page number (default 1) |
| `per_page` | int | Results per page (default 20, max 100) |
| `region` | string | Filter by Lebanon region name |
| `severity` | string | `low`, `medium`, `high`, `critical` |
| `category` | string | Any incident category |
| `status` | string | Incident processing status |
| `search` | string | Full-text search via Elasticsearch |
| `start_date` | ISO datetime | Filter incidents after this time |
| `end_date` | ISO datetime | Filter incidents before this time |

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [ { "id": "...", "title": "...", "category": "violence", "severity": "high", "region": "Beirut", "risk_score": 72.4, "created_at": "..." } ],
    "total": 505,
    "page": 1,
    "per_page": 20,
    "pages": 26
  }
}
```

#### `GET /api/v1/incidents/{id}`

Full incident detail including entities, keywords, sentiment, analyst notes.

#### `POST /api/v1/incidents`

Manually create an incident. Body: `{ title, description, category, severity, region, source? }`.

#### `PATCH /api/v1/incidents/{id}/review`

Analyst review workflow. Body: `{ verification_status, analyst_notes, severity?, category? }`.

#### `GET /api/v1/incidents/live`

Returns the most recent N incidents sorted by `created_at DESC`. Query param: `limit` (default 20).

#### `GET /api/v1/incidents/geo`

GeoJSON FeatureCollection of all incidents with GPS coordinates. Used by the Incident Map polygon layer.

---

### Risk Analysis

#### `GET /api/v1/risk/current`

Current risk scores for all 8 Lebanon regions.

**Response:**
```json
{
  "success": true,
  "data": [
    { "region": "Beirut", "overall_score": 72.4, "sentiment_component": 68.1, "volume_component": 75.2, "keyword_component": 71.0, "behavior_component": 55.3, "geospatial_component": 80.0, "confidence": 0.95, "is_anomalous": false, "escalation_probability": 0.23 }
  ]
}
```

#### `GET /api/v1/risk/region/{region}`

Detailed risk breakdown for a single region including `is_anomalous`, `anomaly_score`, `escalation_probability`, and `incident_count_24h`.

#### `GET /api/v1/risk/predictions`

Prophet forecasts for the next 24 h, 48 h, and 7 days. Optional `?region=Beirut` filter.

**Response:**
```json
{
  "success": true,
  "data": [
    { "region": "Beirut", "horizon": "24h", "predicted_score": 75.2, "lower_bound": 68.1, "upper_bound": 82.3, "generated_at": "..." }
  ]
}
```

#### `GET /api/v1/risk/history`

Historical risk scores. Query params: `region` (required), `hours` (default 48).

#### `POST /api/v1/risk/recalculate`

Trigger an immediate out-of-cycle risk recalculation for all regions. Returns task status.

---

### Alerts

#### `GET /api/v1/alerts`

List alerts. Query params: `region`, `severity`, `acknowledged` (bool).

#### `GET /api/v1/alerts/stats`

Aggregated statistics:
```json
{
  "success": true,
  "data": { "total": 42, "acknowledged": 18, "by_severity": { "info": 12, "warning": 15, "critical": 10, "emergency": 5 }, "average_response_minutes": 14.3 }
}
```

#### `PATCH /api/v1/alerts/{id}/acknowledge`

Mark an alert as acknowledged. Records `acknowledged_by` and `acknowledged_at`.

---

### Dashboard

#### `GET /api/v1/dashboard/overview`

```json
{
  "success": true,
  "data": { "total_incidents_24h": 47, "active_alerts": 3, "avg_risk_score": 57.25, "top_risk_region": "Beirut" }
}
```

#### `GET /api/v1/dashboard/trends`

24-hour time-series data for chart rendering. Returns array of `{ time, incidents, risk_score, sentiment }` objects at hourly resolution.

#### `GET /api/v1/dashboard/hotspots`

GeoJSON FeatureCollection of the top incident clusters computed via PostGIS `ST_ClusterDBSCAN`.

---

### Official Feeds

#### `GET /api/v1/official-feeds`

Returns the latest posts from official Lebanese news channels (LBCI, MTV Lebanon, Al Jadeed, Al Manar, and any extras in `OFFICIAL_FEED_EXTRA_CHANNELS_JSON`).

---

### Health Check

#### `GET /health`

Returns connection status of all services and seed data counts. No auth required.

```json
{
  "success": true,
  "data": {
    "storage_mode": "local",
    "postgres": false,
    "mongodb": false,
    "elasticsearch": false,
    "redis": false,
    "seeded_users": 1,
    "seeded_incidents": 505
  }
}
```

#### `GET /metrics`

Prometheus metrics endpoint (request counts, latencies, WebSocket connections, Kafka lag, NLP processing times).

---

## 12. WebSocket Feed

**Endpoint:** `ws://localhost:8000/ws/live-feed`

The frontend hook `useBackendWebSocket` connects on mount, auto-reconnects with exponential backoff on disconnect, and triggers `useLiveData` re-fetches on each message.

### Message Format

All messages are JSON with a `type` field:

```json
{ "type": "incident", "data": { ...incident fields... }, "timestamp": "2026-04-03T12:00:00Z" }
{ "type": "alert",    "data": { ...alert fields... },    "timestamp": "..." }
{ "type": "risk_update", "data": { "region": "Beirut", "overall_score": 74.1 }, "timestamp": "..." }
{ "type": "heartbeat", "timestamp": "..." }
```

### Message Types

| Type | Trigger | Frontend action |
|---|---|---|
| `snapshot` | On connect | Populate initial incident and alert lists |
| `incident` | New incident processed | Prepend to live feed, update stats |
| `alert` | Alert generated | Show notification bell, update alert list |
| `risk_update` | Risk recalculated | Update regional risk gauges and map colors |
| `heartbeat` | Every 30 seconds | Confirm connection is alive |

---

## 13. Monitoring — Grafana & Prometheus

### Prometheus

**Config:** `infrastructure/monitoring/prometheus.yml`

Scrapes metrics from:
- `backend:8000/metrics` — FastAPI app metrics (via `prometheus-fastapi-instrumentator`)
- `redis:6379` — Redis memory, hit rate, connected clients
- `kafka:9092` — Kafka consumer lag, topic throughput

### Grafana

**URL:** http://localhost:3001 (admin / crisisshield)

**Dashboard:** `infrastructure/grafana/dashboards/crisisshield.json` — auto-provisioned on startup with 8 panels:

| Panel | Metric |
|---|---|
| API Request Rate | Requests/second by endpoint |
| p95 API Latency | 95th percentile response time |
| Error Rate | HTTP 4xx/5xx rates |
| WebSocket Connections | Active WebSocket clients |
| Kafka Consumer Lag | `processed-incidents` topic lag |
| NLP Processing Time | Time per pipeline step |
| Risk Scores by Region | Current risk score per Lebanon region |
| Alert Rates | Alerts generated per hour by severity |

**Data source** is auto-provisioned from `infrastructure/grafana/provisioning/datasources/prometheus.yml` and requires no manual configuration.

---

## 14. Celery Task Schedule

**File:** `backend/app/workers/celery_tasks.py`

Celery Beat runs the following periodic tasks:

| Task | Schedule | Description |
|---|---|---|
| `recalculate_all_risk_scores` | Every 15 minutes | Recomputes risk scores for all 8 regions; triggers alert generation if thresholds crossed |
| `ingest_live_news` | Every 2 minutes | Fetches latest Lebanon-related news stories and publishes to Kafka |
| `retrain_prophet_models` | Daily at 00:00 | Retrains Prophet forecasting models per region on the latest 30 days of risk history |
| `retrain_anomaly_detector` | Weekly, Sunday 02:00 | Retrains Isolation Forest on the latest 30 days of feature vectors |

**Redis keys used by Celery:**
- Broker: `redis://redis:6379/0`
- Result backend: `redis://redis:6379/0`

---

## 15. Running Tests

53 pytest tests cover all API endpoint groups, NLP pipeline, and risk scoring logic.

### Setup

```bash
cd backend
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
```

### Run all tests

```bash
cd backend
pytest
```

### Run specific test files

```bash
pytest app/tests/test_auth.py           # Authentication (login, token, register)
pytest app/tests/test_incidents.py      # Incidents CRUD, filtering, geo endpoint
pytest app/tests/test_risk.py           # Risk scores, region detail, predictions, history
pytest app/tests/test_alerts.py         # Alert list, stats, acknowledge
pytest app/tests/test_dashboard.py      # Overview, trends, hotspots
pytest app/tests/test_nlp.py            # Seed data integrity, NLP scoring, async pipeline
pytest app/tests/test_health.py         # /health endpoint
pytest app/tests/test_official_feeds.py # Official feeds endpoint
```

### Run with verbose output

```bash
pytest -v --tb=short
```

**Test mode:** `STORAGE_MODE=local` is set automatically in the test fixtures. All tests use the in-memory store and do not require any running database services.

**Async support:** `pyproject.toml` sets `asyncio_mode = "auto"` so all `async def test_*` functions are handled automatically by pytest-asyncio.

---

## 16. Troubleshooting

### `ModuleNotFoundError: No module named 'sqlalchemy'`

The backend requires SQLAlchemy only when `STORAGE_MODE=postgres`. In local mode it is not needed. If you see this error in local mode, sqlalchemy's import was not properly guarded. Check that `backend/app/db/postgres.py` imports SQLAlchemy inside methods, not at the module top level.

For local development, install the minimal set of dependencies listed in Step 1 of [Quick Start — Local Mode](#5-quick-start--local-mode-no-docker).

### Login returns `500 Internal Server Error`

Most commonly caused by `bcrypt` version incompatibility with `passlib`. `bcrypt` 4.x+ changed its API in a way that breaks `passlib 1.7.x`.

**Fix:**
```bash
pip install "bcrypt<4.0.0"
```

### `Port 8000 is already in use`

```bash
# Find and kill the process using port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### `Port 8080 is already in use`

The frontend is already running. Open http://127.0.0.1:8080/ directly, or stop the existing process:

```bash
netstat -ano | findstr :8080
taskkill /PID <PID> /F
.\scripts\run-local.ps1
```

### `.\scripts\run-local.ps1` is not recognized

You are in the outer `snuggle-buddy-build-main` folder instead of the inner project root.

```powershell
cd C:\Users\MahdiMortada\Downloads\snuggle-buddy-build-main\snuggle-buddy-build-main
.\scripts\run-local.ps1
```

Verify you are in the correct folder:
```powershell
dir package.json
dir scripts
un-local.ps1
```

### Browser shows stale version or wrong port

Close any tabs open on old ports (8082, 3000, etc.). Open a fresh tab on the correct URL and hard-refresh with `Ctrl+F5`.

### Elasticsearch takes too long to start

Elasticsearch requires ~2 GB RAM. In Docker Desktop, ensure at least 4 GB RAM is allocated. Increase the `healthcheck.retries` for the `elasticsearch` service in `docker-compose.yml` if it fails during startup on slower machines.

### Official feeds return empty results

The official feeds system pulls from public Telegram channels. Channel availability depends on network reachability. If a channel is temporarily unavailable, the system returns an empty list for that source without failing. Add additional channels via `OFFICIAL_FEED_EXTRA_CHANNELS_JSON` in `backend/.env`.

### AI recommendations not appearing on alerts

`CLAUDE_API_KEY` is not set in `backend/.env`. When the key is absent, the recommendation engine falls back to pre-written template recommendations. Add your Anthropic API key to enable live LangChain + Claude recommendations.

### Celery workers not processing tasks

1. Confirm Redis is running and reachable: `redis-cli -p 6380 ping` (Docker) or `redis-cli ping` (local)
2. Confirm the `REDIS_URL` in `backend/.env` matches the running Redis instance
3. Check worker logs: `docker-compose logs celery-worker`

### Chatbot gives outdated information

The AI chatbot reads live incidents from:
1. **Frontend context** (incidents visible on the dashboard when you open the chat)
2. **Live news cache** (`live_news_service._cache`) — fetched at startup and refreshed every 5 minutes
3. **Local store** — fallback seed data (only in `STORAGE_MODE=local`)

If the chatbot seems out of date, wait ~5 minutes for the background refresh or restart the backend container to trigger an immediate news fetch.

### PostgreSQL tables are empty after migration

The app stores incidents in memory (live news cache), not in the PostgreSQL `incidents` table by default. To populate PostgreSQL manually, run the one-time seed script inside the container:

```bash
docker-compose exec backend python /app/seed_pg.py
```

This fetches the latest news and writes all incidents to PostgreSQL. The script can be re-run at any time — it uses `ON CONFLICT DO UPDATE` so it is safe to run multiple times.

### DBeaver — how to connect

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5433` (Docker maps 5433 → 5432 internally) |
| Database | `crisisshield` |
| Username | `postgres` |
| Password | `postgres` |

After connecting, expand `Databases → crisisshield → Schemas → public → Tables` to browse `incidents`, `alerts`, `risk_scores`, `regions`, `users`.

---

## 17. Recent Updates

### April 2026 — Live Data & Chatbot Fixes

| Change | Description |
|--------|-------------|
| **Live news on startup** | Backend now fetches real news from Google News (Reuters, Naharnet, LBCI, NNA, Al Jazeera, L'Orient Today, etc.) immediately on startup in all storage modes, not just `postgres` mode |
| **Background news refresh** | A 5-minute `asyncio` background loop refreshes the news cache automatically without requiring Celery |
| **Chatbot live data fix** | Chat endpoint now reads from `live_news_service._cache` when `local_store` is empty (postgres mode), so the AI always has current news |
| **Chatbot system prompt** | Fully rewritten as an elite Lebanon intelligence analyst with current political leadership (Aoun, Salam, Berri, Nasrallah's death), exact incident timestamps, and no topic restrictions on Lebanon questions |
| **Alembic migration fix** | Fixed `DROP COLUMN IF EXISTS regions.geometry` SQL syntax error that prevented table creation |
| **ORM fix** | Renamed reserved SQLAlchemy attribute `metadata` → `extra_metadata` (mapped to `metadata` column) |
| **PostgreSQL seed script** | Added `backend/seed_pg.py` to manually sync live news into PostgreSQL for DBeaver visibility |
4. Restart workers: `docker-compose restart celery-worker celery-beat`
