from fastapi import APIRouter

from app.api.v1.endpoints import alerts, auth, dashboard, incidents, official_feeds, risk_analysis

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
router.include_router(risk_analysis.router, prefix="/risk", tags=["risk"])
router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
router.include_router(official_feeds.router, prefix="/official-feeds", tags=["official-feeds"])
