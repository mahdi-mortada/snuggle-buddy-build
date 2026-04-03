from datetime import UTC, datetime

from app.services.live_news import LiveNewsService, NewsEntry


def test_live_news_uses_precise_place_coordinates() -> None:
    service = LiveNewsService()
    entries = [
        NewsEntry(
            title="Security alert near Jounieh port",
            description="Authorities closed nearby roads in Jounieh after a suspicious package report.",
            link="https://example.com/jounieh-alert",
            source_name="LBCI",
            published_at=datetime.now(UTC),
        )
    ]

    incidents = service._build_incidents(entries, hours_window=24)

    assert len(incidents) == 1
    incident = incidents[0]
    assert incident.region == "Mount Lebanon"
    assert incident.location_name == "Jounieh"
    assert abs(incident.location.lat - 33.9741506) < 0.01
    assert abs(incident.location.lng - 35.6200633) < 0.01
