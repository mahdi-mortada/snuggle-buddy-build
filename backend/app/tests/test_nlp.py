"""Tests for NLP pipeline and risk scoring services."""
from __future__ import annotations

import asyncio
import pytest

from app.services.nlp_pipeline import nlp_pipeline
from app.services.risk_scoring import risk_scoring_service
from app.services.seed_data import build_seed_incidents, build_seed_risk_scores


# ---------------------------------------------------------------------------
# NLP Pipeline — unit tests (no external models required)
# ---------------------------------------------------------------------------

class TestNlpPipelineSync:
    """Test NLP pipeline synchronous helpers that don't require heavy models."""

    def test_build_seed_incidents_count(self) -> None:
        incidents = build_seed_incidents()
        assert len(incidents) >= 500, f"Expected 500+ seed incidents, got {len(incidents)}"

    def test_seed_incidents_have_required_fields(self) -> None:
        incidents = build_seed_incidents()
        for inc in incidents[:20]:
            assert inc.id
            assert inc.title
            assert inc.region in [
                "Beirut", "North Lebanon", "South Lebanon", "Mount Lebanon",
                "Bekaa", "Nabatieh", "Akkar", "Baalbek-Hermel",
            ]
            assert inc.severity in ("low", "medium", "high", "critical")
            assert inc.category in (
                "violence", "protest", "natural_disaster", "infrastructure",
                "health", "terrorism", "cyber", "armed_conflict", "other",
            )

    def test_seed_incidents_cover_all_regions(self) -> None:
        incidents = build_seed_incidents()
        regions = {i.region for i in incidents}
        expected = {
            "Beirut", "North Lebanon", "South Lebanon", "Mount Lebanon",
            "Bekaa", "Nabatieh", "Akkar", "Baalbek-Hermel",
        }
        assert regions == expected

    def test_seed_incidents_cover_all_categories(self) -> None:
        incidents = build_seed_incidents()
        categories = {i.category for i in incidents}
        expected = {
            "violence", "protest", "natural_disaster", "infrastructure",
            "health", "terrorism", "cyber", "armed_conflict", "other",
        }
        assert categories == expected

    def test_seed_incidents_risk_scores_in_range(self) -> None:
        incidents = build_seed_incidents()
        for inc in incidents:
            assert 0 <= inc.risk_score <= 100, f"Risk score out of range: {inc.risk_score}"

    def test_seed_incidents_sentiment_in_range(self) -> None:
        incidents = build_seed_incidents()
        for inc in incidents:
            assert -1 <= inc.sentiment_score <= 1, f"Sentiment out of range: {inc.sentiment_score}"

    def test_seed_spread_over_30_days(self) -> None:
        from datetime import datetime, timezone, timedelta
        incidents = build_seed_incidents()
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)
        in_window = sum(1 for i in incidents if i.created_at >= cutoff_30d)
        # At least 90% of incidents should be within the 30-day window
        assert in_window / len(incidents) >= 0.9


class TestRiskScoring:
    """Test risk scoring service with seed data."""

    def test_build_seed_risk_scores(self) -> None:
        risk_scores = build_seed_risk_scores()
        assert len(risk_scores) == 8

    def test_risk_score_fields_valid(self) -> None:
        risk_scores = build_seed_risk_scores()
        for rs in risk_scores:
            assert 0 <= rs.overall_score <= 100
            assert 0 <= rs.sentiment_component <= 100
            assert 0 <= rs.volume_component <= 100
            assert 0 <= rs.keyword_component <= 100
            assert 0 <= rs.behavior_component <= 100
            assert 0 <= rs.geospatial_component <= 100
            assert 0 < rs.confidence <= 1

    def test_risk_scoring_calculate_sync(self) -> None:
        """Risk scoring service should produce a valid score from incidents."""
        incidents = build_seed_incidents()
        beirut_incidents = [i for i in incidents if i.region == "Beirut"][:10]
        if not beirut_incidents:
            return

        score = risk_scoring_service.calculate("Beirut", beirut_incidents)
        assert score is not None
        assert 0 <= score.overall_score <= 100
        assert score.region == "Beirut"

    def test_risk_scoring_empty_incidents_returns_zero(self) -> None:
        score = risk_scoring_service.calculate("Beirut", [])
        assert score.overall_score == 0


# ---------------------------------------------------------------------------
# NLP Pipeline — async integration (with model graceful fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nlp_process_english_text() -> None:
    """NLP pipeline should process English text without raising."""
    result = await nlp_pipeline.process(
        "Gunfire reported near Martyrs' Square in downtown Beirut.",
        metadata={"region": "Beirut"},
    )
    assert isinstance(result, dict)
    assert "sentiment_score" in result
    assert "language" in result
    assert "keywords" in result
    assert -1 <= result["sentiment_score"] <= 1


@pytest.mark.asyncio
async def test_nlp_process_arabic_text() -> None:
    """NLP pipeline should process Arabic text without raising."""
    result = await nlp_pipeline.process(
        "اشتباكات مسلحة في منطقة الضاحية الجنوبية لبيروت",
        metadata={"region": "Beirut"},
    )
    assert isinstance(result, dict)
    assert "language" in result
    assert "sentiment_score" in result


@pytest.mark.asyncio
async def test_nlp_returns_category() -> None:
    """NLP pipeline should classify incident category."""
    result = await nlp_pipeline.process(
        "A major power outage struck the Tripoli industrial district.",
        metadata={"region": "North Lebanon"},
    )
    assert "category" in result
    assert result["category"] in (
        "violence", "protest", "natural_disaster", "infrastructure",
        "health", "terrorism", "cyber", "armed_conflict", "other",
    )


@pytest.mark.asyncio
async def test_nlp_returns_entities() -> None:
    """NLP pipeline should extract named entities."""
    result = await nlp_pipeline.process(
        "Lebanese Army deployed near Baalbek following armed clashes.",
        metadata={"region": "Baalbek-Hermel"},
    )
    assert "entities" in result
    assert isinstance(result["entities"], list)
