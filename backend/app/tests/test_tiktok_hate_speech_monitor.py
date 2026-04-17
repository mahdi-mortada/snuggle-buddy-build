from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.hate_speech import get_post_replies, list_all_posts
from app.services.hate_speech_detector import HateSpeechResult, hate_speech_detector
from app.services.social_monitor import SocialMonitorService, SocialPost, social_monitor_service
from app.services.tiktok_scraper import TikTokScraperService, tiktok_scraper_service
from app.services.x_scraper import ScrapedPost, x_scraper_service


def test_tiktok_scraper_parses_profile_payload() -> None:
    service = TikTokScraperService()
    payload = """
    <html>
      <body>
        <script id="SIGI_STATE" type="application/json">
          {
            "ItemModule": {
              "73992220001234": {
                "id": "73992220001234",
                "desc": "Lebanon update #Beirut #Safety",
                "createTime": "1713163200",
                "author": "newsdesk",
                "authorId": "user-123",
                "stats": {
                  "diggCount": 120,
                  "shareCount": 7,
                  "commentCount": 21,
                  "collectCount": 5
                },
                "textExtra": [
                  { "hashtagName": "Beirut" },
                  { "hashtagName": "LebanonNow" }
                ]
              }
            }
          }
        </script>
      </body>
    </html>
    """

    posts = service._parse_posts_from_html(payload, fallback_handle="newsdesk", limit=5)
    assert len(posts) == 1

    post = posts[0]
    assert post.platform == "tiktok"
    assert post.author_handle == "newsdesk"
    assert post.post_id == "73992220001234"
    assert post.content == "Lebanon update #Beirut #Safety"
    assert post.source_url.endswith("/@newsdesk/video/73992220001234")
    assert set(post.hashtags) == {"beirut", "lebanonnow", "safety"}
    assert post.like_count == 120
    assert post.retweet_count == 7
    assert post.reply_count == 21
    assert post.quote_count == 5


@pytest.mark.asyncio
async def test_social_monitor_scan_merges_tiktok_and_x(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SocialMonitorService()
    captured_inputs: list[str] = []

    x_post = ScrapedPost(
        post_id="x-100",
        platform="x",
        author_id="x-author-1",
        author_handle="x_news",
        content="Breaking update from X",
        lang="en",
        like_count=5,
        retweet_count=2,
        reply_count=1,
        quote_count=0,
        posted_at=datetime(2026, 4, 15, 8, 0, tzinfo=UTC),
        source_url="https://x.com/x_news/status/x-100",
        hashtags=["Lebanon"],
    )
    tiktok_post = ScrapedPost(
        post_id="tt-200",
        platform="tiktok",
        author_id="tt-author-1",
        author_handle="tt_news",
        content="TikTok caption on Lebanon",
        lang="en",
        like_count=40,
        retweet_count=4,
        reply_count=7,
        quote_count=3,
        posted_at=datetime(2026, 4, 15, 8, 30, tzinfo=UTC),
        source_url="https://www.tiktok.com/@tt_news/video/tt-200",
        hashtags=["FYP", "LebanonNow"],
    )

    async def fake_scrape_trending(*_args, **_kwargs) -> list[ScrapedPost]:
        return [x_post]

    async def fake_scrape_timelines(*_args, **_kwargs) -> list[ScrapedPost]:
        return []

    async def fake_scrape_queries(*_args, **_kwargs) -> list[ScrapedPost]:
        return []

    async def fake_scrape_tiktok(*_args, **_kwargs) -> list[ScrapedPost]:
        return [tiktok_post]

    async def fake_analyze(text: str) -> HateSpeechResult:
        captured_inputs.append(text)
        return HateSpeechResult(
            text=text,
            language="en",
            hate_score=62.0,
            category="sectarian",
            is_flagged=True,
            keyword_matches=["keyword"],
            model_confidence=0.9,
        )

    monkeypatch.setattr(x_scraper_service, "scrape_trending", fake_scrape_trending)
    monkeypatch.setattr(x_scraper_service, "scrape_media_timelines", fake_scrape_timelines)
    monkeypatch.setattr(x_scraper_service, "scrape_queries", fake_scrape_queries)
    monkeypatch.setattr(tiktok_scraper_service, "scrape_monitored_accounts", fake_scrape_tiktok)
    monkeypatch.setattr(hate_speech_detector, "analyze", fake_analyze)

    summary = await service.run_scan()

    assert summary["scraped"] == 2
    assert summary["analyzed"] == 2
    assert "x:x-100" in service._posts
    assert "tiktok:tt-200" in service._posts
    assert any("TikTok caption on Lebanon" in text and "#FYP" in text for text in captured_inputs)


@pytest.mark.asyncio
async def test_replies_endpoint_rejects_non_x_platform() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_post_replies(post_id="tiktok:123", limit=10, _user=None)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 400
    assert "X posts in Phase 1" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_all_posts_endpoint_returns_tiktok_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    sample_post = SocialPost(
        id="tiktok:abc123",
        platform="tiktok",
        author_handle="tt_monitor",
        author_id="tt-author",
        author_age_days=None,
        content="TikTok sample caption",
        language="en",
        hate_score=55.0,
        category="anti_refugee",
        is_flagged=True,
        keyword_matches=["sample"],
        model_confidence=0.8,
        like_count=10,
        retweet_count=1,
        reply_count=2,
        quote_count=0,
        engagement_total=13,
        posted_at=datetime(2026, 4, 15, 9, 0, tzinfo=UTC),
        scraped_at=datetime(2026, 4, 15, 9, 5, tzinfo=UTC),
        source_url="https://www.tiktok.com/@tt_monitor/video/abc123",
        hashtags=["beirut"],
        reviewed=False,
        review_action="",
    )

    monkeypatch.setattr(social_monitor_service, "list_all", lambda limit, hours: [sample_post])
    response = await list_all_posts(hours=24, limit=50, _user=None)  # type: ignore[arg-type]

    assert response.data is not None
    assert len(response.data) == 1
    assert response.data[0].platform == "tiktok"
    assert response.data[0].id == "tiktok:abc123"
