from datetime import UTC, datetime

from app.services.official_feed_filtering import KeywordMatcher, resolve_official_feed_filter_keywords
from app.services.official_feeds import OfficialFeedPost, OfficialFeedService


def _build_post(*, content: str) -> OfficialFeedPost:
    return OfficialFeedPost(
        id="post-1",
        platform="telegram",
        publisher_name="LBCI",
        account_label="LBCI News Wire",
        account_handle="LBCI_NEWS",
        account_url="https://t.me/LBCI_NEWS",
        post_url="https://t.me/LBCI_NEWS/1",
        content=content,
        signal_tags=[],
        source_info={
            "name": "LBCI",
            "type": "tv",
            "credibility": "verified",
            "credibilityScore": 88,
            "logoInitials": "LB",
            "url": "https://t.me/LBCI_NEWS",
            "verifiedBy": [],
        },
        published_at=datetime(2026, 3, 31, 8, 0, tzinfo=UTC),
    )


def test_keyword_matcher_supports_case_insensitive_partial_matches_across_fields() -> None:
    matcher = KeywordMatcher(["Hosp", "beir"])

    result = matcher.match_record(
        {
            "title": "Hospital preparedness updated",
            "description": "Conditions are changing in BEIRUT districts.",
            "content": "",
        }
    )

    assert result.matched_keywords == ["hosp", "beir"]
    assert result.primary_keyword == "hosp"


def test_keyword_config_supports_json_array_and_deduplicates_keywords() -> None:
    keywords = resolve_official_feed_filter_keywords('["Airport", " airport ", "Border"]')

    assert keywords == ["airport", "border"]


def test_blank_keyword_config_keeps_filtering_disabled() -> None:
    assert resolve_official_feed_filter_keywords("") == []


def test_empty_keyword_config_disables_filtering() -> None:
    assert resolve_official_feed_filter_keywords("[]") == []


def test_official_feed_service_filters_posts_and_prioritizes_matches() -> None:
    service = OfficialFeedService()
    matcher = KeywordMatcher(["gov", "air"])
    matching_post = _build_post(content="Government update confirms airport operations remain active. #Urgent")
    ignored_post = _build_post(content="Sports bulletin without any relevant topic.")
    ignored_post.id = "post-2"
    ignored_post.post_url = "https://t.me/LBCI_NEWS/2"

    filtered_posts = service._apply_keyword_filter([matching_post, ignored_post], matcher)

    assert [post.id for post in filtered_posts] == ["post-1"]
    assert filtered_posts[0].matched_keywords == ["gov", "air"]
    assert filtered_posts[0].primary_keyword == "gov"
    assert filtered_posts[0].signal_tags == ["gov", "air", "urgent"]
