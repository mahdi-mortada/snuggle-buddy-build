from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.alert import AlertRecord
from app.models.incident import IncidentLocation, IncidentRecord, SourceInfoRecord
from app.models.risk_score import RiskScoreRecord
from app.models.user import UserRecord

# Deterministic seed for reproducibility
_RNG = random.Random(42)

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

REGION_LOCATIONS: dict[str, list[str]] = {
    "Beirut": ["Martyrs' Square", "Hamra Street", "Achrafieh", "Dahiyeh", "Port Area", "Corniche", "Verdun", "Gemmayzeh"],
    "North Lebanon": ["Tripoli City Center", "Bab al-Tabbaneh", "Jabal Mohsen", "Mina Port", "Koura Road", "Zgharta"],
    "South Lebanon": ["Sidon Old City", "Sidon Port", "Tyre Coast", "Nabatieh Road", "Khiam", "Bint Jbeil"],
    "Mount Lebanon": ["Jounieh", "Jbeil (Byblos)", "Chouf Mountains", "Metn Highway", "Aley Village", "Baabda"],
    "Bekaa": ["Zahleh Center", "Chtaura Junction", "Bekaa Valley Farms", "West Bekaa Fields", "Rachaya"],
    "Nabatieh": ["Nabatieh Market", "Marjayoun Valley", "Hasbaya", "Bint Jbeil District", "Ibl al-Saqi"],
    "Akkar": ["Halba Town", "Kobayat Village", "Akkar Agricultural Zone", "Minyeh"],
    "Baalbek-Hermel": ["Baalbek City", "Hermel Valley", "Qaa Village", "Yammouneh", "Labweh"],
}

# Source definitions
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
    "annahar": _source("An-Nahar", "newspaper", "verified", 87, "AN", "https://www.annahar.com"),
    "aljazeera": _source("Al Jazeera Arabic", "tv", "high", 85, "AJ", "https://www.aljazeera.net"),
    "army": _source("Lebanese Armed Forces", "government", "verified", 95, "LA"),
    "isf": _source("Internal Security Forces", "government", "verified", 94, "IS"),
    "civil_defense": _source("Civil Defence", "government", "high", 89, "CD"),
    "who": _source("WHO Lebanon", "ngo", "verified", 91, "WH", "https://www.emro.who.int/leb"),
    "icrc": _source("ICRC Lebanon", "ngo", "high", 88, "IC", "https://www.icrc.org/en/where-we-work/middle-east/lebanon"),
    "manual": _source("Manual Field Report", "government", "high", 75, "MR"),
    "twitter_monitor": _source("Social Monitor", "social_media", "moderate", 52, "SM"),
    "reuters": _source("Reuters", "news_agency", "verified", 93, "RT", "https://www.reuters.com"),
}

# ---------------------------------------------------------------------------
# Incident templates per category
# Each entry: (title_template, description_template, keywords, entities)
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, list[tuple[str, str, list[str], list[str]]]] = {
    "violence": [
        ("Armed clash reported in {location}", "Security forces and armed groups exchanged fire near {location}. Residents urged to avoid the area.", ["gunfire", "clash", "armed", "security"], ["security forces"]),
        ("Street altercation escalates in {location}", "A street fight escalated into an armed confrontation in {location}. Multiple injuries reported.", ["fighting", "violence", "altercation"], ["{region}"]),
        ("Shooting incident near {location}", "Gunshots reported near {location}. Police deployed to secure the area.", ["shooting", "gunfire", "police"], ["police"]),
        ("Violent protest dispersal in {location}", "Security forces dispersed a violent gathering in {location} using tear gas.", ["tear gas", "dispersal", "protest"], ["security forces", "{region}"]),
        ("Stabbing incident reported at {location}", "A stabbing was reported at {location}. Victim transported to hospital.", ["stabbing", "violence", "hospital"], ["{region}"]),
        ("Roadblock violence at {location}", "Armed individuals erected a roadblock near {location}, exchanging fire with passing vehicles.", ["roadblock", "armed", "gunfire"], ["militia"]),
    ],
    "protest": [
        ("Demonstrators block main road in {location}", "Hundreds of protesters blocked the main road near {location} demanding economic relief.", ["protest", "road block", "demonstration", "economic"], ["civil society"]),
        ("Anti-government march in {location}", "Thousands participated in an anti-government march starting from {location}.", ["march", "anti-government", "demonstration"], ["opposition"]),
        ("Labor strike disrupts services in {location}", "Workers launched a strike in {location}, disrupting public services and transport.", ["strike", "labor", "workers", "service disruption"], ["unions"]),
        ("Student protest at university near {location}", "Students gathered for a protest near {location} over tuition and political issues.", ["students", "protest", "university"], ["students"]),
        ("Sit-in at government building in {location}", "Protesters set up a sit-in outside a government building in {location}.", ["sit-in", "government", "protest"], ["civil society"]),
        ("Fuel price protest at {location}", "Residents gathered at {location} to protest fuel shortages and rising prices.", ["fuel", "prices", "protest", "shortage"], ["{region}"]),
    ],
    "natural_disaster": [
        ("Flash flooding reported near {location}", "Heavy rainfall caused flash flooding in low-lying areas near {location}. Roads submerged.", ["flooding", "flash flood", "rainfall", "road closure"], ["civil defence"]),
        ("Wildfire spreading near {location}", "A wildfire has broken out near {location} and is spreading due to high winds.", ["wildfire", "fire", "evacuation", "wind"], ["civil defence", "forests"]),
        ("Landslide blocks road at {location}", "A landslide caused by heavy rain has blocked the main road at {location}.", ["landslide", "road closure", "rain"], ["{region}"]),
        ("Earthquake tremors felt across {region}", "Residents near {location} reported tremors felt across the region. No major damage confirmed.", ["earthquake", "tremors", "seismic"], ["{region}"]),
        ("Snowstorm isolates {location}", "A major snowstorm has isolated {location}, cutting off access to mountain villages.", ["snow", "storm", "isolation", "mountain"], ["{region}"]),
        ("River overflow threatens {location}", "The river near {location} is overflowing following three days of continuous rain.", ["overflow", "river", "flooding", "rain"], ["civil defence"]),
    ],
    "infrastructure": [
        ("Power outage affecting {location}", "A major power outage has affected most of {location}, impacting hospitals and businesses.", ["power outage", "electricity", "grid failure"], ["EDL", "hospitals"]),
        ("Water supply cut in {location}", "The main water supply to {location} has been disrupted following a pipe burst.", ["water", "supply", "pipe burst", "disruption"], ["water authority"]),
        ("Internet disruption reported in {location}", "Residents report internet and mobile network disruptions in {location}.", ["internet", "telecom", "disruption", "mobile"], ["telecom"]),
        ("Bridge closure due to damage at {location}", "Structural damage has forced authorities to close the bridge at {location}.", ["bridge", "closure", "structural", "damage"], ["public works"]),
        ("Hospital generator failure in {location}", "A hospital in {location} is running on backup power after generator failure.", ["hospital", "generator", "power", "medical"], ["Ministry of Health"]),
        ("Fuel station shortage crisis in {location}", "Long queues forming at fuel stations across {location} as shortage intensifies.", ["fuel", "shortage", "petrol", "queues"], ["energy ministry"]),
    ],
    "health": [
        ("Cholera cases confirmed near {location}", "Health authorities have confirmed cholera cases in a displacement camp near {location}.", ["cholera", "outbreak", "displacement", "water"], ["WHO", "Ministry of Health"]),
        ("Respiratory illness cluster in {location}", "A cluster of respiratory illness cases has been reported in {location}, linked to air quality.", ["respiratory", "illness", "air quality", "hospital"], ["WHO"]),
        ("Dengue fever cases rising in {location}", "A rise in dengue fever cases has been documented across {location} due to mosquito breeding.", ["dengue", "fever", "mosquito", "outbreak"], ["Ministry of Health"]),
        ("COVID-19 resurgence in {location}", "Health officials report an increase in COVID-19 cases in {location} following gatherings.", ["covid", "coronavirus", "resurgence", "cases"], ["Ministry of Health", "WHO"]),
        ("Contaminated water supply in {location}", "Tests reveal contaminated water supplies in {location}, raising gastroenteritis risk.", ["contamination", "water", "gastroenteritis", "health"], ["water authority"]),
        ("Hepatitis A outbreak in {location}", "An outbreak of Hepatitis A has been traced to water sources near {location}.", ["hepatitis", "outbreak", "water", "contamination"], ["WHO", "UNICEF"]),
    ],
    "terrorism": [
        ("IED discovered near {location}", "An improvised explosive device was discovered and defused near {location}.", ["IED", "explosive", "bomb disposal", "security"], ["army", "ISF"]),
        ("Car bomb threat reported in {location}", "Security forces received credible intelligence about a car bomb threat near {location}.", ["car bomb", "threat", "security", "evacuation"], ["ISF", "army"]),
        ("Armed cell disrupted in {location}", "Security forces disrupted an armed cell operating near {location}, seizing weapons.", ["armed cell", "weapons", "disrupted", "security"], ["army"]),
        ("Suspicious package at {location}", "A suspicious package was found near {location}. Bomb disposal team deployed.", ["suspicious package", "bomb disposal", "security"], ["police"]),
        ("Attack on security checkpoint near {location}", "An armed attack was carried out against a security checkpoint near {location}.", ["checkpoint", "attack", "armed", "security forces"], ["army", "ISF"]),
        ("Rocket fired toward {location}", "A rocket was fired toward {location}, landing in an open area with no casualties.", ["rocket", "attack", "explosion"], ["army"]),
    ],
    "cyber": [
        ("Government website defaced in cyberattack", "Hackers defaced the website of a government ministry, posting political messages. Origin traced to actors near {location}.", ["cyberattack", "defacement", "hacking", "government"], ["cyber authority"]),
        ("Banking system outage after DDoS attack", "A major bank serving {location} reported service disruption following a DDoS attack.", ["DDoS", "cyber", "banking", "disruption"], ["bank", "cyber"]),
        ("State broadcaster hacked in {region}", "The state broadcaster's stream was hijacked for 30 minutes. Investigation ongoing.", ["hacking", "broadcaster", "cyber", "media"], ["media"]),
        ("Critical infrastructure targeted by malware", "Power grid control systems near {location} were targeted by sophisticated malware.", ["malware", "power grid", "cyber", "critical infrastructure"], ["energy authority"]),
        ("Phishing campaign targeting officials in {region}", "A coordinated phishing campaign is targeting government officials across {region}.", ["phishing", "cyber", "officials", "email"], ["government"]),
        ("Data breach at health ministry affecting {region}", "Patient data from health ministry servers was leaked, affecting residents of {region}.", ["data breach", "health", "privacy", "leak"], ["Ministry of Health"]),
    ],
    "armed_conflict": [
        ("Cross-border shelling near {location}", "Artillery shells landed in the {location} area. No casualties reported. Army deployed.", ["shelling", "artillery", "cross-border", "army"], ["Lebanese Army", "UNIFIL"]),
        ("Armed militia incursion near {location}", "Armed militia elements crossed into the {location} area. Security forces on high alert.", ["militia", "incursion", "armed", "security"], ["army"]),
        ("Military operation in {location}", "The Lebanese Army launched a targeted operation against armed groups near {location}.", ["military", "operation", "army", "armed groups"], ["Lebanese Army"]),
        ("Drone activity detected over {location}", "Military drones were observed over {location}. Air defense units placed on alert.", ["drone", "UAV", "military", "airspace"], ["army"]),
        ("Exchange of fire across border near {location}", "Brief exchanges of fire reported across the border near {location}. Ceasefire called.", ["border", "exchange", "gunfire", "ceasefire"], ["UNIFIL", "army"]),
        ("Unexploded ordnance found near {location}", "Unexploded ordnance from a previous conflict was discovered near {location}.", ["UXO", "ordnance", "demining", "explosive"], ["army", "demining"]),
    ],
    "other": [
        ("Unconfirmed reports of incident in {location}", "Unverified social media reports suggest an incident near {location}. Authorities investigating.", ["unconfirmed", "social media", "reports"], ["{region}"]),
        ("Crowd crush at event in {location}", "A crowd crush occurred at a public event in {location}, injuring several attendees.", ["crowd", "crush", "event", "injury"], ["{region}"]),
        ("Fire at market in {location}", "A fire broke out at the {location} market, damaging several stalls. No fatalities.", ["fire", "market", "damage", "emergency"], ["civil defence"]),
        ("Traffic accident blocks highway near {location}", "A multi-vehicle accident has blocked the main highway near {location}.", ["traffic", "accident", "highway", "blocked"], ["ISF"]),
        ("Refugee camp flooding in {location}", "Heavy rain caused flooding in a refugee camp near {location}.", ["refugees", "flooding", "camp", "rain"], ["UNHCR"]),
        ("Economic protest turns disorderly in {location}", "An economic protest in {location} turned disorderly as tensions escalated.", ["economic", "protest", "disorder"], ["{region}"]),
    ],
}

_SEVERITY_WEIGHTS = {
    "low": 0.25,
    "medium": 0.35,
    "high": 0.28,
    "critical": 0.12,
}

_SEVERITY_RISK: dict[str, tuple[float, float]] = {
    "low": (15.0, 45.0),
    "medium": (40.0, 65.0),
    "high": (60.0, 80.0),
    "critical": (75.0, 100.0),
}

_SEVERITY_SENTIMENT: dict[str, tuple[float, float]] = {
    "low": (-0.4, -0.1),
    "medium": (-0.65, -0.3),
    "high": (-0.85, -0.55),
    "critical": (-1.0, -0.8),
}

_STATUS_BY_SEVERITY = {
    "low": ["new", "analyzed", "resolved"],
    "medium": ["new", "processing", "analyzed"],
    "high": ["analyzed", "escalated"],
    "critical": ["escalated"],
}

_SOURCE_POOL_BY_CATEGORY: dict[str, list[str]] = {
    "violence": ["nna", "lbci", "isf", "army", "twitter_monitor"],
    "protest": ["lbci", "lorient", "annahar", "twitter_monitor"],
    "natural_disaster": ["nna", "civil_defense", "lbci", "reuters"],
    "infrastructure": ["nna", "lbci", "lorient", "manual"],
    "health": ["who", "nna", "lorient", "manual"],
    "terrorism": ["army", "isf", "nna", "reuters"],
    "cyber": ["nna", "lorient", "manual"],
    "armed_conflict": ["army", "nna", "reuters", "aljazeera"],
    "other": ["nna", "lbci", "twitter_monitor", "manual"],
}


def _jitter_coords(lat: float, lng: float, radius: float = 0.08) -> tuple[float, float]:
    dlat = _RNG.uniform(-radius, radius)
    dlng = _RNG.uniform(-radius, radius)
    return round(lat + dlat, 5), round(lng + dlng, 5)


def _pick_severity() -> str:
    choices = list(_SEVERITY_WEIGHTS.keys())
    weights = list(_SEVERITY_WEIGHTS.values())
    return _RNG.choices(choices, weights=weights, k=1)[0]


def _format_template(text: str, location: str, region: str) -> str:
    return text.replace("{location}", location).replace("{region}", region)


def build_seed_incidents() -> list[IncidentRecord]:
    now = datetime.now(UTC)
    incidents: list[IncidentRecord] = []

    regions = list(REGION_COORDINATES.keys())
    categories = list(_TEMPLATES.keys())

    # --- Original 5 seed incidents (kept for backward compatibility) ---
    original = [
        ("news", "Crowd buildup near Martyrs' Square", "Growing crowd reported near downtown Beirut.", "protest", "high", "Beirut", "Martyrs' Square", -0.72, 78, ["Martyrs' Square", "Beirut"], ["crowd", "protest"], "lbci"),
        ("news", "Power outage in Tripoli industrial zone", "Large outage affecting factories and nearby services.", "infrastructure", "critical", "North Lebanon", "Tripoli Industrial Zone", -0.88, 89, ["Tripoli"], ["power", "outage", "grid"], "nna"),
        ("news", "Flash flooding risk in Bekaa", "Heavy rainfall is creating flood conditions in low-lying farms.", "natural_disaster", "high", "Bekaa", "Bekaa Valley", -0.64, 73, ["Bekaa Valley"], ["flood", "rain"], "lorient"),
        ("news", "Suspicious package investigated at Jounieh port", "Authorities are investigating a package near port operations.", "terrorism", "critical", "Mount Lebanon", "Jounieh Port", -0.91, 85, ["Jounieh", "port"], ["package", "security"], "army"),
        ("manual", "Respiratory illness cluster in Sidon clinic", "Local clinic has reported a rapid increase in respiratory cases.", "health", "medium", "South Lebanon", "Sidon", -0.42, 56, ["Sidon"], ["clinic", "health"], "manual"),
    ]
    for index, sample in enumerate(original, start=1):
        source_key, title, description, category, severity, region, location_name, sentiment, risk, entities, keywords, src_key = sample
        lat, lng = REGION_COORDINATES[region]
        created_at = now - timedelta(minutes=index * 9)
        incidents.append(IncidentRecord(
            id=f"incident-{index}",
            source=source_key,  # type: ignore[arg-type]
            source_id=f"seed-{index}",
            title=title, description=description,
            raw_text=description,
            category=category,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            location=IncidentLocation(lat=lat, lng=lng),
            location_name=location_name, region=region,
            sentiment_score=sentiment, risk_score=risk,
            entities=entities, keywords=keywords,
            status="analyzed" if severity != "critical" else "escalated",
            source_info=SOURCES[src_key],
            source_url=SOURCES[src_key].url,
            created_at=created_at, updated_at=created_at,
        ))

    # --- Generate 500 synthetic incidents spread over the last 30 days ---
    target_total = 505
    for i in range(len(incidents) + 1, target_total + 1):
        region = _RNG.choice(regions)
        category = _RNG.choice(categories)
        severity = _pick_severity()

        templates = _TEMPLATES[category]
        title_tmpl, desc_tmpl, keywords, raw_entities = _RNG.choice(templates)
        location = _RNG.choice(REGION_LOCATIONS[region])

        title = _format_template(title_tmpl, location, region)
        description = _format_template(desc_tmpl, location, region)
        entities = [_format_template(e, location, region) for e in raw_entities]

        base_lat, base_lng = REGION_COORDINATES[region]
        lat, lng = _jitter_coords(base_lat, base_lng)

        risk_lo, risk_hi = _SEVERITY_RISK[severity]
        risk_score = round(_RNG.uniform(risk_lo, risk_hi), 1)

        sent_lo, sent_hi = _SEVERITY_SENTIMENT[severity]
        sentiment_score = round(_RNG.uniform(sent_lo, sent_hi), 3)

        # Spread over 30 days with slightly more recent events
        # Use exponential distribution toward recent
        max_hours = 30 * 24
        hours_ago = round(_RNG.expovariate(1 / (max_hours / 4)))
        hours_ago = min(hours_ago, max_hours)
        created_at = now - timedelta(hours=hours_ago, minutes=_RNG.randint(0, 59))

        source_pool = _SOURCE_POOL_BY_CATEGORY.get(category, ["nna", "lbci", "manual"])
        source_key = _RNG.choice(source_pool)
        source_info = SOURCES[source_key]

        status_choices = _STATUS_BY_SEVERITY[severity]
        status = _RNG.choice(status_choices)

        incidents.append(IncidentRecord(
            id=f"incident-{i}",
            source="news",  # type: ignore[arg-type]
            source_id=f"seed-gen-{i}",
            title=title,
            description=description,
            raw_text=description,
            category=category,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            location=IncidentLocation(lat=lat, lng=lng),
            location_name=location,
            region=region,
            sentiment_score=sentiment_score,
            risk_score=risk_score,
            entities=entities,
            keywords=keywords,
            status=status,  # type: ignore[arg-type]
            source_info=source_info,
            source_url=source_info.url,
            created_at=created_at,
            updated_at=created_at,
        ))

    # Sort by created_at desc (most recent first)
    incidents.sort(key=lambda x: x.created_at, reverse=True)
    return incidents


def build_seed_risk_scores() -> list[RiskScoreRecord]:
    now = datetime.now(UTC)
    rows = [
        ("Beirut", 78, 82, 75, 80, 63, 70, 0.88),
        ("North Lebanon", 72, 75, 68, 77, 58, 61, 0.82),
        ("South Lebanon", 54, 49, 44, 59, 42, 48, 0.76),
        ("Mount Lebanon", 66, 64, 58, 69, 52, 60, 0.80),
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
        AlertRecord(
            id="alert-south-conflict",
            risk_score_id=risk_lookup["South Lebanon"],
            incident_id="incident-3",
            alert_type="escalation",
            severity="critical",
            title="Armed conflict risk elevated in South Lebanon",
            message="Multiple conflict-related incidents detected in South Lebanon over the past 6 hours.",
            recommendation="Alert all field units, increase patrol frequency, and brief municipal leaders.",
            region="South Lebanon",
            linked_incidents=["incident-3"],
            created_at=now - timedelta(minutes=35),
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
