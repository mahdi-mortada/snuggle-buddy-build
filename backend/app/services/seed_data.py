from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.alert import AlertRecord
from app.models.incident import IncidentLocation, IncidentRecord, SourceInfoRecord
from app.models.risk_score import RiskScoreRecord
from app.models.user import UserRecord

REGION_COORDINATES: dict[str, tuple[float, float]] = {
    "Beirut": (33.8938, 35.5018),
    "North Lebanon": (34.4367, 35.8497),
    "South Lebanon": (33.2721, 35.2033),
    "Mount Lebanon": (33.81, 35.59),
    "Bekaa": (33.8463, 35.9019),
    "Nabatieh": (33.3772, 35.4836),
    "Akkar": (34.5331, 36.0781),
    "Baalbek-Hermel": (34.0047, 36.211),
}


def _source(name: str, source_type: str, credibility: str, score: float, initials: str, url: str | None = None) -> SourceInfoRecord:
    return SourceInfoRecord(
        name=name,
        type=source_type,
        credibility=credibility,
        credibilityScore=score,
        logoInitials=initials,
        url=url,
    )


SOURCES: dict[str, SourceInfoRecord] = {
    "lbci": _source("LBCI", "tv", "verified", 88, "LB", "https://www.lbci.com"),
    "nna": _source("NNA", "news_agency", "verified", 92, "NN", "https://nna-leb.gov.lb"),
    "lorient": _source("L'Orient Today", "newspaper", "verified", 90, "LO", "https://today.lorientlejour.com"),
    "army": _source("Lebanese Armed Forces", "government", "verified", 95, "LA"),
    "manual": _source("Manual Report", "government", "high", 75, "MR"),
}


def build_seed_incidents() -> list[IncidentRecord]:
    now = datetime.now(UTC)
    samples = [
        ("news", "Crowd buildup near Martyrs' Square", "Growing crowd reported near downtown Beirut.", "protest", "high", "Beirut", "Martyrs' Square", -0.72, 78, ["Martyrs' Square", "Beirut"], ["crowd", "protest"], "lbci"),
        ("news", "Power outage in Tripoli industrial zone", "Large outage affecting factories and nearby services.", "infrastructure", "critical", "North Lebanon", "Tripoli Industrial Zone", -0.88, 89, ["Tripoli"], ["power", "outage", "grid"], "nna"),
        ("news", "Flash flooding risk in Bekaa", "Heavy rainfall is creating flood conditions in low-lying farms.", "natural_disaster", "high", "Bekaa", "Bekaa Valley", -0.64, 73, ["Bekaa Valley"], ["flood", "rain"], "lorient"),
        ("news", "Suspicious package investigated at Jounieh port", "Authorities are investigating a package near port operations.", "terrorism", "critical", "Mount Lebanon", "Jounieh Port", -0.91, 85, ["Jounieh", "port"], ["package", "security"], "army"),
        ("manual", "Respiratory illness cluster in Sidon clinic", "Local clinic has reported a rapid increase in respiratory cases.", "health", "medium", "South Lebanon", "Sidon", -0.42, 56, ["Sidon"], ["clinic", "health"], "manual"),
    ]

    incidents: list[IncidentRecord] = []
    for index, sample in enumerate(samples, start=1):
        source, title, description, category, severity, region, location_name, sentiment, risk, entities, keywords, source_key = sample
        lat, lng = REGION_COORDINATES[region]
        created_at = now - timedelta(minutes=index * 9)
        incidents.append(
            IncidentRecord(
                id=f"incident-{index}",
                source=source,  # type: ignore[arg-type]
                source_id=f"seed-{index}",
                title=title,
                description=description,
                raw_text=description,
                category=category,  # type: ignore[arg-type]
                severity=severity,  # type: ignore[arg-type]
                location=IncidentLocation(lat=lat, lng=lng),
                location_name=location_name,
                region=region,
                sentiment_score=sentiment,
                risk_score=risk,
                entities=entities,
                keywords=keywords,
                status="analyzed" if severity != "critical" else "escalated",
                source_info=SOURCES[source_key],
                source_url=SOURCES[source_key].url,
                created_at=created_at,
                updated_at=created_at,
            )
        )
    return incidents


def build_seed_risk_scores() -> list[RiskScoreRecord]:
    now = datetime.now(UTC)
    rows = [
        ("Beirut", 78, 82, 75, 80, 63, 70, 0.88),
        ("North Lebanon", 72, 75, 68, 77, 58, 61, 0.82),
        ("South Lebanon", 54, 49, 44, 59, 42, 48, 0.76),
        ("Mount Lebanon", 66, 64, 58, 69, 52, 60, 0.8),
        ("Bekaa", 59, 56, 61, 57, 43, 50, 0.79),
        ("Nabatieh", 44, 42, 39, 47, 34, 40, 0.74),
        ("Akkar", 38, 35, 40, 42, 31, 36, 0.71),
        ("Baalbek-Hermel", 47, 45, 43, 49, 35, 39, 0.73),
    ]
    return [
        RiskScoreRecord(
            id=f"risk-{region.lower().replace(' ', '-')}",
            region=region,
            overall_score=overall,
            sentiment_component=sentiment,
            volume_component=volume,
            keyword_component=keyword,
            behavior_component=behavior,
            geospatial_component=geospatial,
            confidence=confidence,
            calculated_at=now,
        )
        for region, overall, sentiment, volume, keyword, behavior, geospatial, confidence in rows
    ]


def build_seed_alerts(risk_scores: list[RiskScoreRecord]) -> list[AlertRecord]:
    now = datetime.now(UTC)
    risk_lookup = {risk.region: risk.id for risk in risk_scores}
    return [
        AlertRecord(
            id="alert-cyber-beirut",
            risk_score_id=risk_lookup["Beirut"],
            incident_id="incident-1",
            alert_type="prediction",
            severity="critical",
            title="Escalation predicted in Beirut",
            message="Risk velocity and crowd indicators suggest escalation over the next 24 hours.",
            recommendation="Increase monitoring near Martyrs' Square, coordinate crowd-management units, and issue a public traffic advisory.",
            region="Beirut",
            linked_incidents=["incident-1"],
            created_at=now - timedelta(minutes=18),
        ),
        AlertRecord(
            id="alert-tripoli-grid",
            risk_score_id=risk_lookup["North Lebanon"],
            incident_id="incident-2",
            alert_type="threshold_breach",
            severity="emergency",
            title="Critical infrastructure disruption in Tripoli",
            message="Power grid disruption has crossed the emergency threshold.",
            recommendation="Dispatch repair crews, notify hospitals, and activate contingency power plans.",
            region="North Lebanon",
            linked_incidents=["incident-2"],
            created_at=now - timedelta(minutes=9),
        ),
    ]


def build_seed_admin(hashed_password: str, email: str, full_name: str, organization: str) -> UserRecord:
    now = datetime.now(UTC)
    return UserRecord(
        id=str(uuid4()),
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        role="admin",
        organization=organization,
        created_at=now,
        updated_at=now,
    )
