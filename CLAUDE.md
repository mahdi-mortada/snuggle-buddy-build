# CrisisShield / AMAN — Complete Project Documentation

> **NEW CHAT? START HERE.**
> This file is the single source of truth for every decision, fix, and feature built on this project.
> Read sections 1–4 for orientation, then jump to section 17 for the latest changes.
> GitHub repo: https://github.com/mahdi-mortada/snuggle-buddy-build
> Active branch with pending PR: `fix-telegram-validation`

---

## 1. What This Project Is

**CrisisShield** (internal name: **AMAN** — Integrated Smart Security Tool) is a full-stack crisis monitoring and intelligence platform for Lebanon. It provides real-time situational awareness to security analysts and decision makers by ingesting news and incident data, running NLP analysis, computing regional risk scores, detecting anomalies, forecasting escalation, and dispatching alerts.

**Stack**: React 18 + TypeScript + Vite (frontend) · FastAPI + Python 3.11 (backend) · PostgreSQL 16 + PostGIS · MongoDB 7 · Elasticsearch 8.12 · Redis · Apache Kafka · Celery · spaCy + HuggingFace (NLP) · Facebook Prophet (forecasting) · XGBoost (escalation) · Isolation Forest (anomaly) · LangChain + Claude API (AI recommendations) · MLflow (experiment tracking) · Prometheus + Grafana (monitoring)

---

## 2. Repository Layout

```
snuggle-buddy-build-main/
├── src/                          # React frontend (Vite + TypeScript)
│   ├── pages/                    # All page components (Dashboard, IncidentMap, Analytics, Alerts, OfficialFeeds, Login)
│   ├── components/
│   │   ├── layout/               # DashboardLayout, AppSidebar, Header (with NotificationCenter)
│   │   ├── dashboard/            # StatCards, LiveIncidentFeed, RegionalRiskList, RiskGauge, TrendCharts
│   │   ├── alerts/               # NotificationCenter.tsx (bell + dropdown)
│   │   ├── chat/                 # CrisisChat (in-app AI chatbot)
│   │   ├── shared/               # SourceBadge, CredibilityBadge
│   │   └── ui/                   # shadcn/ui components
│   ├── hooks/
│   │   ├── useLiveData.ts        # Main data aggregation hook (backend + Supabase + mock fallback)
│   │   └── useBackendWebSocket.ts # Auto-reconnect WebSocket hook
│   ├── services/
│   │   └── backendApi.ts         # All backend API calls with JWT auth + snake_case→camelCase mapping
│   ├── data/
│   │   ├── lebanon_geojson.ts    # Lebanon Governorate + District GeoJSON (33 features) for map choropleth
│   │   └── mockData.ts           # Fallback mock data for local demo mode
│   ├── types/
│   │   └── crisis.ts             # All TypeScript types (Incident, Alert, RiskScore, RiskPrediction, etc.)
│   └── lib/
│       └── runtimeConfig.ts      # Runtime env config (backend URL, Supabase keys, etc.)
│
├── backend/                      # FastAPI backend
│   ├── app/
│   │   ├── main.py               # FastAPI app, lifespan (DB connect, NLP init, Kafka start), WebSocket /ws/live-feed
│   │   ├── config.py             # All settings via pydantic-settings (env vars, thresholds, ML config)
│   │   ├── api/v1/
│   │   │   ├── router.py
│   │   │   └── endpoints/
│   │   │       ├── auth.py           # POST /login, GET /me
│   │   │       ├── incidents.py      # CRUD + /live + /geo + /{id}/review
│   │   │       ├── risk_analysis.py  # /current, /region/{region}, /predictions, /history, /recalculate
│   │   │       ├── alerts.py         # list, stats, /{id}/acknowledge
│   │   │       ├── dashboard.py      # /overview, /trends, /hotspots
│   │   │       └── official_feeds.py
│   │   ├── db/
│   │   │   ├── orm.py            # SQLAlchemy ORM models (RegionORM, IncidentORM, RiskScoreORM, AlertORM, UserORM)
│   │   │   ├── postgres.py       # asyncpg engine, session_scope(), get_db() dependency
│   │   │   ├── mongodb.py        # Motor async client + TTL index (90d on raw_data)
│   │   │   ├── elasticsearch.py  # AsyncElasticsearch + Arabic analyzer index mapping
│   │   │   └── redis.py          # aioredis + risk weights, alert thresholds, threat keywords, rate limiting
│   │   ├── models/               # Pydantic v2 domain models (IncidentRecord, AlertRecord, RiskScoreRecord, UserRecord)
│   │   ├── schemas/              # Pydantic request/response schemas (IncidentOut, AlertOut, RiskOut, etc.)
│   │   ├── services/
│   │   │   ├── nlp_pipeline.py       # Language detect → Arabic normalize → spaCy NER → HuggingFace sentiment → zero-shot category → keyword score
│   │   │   ├── feature_engineering.py # Sentiment velocity, volume z-score, keyword score, behavior patterns, geospatial density
│   │   │   ├── location_resolver.py  # GPS→PostGIS ST_Within, NLP GPE→fuzzy alias match, ~80 Lebanon aliases
│   │   │   ├── risk_scoring.py       # 5-component risk formula (sentiment+volume+keyword+behavior+geospatial), weights from Redis
│   │   │   ├── anomaly_detection.py  # Isolation Forest (n=100, contamination=0.1), weekly retrain
│   │   │   ├── prediction_engine.py  # Facebook Prophet per-region (24h/48h/7d), daily retrain
│   │   │   ├── escalation_model.py   # GradientBoostingClassifier, MLflow tracking, 8-feature vector
│   │   │   ├── alert_service.py      # Redis thresholds, rate limiting (1/region/severity/hr), velocity+anomaly+escalation triggers
│   │   │   ├── recommendation_engine.py # LangChain + Claude claude-haiku-4-5-20251001, Redis cache TTL 1hr
│   │   │   ├── notification_service.py  # FastAPI-Mail (SMTP), Twilio SMS (EMERGENCY only), webhook POST
│   │   │   ├── seed_data.py          # 505 realistic incidents: 8 categories × 8 regions × 30 days (deterministic RNG seed=42)
│   │   │   ├── local_store.py        # In-memory store (fallback when no DB), list/get/update incidents/alerts/risk scores
│   │   │   └── auth_service.py       # JWT (HS256), bcrypt passwords
│   │   ├── workers/
│   │   │   ├── kafka_consumer.py     # Consumes raw-incidents → NLP → location → store → ES → processed-incidents → WebSocket
│   │   │   └── celery_tasks.py       # Beat: risk recalc (15min), news (2min), Prophet retrain (daily), anomaly retrain (weekly)
│   │   └── tests/
│   │       ├── test_health.py
│   │       ├── test_auth.py
│   │       ├── test_incidents.py     # 11 tests (list, filter, pagination, geo, auth)
│   │       ├── test_risk.py          # 11 tests (scores, region detail, predictions, history)
│   │       ├── test_alerts.py        # 9 tests (list, stats, acknowledge, auth)
│   │       ├── test_dashboard.py     # 5 tests (overview, trends, hotspots)
│   │       ├── test_nlp.py           # 11 tests (seed data integrity, risk scoring, async NLP)
│   │       └── test_official_feeds.py
│   ├── alembic/versions/
│   │   └── 001_initial_schema.py    # Full schema: PostGIS ext, regions, users, incidents, risk_scores, alerts
│   ├── data/
│   │   └── lebanon_boundaries.geojson # 33 Lebanon GeoJSON features (8 governorates + 25 districts)
│   ├── pyproject.toml               # pytest config: asyncio_mode=auto, testpaths=app/tests
│   └── requirements.txt             # Full ML stack (asyncpg, motor, elasticsearch, redis, spacy, transformers, prophet, xgboost, mlflow, langchain, etc.)
│
├── infrastructure/
│   ├── monitoring/
│   │   └── prometheus.yml           # Scrape: backend:8000/metrics, redis:6379, kafka:9092
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/prometheus.yml  # Grafana auto-connects to Prometheus
│   │   │   └── dashboards/dashboards.yml   # Points to /etc/grafana/dashboards
│   │   └── dashboards/
│   │       └── crisisshield.json    # 8-panel dashboard: API rate, p95 latency, error rate, WebSocket conns, Kafka lag, NLP latency, risk scores by region
│   └── nginx/
│       └── nginx.conf               # Production reverse proxy config
│
├── ml-pipeline/
│   ├── models/                      # Trained artifacts (anomaly_detector.pkl, prophet/*.pkl)
│   ├── notebooks/                   # Exploratory notebooks
│   └── scripts/                     # Training scripts
│
└── docker-compose.yml               # All services: postgres, mongodb, elasticsearch, redis, zookeeper, kafka, backend, celery-worker, celery-beat, mlflow, prometheus, grafana
```

---

## 3. Environment Variables (.env)

Copy `.env.example` to `.env`. Key variables:

```env
# Storage mode
STORAGE_MODE=local                  # "local" = in-memory (no DB needed), "postgres" = full DB

# Databases (only needed when STORAGE_MODE=postgres)
DATABASE_URL=postgresql+asyncpg://crisisshield:crisisshield@localhost:5432/crisisshield
MONGODB_URL=mongodb://crisisshield:crisisshield@localhost:27017
ELASTICSEARCH_URL=http://localhost:9200
REDIS_URL=redis://localhost:6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:29092

# JWT
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Default admin user (created on startup)
DEFAULT_ADMIN_EMAIL=admin@crisisshield.dev
DEFAULT_ADMIN_PASSWORD=admin12345

# Claude AI (for AI recommendations on CRITICAL/EMERGENCY alerts)
CLAUDE_API_KEY=your-anthropic-api-key

# MLflow
MLFLOW_TRACKING_URI=http://localhost:5000

# Notifications (all optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@crisisshield.dev
SMTP_FROM_NAME=CrisisShield
ALERT_EMAIL_RECIPIENTS=ops@example.com

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_PHONE=
ALERT_SMS_RECIPIENTS=          # EMERGENCY only

ALERT_WEBHOOK_URLS=            # comma-separated

# Alert thresholds (tunable without code changes — also stored in Redis)
ALERT_THRESHOLD_INFO=40
ALERT_THRESHOLD_WARNING=60
ALERT_THRESHOLD_CRITICAL=80
ALERT_THRESHOLD_EMERGENCY=90

# Risk scoring weights (must sum to 1.0)
RISK_WEIGHT_SENTIMENT=0.25
RISK_WEIGHT_VOLUME=0.25
RISK_WEIGHT_KEYWORD=0.20
RISK_WEIGHT_BEHAVIOR=0.15
RISK_WEIGHT_GEOSPATIAL=0.15
```

---

## 4. How to Run

### Quick local mode (no databases needed)
```bash
# Terminal 1 — Backend (in-memory local store)
cd backend
pip install -r requirements.txt
STORAGE_MODE=local uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
npm install
npm run dev
# or: bun install && bun dev
```
Frontend: http://localhost:8080  
Backend: http://localhost:8000  
Login: admin@crisisshield.dev / admin12345

### Full Docker stack

```bash
# Step 1 — navigate to project root (inner folder)
cd C:\Users\MahdiMortada\Downloads\snuggle-buddy-build-main\snuggle-buddy-build-main

# Step 2 — copy env files (first time only)
cp backend/.env.example backend/.env

# Step 3 — set STORAGE_MODE=postgres in backend/.env
# Open backend/.env and change STORAGE_MODE=local to STORAGE_MODE=postgres

# Step 4 — build and start all 13 services
docker-compose up --build

# Step 5 — (separate terminal, after postgres is healthy) run DB migrations
docker-compose exec backend alembic upgrade head

# Step 6 — seed data is loaded automatically on first startup
# Verify: docker-compose exec backend curl -s http://localhost:8000/health
```

**Service URLs (Docker):**

| Service | URL | Login |
|---|---|---|
| Frontend | http://localhost:3002 | admin@crisisshield.dev / admin12345 |
| Backend API | http://localhost:8010 | JWT via `/api/v1/auth/login` |
| API Docs (Swagger) | http://localhost:8010/docs | — |
| Grafana | http://localhost:3001 | admin / crisisshield |
| Prometheus | http://localhost:9090 | — |
| MLflow | http://localhost:5001 | — |
| Kafka (host access) | localhost:29093 | — |

**Note:** Docker ports are offset from standard values to avoid conflicts with locally installed services (e.g. PostgreSQL runs on host port 5433, not 5432).

**Useful Docker commands:**
```bash
# View logs for a specific service
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Restart a single service after code changes
docker-compose up --build backend

# Stop all services (keep volumes/data)
docker-compose down

# Stop and wipe all data
docker-compose down -v

# Open a shell inside the backend container
docker-compose exec backend bash
```

### Run tests
```bash
cd backend
pip install -r requirements.txt
pytest
```

---

## 5. Frontend Architecture

### Data flow
1. `useLiveData(30000)` is called by every page — it is the single source of truth
2. If `VITE_BACKEND_API_URL` is set → calls `fetchBackendDashboardSnapshot()` from `backendApi.ts`
3. If `VITE_SUPABASE_*` is set → calls Supabase Edge Function `/live-news`
4. Otherwise → uses `mockData.ts` (demo mode)
5. `useBackendWebSocket` connects to `ws://localhost:8000/ws/live-feed` and triggers re-fetches on `incident`/`alert`/`risk_update` messages

### Key frontend files

| File | Purpose |
|------|---------|
| `src/services/backendApi.ts` | All API calls. Every `BackendXxx` type maps snake_case → camelCase. Exports: `fetchBackendDashboardSnapshot`, `fetchBackendPredictions`, `fetchBackendRegionDetail`, `fetchBackendAlertStats`, `fetchBackendHotspots`, `acknowledgeBackendAlert`, `fetchBackendOfficialFeedPosts` |
| `src/types/crisis.ts` | All shared types: `Incident`, `Alert`, `RiskScore`, `RiskPrediction`, `RegionRiskDetail`, `AlertStats`, `DashboardStats`, `OfficialFeedPost`, `TrendDataPoint`. `IncidentCategory` includes `armed_conflict`. |
| `src/data/lebanon_geojson.ts` | 33 GeoJSON features. `GOVERNORATE_FEATURES` used by IncidentMap choropleth. |
| `src/hooks/useLiveData.ts` | Returns: `{ incidents, stats, riskScores, alerts, trendData, lastUpdated, acknowledgeAlert, acknowledgeAllAlerts, connectionStatus }` |
| `src/components/layout/DashboardLayout.tsx` | Wraps every page. Accepts `liveData` prop including `acknowledgeAlert` callback. Passes `alerts` to Header → `NotificationCenter`. |
| `src/components/alerts/NotificationCenter.tsx` | Bell icon with unread badge. Dropdown panel with per-alert acknowledge and acknowledge-all. |

### Pages

| Page | Route | Key feature |
|------|-------|-------------|
| Dashboard | `/` | StatCards, LiveIncidentFeed, RegionalRiskList, RiskGauge, TrendCharts |
| Incident Map | `/map` | Leaflet map — Lebanon GeoJSON **polygon choropleth** (risk → color) + incident circle markers. Toggle heatmap button + legend. |
| Analytics | `/analytics` | Risk breakdown stacked bar, radar chart, sentiment trend, **prediction chart** (uses real Prophet data when backend available with confidence bands), anomaly log table |
| Alerts | `/alerts` | Alert list with tabs (All/Emergency/Critical/Warning/Acknowledged). **Web Audio API sound alerts** for CRITICAL/EMERGENCY. Sound On/Off toggle. |
| Official Feeds | `/official-feeds` | Telegram/X posts from official Lebanese media accounts |
| Settings | `/settings` | User settings |

---

## 6. Backend Architecture

### Request lifecycle (full stack)
```
External news / Kafka message
  → kafka_consumer.py
    → nlp_pipeline.py         (language, entities, sentiment, category, keywords)
    → location_resolver.py    (GPS or text → Lebanon region name)
    → IncidentRecord saved (local_store OR PostgreSQL)
    → elasticsearch.py        (index for full-text search)
    → processed-incidents topic published
    → websocket_manager       (broadcast to connected clients)
      → useLiveData re-fetches
```

### Alert pipeline
```
risk_scoring.py calculates RiskScoreRecord
  → alert_service.generate_alerts_async()
    → Redis: check threshold (info=40/warning=60/critical=80/emergency=90)
    → Redis: rate limit (1 alert per region:severity per hour)
    → velocity trigger (score up >15 in 2h)
    → anomaly trigger (Isolation Forest flags)
    → escalation trigger (XGBoost prob >70%)
    → recommendation_engine.generate() → LangChain + Claude claude-haiku-4-5-20251001
    → notification_service.dispatch() → email (CRITICAL+) / SMS (EMERGENCY) / webhook
    → websocket_manager.broadcast()
```

### Celery beat schedule
| Task | Interval |
|------|----------|
| Risk recalculation (all regions) | Every 15 minutes |
| Live news ingestion | Every 2 minutes |
| Prophet model retrain | Daily at midnight |
| Isolation Forest retrain | Weekly Sunday 02:00 |

### API Endpoints

All routes under `/api/v1/` — JWT Bearer auth required (except `/auth/login`).

**Auth**
- `POST /auth/login` — `{email, password}` → `{access_token, token_type}`
- `GET /auth/me` — current user profile

**Incidents**
- `GET /incidents` — list with filters: `region`, `severity`, `category`, `status`, `search`, `page`, `per_page`
- `POST /incidents` — create
- `GET /incidents/{id}` — detail
- `PATCH /incidents/{id}/review` — analyst review (verification_status, analyst_notes, severity override)
- `GET /incidents/live` — last N incidents sorted by created_at
- `GET /incidents/geo` — GeoJSON FeatureCollection for map

**Risk**
- `GET /risk/current` — all region risk scores
- `GET /risk/region/{region}` — detail with `is_anomalous`, `anomaly_score`, `escalation_probability`, `incident_count_24h`
- `GET /risk/predictions` — Prophet forecasts (24h/48h/7d per region). Query: `?region=Beirut`
- `GET /risk/history` — historical scores. Query: `?region=Beirut&hours=48`
- `POST /risk/recalculate` — trigger immediate recalc

**Alerts**
- `GET /alerts` — list with filters: `region`, `severity`, `acknowledged`
- `GET /alerts/stats` — `{total, acknowledged, by_severity, average_response_minutes}`
- `PATCH /alerts/{id}/acknowledge` — acknowledge alert

**Dashboard**
- `GET /dashboard/overview` — `{total_incidents_24h, active_alerts, avg_risk_score, top_risk_region}`
- `GET /dashboard/trends` — 24h trend data `[{time, incidents, risk_score, sentiment}]`
- `GET /dashboard/hotspots` — GeoJSON FeatureCollection of incident clusters

**Official Feeds**
- `GET /official-feeds` — Telegram/X posts from tracked Lebanese media accounts

**WebSocket**
- `WS /ws/live-feed` — on connect sends `{type:"snapshot", data:{incidents, alerts}}`. Broadcasts `{type:"incident"}`, `{type:"alert"}`, `{type:"risk_update"}`, `{type:"heartbeat"}`

**Health**
- `GET /health` — DB ping status, storage mode, seeded counts
- `GET /metrics` — Prometheus metrics

---

## 7. Database Schema (PostgreSQL + PostGIS)

```sql
-- Alembic: backend/alembic/versions/001_initial_schema.py

regions (
  id TEXT PK,
  name TEXT UNIQUE,        -- "Beirut", "North Lebanon", etc.
  name_ar TEXT,
  region_type TEXT,        -- "governorate" | "district"
  parent_id TEXT,
  geom geometry(POLYGON,4326),     -- PostGIS polygon
  centroid geography(POINT,4326),
  centroid_lat FLOAT,
  centroid_lng FLOAT
)

users (
  id UUID PK,
  email TEXT UNIQUE,
  hashed_password TEXT,
  full_name TEXT,
  role TEXT,               -- "admin" | "analyst" | "viewer"
  organization TEXT,
  is_active BOOL
)

incidents (
  id TEXT PK,
  source TEXT,             -- "news" | "manual" | "sensor"
  source_id TEXT,
  title TEXT,
  description TEXT,
  raw_text TEXT,
  processed_text TEXT,
  category TEXT,           -- violence|protest|natural_disaster|infrastructure|health|terrorism|cyber|armed_conflict|other
  severity TEXT,           -- low|medium|high|critical
  location geography(POINT,4326),
  location_name TEXT,
  region TEXT,
  sentiment_score FLOAT,
  risk_score FLOAT,
  entities TEXT[],
  keywords TEXT[],
  status TEXT,             -- new|processing|analyzed|escalated|resolved|false_alarm
  processing_status TEXT,
  verification_status TEXT, -- unverified|reviewed|confirmed|rejected
  confidence_score FLOAT,
  reviewed_by UUID FK→users,
  reviewed_at TIMESTAMPTZ,
  analyst_notes TEXT,
  source_info JSONB,       -- SourceInfoRecord
  source_url TEXT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
  -- Indexes: GIN trigram on title, btree on region+created_at, btree on severity, geography GIST on location
)

risk_scores (
  id TEXT PK,
  region TEXT,
  overall_score FLOAT,
  sentiment_component FLOAT,
  volume_component FLOAT,
  keyword_component FLOAT,
  behavior_component FLOAT,
  geospatial_component FLOAT,
  confidence FLOAT,
  is_anomalous BOOL,
  anomaly_score FLOAT,
  escalation_probability FLOAT,
  incident_count_24h INT,
  calculated_at TIMESTAMPTZ
)

alerts (
  id TEXT PK,
  risk_score_id TEXT FK,
  incident_id TEXT FK,
  alert_type TEXT,         -- threshold_breach|escalation|anomaly|prediction|velocity
  severity TEXT,           -- info|warning|critical|emergency
  title TEXT,
  message TEXT,
  recommendation TEXT,
  region TEXT,
  is_acknowledged BOOL,
  acknowledged_by UUID FK→users,
  acknowledged_at TIMESTAMPTZ,
  notification_channels TEXT[],
  linked_incidents TEXT[],
  created_at TIMESTAMPTZ
)
```

**MongoDB** (`raw_data` collection): TTL index `expireAfterSeconds=7776000` (90 days) on `collected_at`

**Elasticsearch** (`incidents` index): Arabic analyzer with `arabic_normalization`, `arabic_stop`, `arabic_stemmer` filters. Fields: `title`, `description`, `region`, `category`, `severity`, `keywords`, `created_at`

**Redis** keys:
- `risk_weights` hash → `{sentiment, volume, keyword, behavior, geospatial}` (float, sum=1.0)
- `alert_thresholds` hash → `{info, warning, critical, emergency}` (float 0-100)
- `threat_keywords` hash → keyword → float weight (40 Arabic+English terms)
- `alert_rate:{region}:{severity}` → TTL key for rate limiting
- `recommendation:{region}:{severity}:{score_rounded}` → cached AI text, TTL 3600s
- `dashboard_cache` → cached overview, TTL 60s
- `risk_cache:{region}` → cached risk score, TTL 300s

---

## 8. Lebanon Regions (8 Governorates)

The system uses these canonical names — they must match exactly in API calls and filters:

| Name | Arabic | Centroid |
|------|--------|----------|
| Beirut | بيروت | 33.8938, 35.5018 |
| Mount Lebanon | جبل لبنان | 33.8100, 35.6500 |
| North Lebanon | الشمال | 34.4367, 35.8497 |
| South Lebanon | الجنوب | 33.2721, 35.2033 |
| Nabatieh | النبطية | 33.3772, 35.4836 |
| Bekaa | البقاع | 33.8463, 35.9019 |
| Baalbek-Hermel | بعلبك الهرمل | 34.0047, 36.2110 |
| Akkar | عكار | 34.5331, 36.0781 |

---

## 9. NLP Pipeline Detail

File: `backend/app/services/nlp_pipeline.py`

Steps (each has a graceful fallback if model unavailable):
1. **Language detection** — `langdetect` → `"ar"` or `"en"` or `"other"`
2. **Arabic normalization** — strip diacritics (tashkeel), normalize alef/ya/ta marbuta
3. **spaCy NER** — `en_core_web_lg` (English), `xx_ent_wiki_sm` (multilingual)
4. **Sentiment** — `cardiffnlp/twitter-roberta-base-sentiment-latest` (EN), `aubmindlab/bert-base-arabertv2` (AR). Fallback: keyword scoring from Redis threat_keywords
5. **Category** — `facebook/bart-large-mnli` zero-shot classification. Fallback: keyword heuristics
6. **Keyword scoring** — match against Redis `threat_keywords`, returns sorted list + weighted score

All models are **lazy-loaded once** at startup via `nlp_pipeline.initialize()` in `app/main.py` lifespan.

---

## 10. Risk Scoring Formula

File: `backend/app/services/risk_scoring.py`

```
overall_score = (
  w_sentiment * sentiment_component  +
  w_volume    * volume_component     +
  w_keyword   * keyword_component    +
  w_behavior  * behavior_component   +
  w_geospatial * geospatial_component
) * confidence
```

Default weights (Redis-configurable): sentiment=0.25, volume=0.25, keyword=0.20, behavior=0.15, geospatial=0.15

Components:
- **sentiment**: mean(sentiment_scores) × velocity factor (30-min window)
- **volume**: z-score normalized incident count (30-day rolling baseline)
- **keyword**: max(threat_keyword_score) in last 6 hours
- **behavior**: burst detection (≥3 incidents in 30 min) + escalated/total ratio + single-source spam penalty
- **geospatial**: incident density (incidents / km² from bounding box)

Confidence = f(incident_count): 0→0.5, 5→0.75, 10→0.9, 20+→0.95

---

## 11. Seed Data

File: `backend/app/services/seed_data.py`

`build_seed_incidents()` generates **505 incidents**:
- 5 hand-crafted original incidents (kept for backward compatibility with alert IDs)
- 500 programmatically generated using `random.Random(42)` (deterministic/reproducible)
- Coverage: all 8 regions × all 9 categories × 30-day time window
- Distribution: severity weighted (low=25%, medium=35%, high=28%, critical=12%)
- Sources: 13 realistic Lebanese/international sources (LBCI, NNA, L'Orient Today, An-Nahar, Al Jazeera, Lebanese Armed Forces, ISF, Civil Defence, WHO, ICRC, Reuters, Social Monitor, Manual Report)
- Spread: exponential distribution toward recent (most incidents in last ~7.5 days)

---

## 12. Current Status — What Is Complete

All 8 build phases are **100% complete**:

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Infrastructure — docker-compose (all services), Dockerfile (ML deps), .env.example, Prometheus, nginx | ✅ Done |
| 2 | Database layer — Alembic migration, Lebanon GeoJSON (33 features), asyncpg/Motor/ES/Redis real drivers | ✅ Done |
| 3 | Backend API core — all models, schemas, endpoints, location resolver (ST_Within + fuzzy alias) | ✅ Done |
| 4 | NLP pipeline — language detect, Arabic normalize, spaCy NER, HuggingFace sentiment/classification, Kafka consumer | ✅ Done |
| 5 | Risk scoring & prediction — 5-component formula, Prophet (24h/48h/7d), Isolation Forest, XGBoost + MLflow | ✅ Done |
| 6 | Alert system — Redis rate limiting, velocity/anomaly/escalation triggers, LangChain+Claude recommendations, email/SMS/webhook notifications | ✅ Done |
| 7 | Frontend — `armed_conflict` category, Lebanon polygon choropleth heatmap, prediction chart wired to Prophet, Web Audio sound alerts, NotificationCenter bell, backendApi new endpoints | ✅ Done |
| 8 | Integration & testing — 505 seed incidents, 53 pytest tests (incidents/risk/alerts/dashboard/nlp/auth/health), Grafana dashboard (8 panels), pyproject.toml asyncio_mode | ✅ Done |

---

## 13. What Needs to Be Done Next (Possible Extensions)

These were NOT part of the original build and have not been started:
- **Analyst workflow UI** — frontend form for `PATCH /incidents/{id}/review` (verification_status, analyst_notes)
- **Real Kafka ingestion** — currently the consumer polls mock data in `data_ingestion.py`; a real news scraper/RSS feed needs to be built
- **Arabic spaCy model** — `xx_ent_wiki_sm` is multilingual; a proper Arabic NER model (`ar_core_news_lg` if available) would improve accuracy
- **Frontend Settings page** — currently a stub; could expose Redis threshold/weight tuning UI
- **Map district layer** — IncidentMap currently shows only governorate polygons; could add district-level detail on zoom
- **Persistent live news → PostgreSQL** — live news is currently stored in memory only; writing it to PostgreSQL automatically on every refresh would make data fully persistent across restarts

---

## 14. Important Technical Decisions (Do Not Change)

| Decision | Why |
|----------|-----|
| `STORAGE_MODE=local` uses in-memory store, not DB | Allows zero-infrastructure demo; all endpoints work without Docker |
| `asyncpg` not `psycopg2` | Blueprint required fully async I/O throughout |
| HuggingFace models lazy-loaded once at startup | Models are 400MB+; per-request loading would be unusable |
| Risk weights and alert thresholds live in Redis | Blueprint: tunable at runtime without code deployments |
| `random.Random(42)` for seed data | Reproducible test data; same 505 incidents every restart |
| Alert rate limit: 1 per region:severity per hour | Prevents alert fatigue from rapid risk score fluctuations |
| Claude model: `claude-haiku-4-5-20251001` | Fast + cheap for operational recommendations; falls back to templates if key absent |
| No `armed_conflict` → `other` fallback | `armed_conflict` is a first-class category per blueprint Section 0.4.2 |
| Frontend never rebuilt from scratch | Existing design was high quality and matched blueprint exactly |

---

## 15. Files Modified in This Project (Full Change Log)

### New files created
- `backend/app/db/orm.py` — SQLAlchemy ORM models
- `backend/app/services/location_resolver.py` — GPS+text→region
- `backend/app/services/anomaly_detection.py` — Isolation Forest
- `backend/app/services/escalation_model.py` — XGBoost + MLflow
- `backend/app/services/notification_service.py` — email/SMS/webhook
- `backend/alembic/versions/001_initial_schema.py` — full DB migration
- `backend/data/lebanon_boundaries.geojson` — 33 GeoJSON features
- `src/data/lebanon_geojson.ts` — TypeScript GeoJSON for frontend
- `src/components/alerts/NotificationCenter.tsx` — notification bell
- `backend/app/tests/test_incidents.py`
- `backend/app/tests/test_risk.py`
- `backend/app/tests/test_alerts.py`
- `backend/app/tests/test_nlp.py`
- `backend/app/tests/test_dashboard.py`
- `infrastructure/grafana/provisioning/datasources/prometheus.yml`
- `infrastructure/grafana/provisioning/dashboards/dashboards.yml`
- `infrastructure/grafana/dashboards/crisisshield.json`

### Files significantly rebuilt
- `backend/app/config.py` — all new settings (SMTP, Twilio, Claude, MLflow, thresholds, weights)
- `backend/app/db/postgres.py` — real asyncpg engine
- `backend/app/db/mongodb.py` — real Motor + TTL index
- `backend/app/db/elasticsearch.py` — real ES client + Arabic index
- `backend/app/db/redis.py` — real aioredis + initial config seeding
- `backend/app/services/nlp_pipeline.py` — full NLP pipeline
- `backend/app/services/feature_engineering.py` — z-scores, velocity, behavior
- `backend/app/services/risk_scoring.py` — 5-component formula
- `backend/app/services/prediction_engine.py` — Prophet forecasting
- `backend/app/services/alert_service.py` — Redis thresholds + triggers
- `backend/app/services/recommendation_engine.py` — LangChain + Claude
- `backend/app/services/seed_data.py` — 505 realistic incidents
- `backend/app/workers/kafka_consumer.py` — full pipeline
- `backend/app/workers/celery_tasks.py` — beat schedule
- `backend/app/main.py` — NLP init, Kafka start, Prometheus
- `docker-compose.yml` — celery-worker, celery-beat, mlflow, prometheus, grafana
- `backend/Dockerfile` — spaCy models, system ML deps
- `backend/requirements.txt` — full ML stack
- `backend/pyproject.toml` — asyncio_mode=auto

### Frontend files updated
- `src/types/crisis.ts` — armed_conflict, verification fields, RiskPrediction, AlertStats, RegionRiskDetail
- `src/services/backendApi.ts` — new types + fetch functions for predictions/region/stats/hotspots
- `src/pages/IncidentMap.tsx` — GeoJSON choropleth layer + legend + armed_conflict category
- `src/pages/Analytics.tsx` — real Prophet predictions wired in
- `src/pages/Alerts.tsx` — Web Audio sound alerts + sound toggle
- `src/components/layout/Header.tsx` — NotificationCenter replaces static bell
- `src/components/layout/DashboardLayout.tsx` — passes alerts + acknowledgeAlert to Header

---

## 16. Post-Build Fixes (April 2026)

These changes were made after all 8 phases were complete, during live testing.

### Chat Endpoint (`backend/app/api/v1/endpoints/chat.py`)

**Problem:** In `STORAGE_MODE=postgres`, `local_store` starts empty (seed data not loaded). The chat endpoint called `local_store.list_incidents()` → got 0 results → Claude had no incident data.

**Fix:** When `local_store` is empty, fall back to `live_news_service._cache` which is always populated at startup:
```python
store_incidents = local_store.list_incidents()
if not store_incidents:
    from app.services.live_news import live_news_service
    store_incidents = live_news_service._cache or []
```

**Chatbot system prompt also rewritten** to be a comprehensive Lebanon intelligence analyst:
- Current political leadership: President Joseph Aoun (elected Jan 9, 2025), PM Nawaf Salam, Speaker Nabih Berri, Hassan Nasrallah killed Sept 27, 2024
- Rule 1: Answer ANY Lebanon question freely — no topic restrictions
- Rule 3: Always use exact timestamps from incident data — never claim dates are unavailable
- Data priority: frontend context → live news cache → local store

### Live News Background Refresh (`backend/app/main.py`)

**Problem:** `live_news_service.sync_current_incidents()` was only called at startup in `STORAGE_MODE=postgres`. In all other modes, the in-memory cache never refreshed.

**Fix:**
1. Startup fetch now runs in **all modes** (removed `if settings.storage_mode == "postgres":` guard)
2. Added `_news_refresh_loop()` — an `asyncio` background task refreshing every 5 minutes

### Alembic Migration Fix (`backend/alembic/versions/001_initial_schema.py`)

Fixed invalid SQL: `DROP COLUMN IF EXISTS regions.geometry` → `ALTER TABLE regions DROP COLUMN IF EXISTS geometry`

### ORM Fix (`backend/app/db/orm.py`)

`metadata` is a reserved attribute in SQLAlchemy's Declarative API. Renamed to `extra_metadata` with a column alias:
```python
extra_metadata = Column("metadata", JSONB, default=dict)
```

### PostgreSQL Seed Script (`backend/seed_pg.py`)

One-time utility script to populate the PostgreSQL `incidents` table from the live news cache. Run inside the container:
```bash
docker-compose exec backend python /app/seed_pg.py
```

### DBeaver Database Access

PostgreSQL is accessible from the host at `localhost:5433` (Docker maps 5433 → 5432 internally).
- Username: `postgres` / Password: `postgres` / Database: `crisisshield`
- Run `alembic upgrade head` inside the backend container before connecting to create tables
- Tables: `incidents`, `alerts`, `risk_scores`, `regions`, `users`

### Git Workflow Rule

**CRITICAL:** Never push directly to `main`. Always create a feature branch, push that branch, then open a PR on GitHub for review and merge. This rule applies to all future changes.
- `src/pages/Dashboard.tsx` — passes acknowledgeAlert to DashboardLayout

---

## 17. Post-Build Fixes — April 2026 (Session 2)

Everything below was built after Section 16. All changes are on branch **`fix-telegram-validation`** (pending PR merge into `main`).

---

### 17.1 Telegram Channel Validation — No API Required

**Problem:** Adding a source in Official Feeds gave: *"Telegram validation is unavailable because Telethon is not installed"*. Telethon requires an API_ID, API_HASH and a session string that many users cannot obtain.

**Solution — two-tier validation in `backend/app/services/telegram_client.py`:**

1. **HTTP fallback (default when no credentials):** Fetches `https://t.me/s/{username}`. If Telegram keeps the response on the `/s/` URL → channel has a public web preview → extracts real title from `og:title` and accepts it. If Telegram redirects away from `/s/` (no web preview) → accepts the channel with username as display name.

2. **Telethon (primary when credentials configured):** Uses real Telegram MTProto API for validated channel names and real integer telegram_ids.

**Telethon credentials now configured in `backend/.env`:**
```env
TELEGRAM_API_ID=34716392
TELEGRAM_API_HASH=3f673040bbbfb24876f9980fb6eee372
TELEGRAM_SESSION_STRING=1BJWap1wBuzWc0THbh7Q8...  # (real session, keep secret)
TELEGRAM_REQUEST_TIMEOUT_SECONDS=10
```

**New file:** `backend/scripts/gen_telegram_session.py` — run once locally to regenerate the session string if it expires:
```bash
pip install telethon
python backend/scripts/gen_telegram_session.py
# Enter phone number → enter Telegram code → copy printed SESSION_STRING into .env
```

**`backend/requirements.docker.txt`** — added `Telethon>=1.37,<2.0` so Docker image has Telethon available.

---

### 17.2 Official Feeds — Custom Sources Always Show Posts

**Problem:** Alert-style channels (e.g. `redlinkleb` — Red Alert Lebanon) post short messages using only Arabic hashtags + emojis like `⭕️ 🛩 #مسير #صريفا`. The Lebanon-relevance + keyword filter in `official_feeds.py` dropped all their posts silently.

**Root fix in `backend/app/services/official_feeds.py` — `_enrich_post()`:**

```python
# Custom sources (user-added) → always show posts, skip all filters
if not post.is_custom:
    if not self._is_lebanon_relevant(post.content):
        return None

# Keyword fallback: use hashtags when no category keywords match
if not keywords:
    keywords = self._extract_hashtags(post.content)[:8]

# Only drop keyword-empty posts for default sources, never for custom
if not keywords and not post.is_custom:
    return None
```

**Also fixed `_is_lebanon_relevant()`** — normalises `_` to space before checking, so `#جنوب_لبنان` matches the keyword `جنوب لبنان`.

**Rule going forward:** Any channel added via "Add Source" (`is_custom=True`) will always have all its posts shown, regardless of language, format, or topic. Default official sources (LBCI, Al Jadeed, etc.) still go through Lebanon-relevance and keyword filtering.

---

### 17.3 Incident Map — Category Icons + Backend-Based Pin Placement

**Problem 1 — Wrong icons:** Map had only 4 generic marker kinds (`fire`, `conflict`, `crime`, `default`). All Arabic alert posts got `default` (blue pin) regardless of content.

**Problem 2 — Wrong pin placement:** The frontend re-analysed text locally with basic keyword matching and placed pins based on town name matches. A post about "Yaroun" could get placed at the wrong coordinates if the OSM scan matched a different town.

**Fix — `src/pages/IncidentMap.tsx`:**

**12 category-specific marker icons:**
| Kind | Emoji | Color | Triggered by |
|------|-------|-------|--------------|
| `violence` | ⚔️ | Red | category=violence |
| `armed_conflict` | 💥 | Dark Red | category=armed_conflict |
| `terrorism` | 💣 | Crimson | category=terrorism |
| `protest` | ✊ | Amber | category=protest |
| `natural_disaster` | 🌊 | Cyan | category=natural_disaster |
| `fire` | 🔥 | Orange | text: fire/blaze/حريق (sub-refinement) |
| `infrastructure` | ⚡ | Purple | category=infrastructure |
| `health` | 🏥 | Green | category=health |
| `cyber` | 💻 | Indigo | category=cyber |
| `drone` | 🛩️ | Rose | text: drone/uav/مسير (sub-refinement) |
| `crime` | 🚨 | Amber | text: crime/robbery/shooting |
| `default` | 📍 | Blue | fallback |

**Pin placement priority:**
1. Use backend-provided `incident.location` / `feed.location` (lat/lng already validated by NLP pipeline + location resolver)
2. Fall back to OSM text matching only if backend coordinates are missing or outside Lebanon bounds
3. `isFiniteCoordinate()` gate: only accepts lat 33.0–34.9, lng 35.0–36.9

**`src/types/crisis.ts`** — `OfficialFeedPost` now includes: `category`, `severity`, `region`, `location`, `locationName`, `riskScore`, `keywords`, `isSafetyRelevant`

**`src/services/backendApi.ts`** — `mapOfficialFeedPost()` now maps all new backend fields to the frontend type.

**Popup now shows:** colored dot + category label (e.g. "🔴 Armed Conflict · telegram") instead of just "Type: telegram".

---

### 17.4 Current Git State

| Branch | Status |
|--------|--------|
| `main` | Last merged: original build phases 1–8 + Section 16 fixes |
| `fix-telegram-validation` | **5 commits ahead of main — PENDING PR** |

**PR URL:** https://github.com/mahdi-mortada/snuggle-buddy-build/pull/new/fix-telegram-validation

**Commits on the branch (oldest → newest):**
1. `fix: replace Telethon with HTTP-based Telegram channel validation`
2. `chore: add Telegram session string generator script`
3. `fix: show posts from alert-style Telegram channels (e.g. Red Alert Lebanon)`
4. `fix: always show posts from user-added (custom) sources without filtering`
5. `feat: category-specific map icons and backend-based pin placement`

**To resume work:** checkout `fix-telegram-validation`, or merge the PR first then branch off `main`.

---

### 17.5 Known State After Session 2

- Docker is running all services on the user's machine
- `redlinkleb` (Red Alert Lebanon) was added as a custom source and is showing posts correctly
- Telethon credentials are live in `backend/.env` (not committed to git — .env is gitignored)
- `backend/requirements.docker.txt` has Telethon so it is installed in the Docker image
- The `.env` file must never be committed — it contains real Telegram session string and API key
