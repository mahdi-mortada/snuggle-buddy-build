"""TikTok scraper for hate-speech monitoring (Phase 1).

Fetches public profile pages for curated accounts and extracts recent post
metadata needed by the existing social monitor pipeline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import get_settings
from app.services.x_scraper import ScrapedPost

logger = logging.getLogger(__name__)

_HASHTAG_PATTERN = re.compile(r"#([\w\u0600-\u06ff]+)")


class TikTokScraperService:
    def _safe_int(self, raw_value: Any) -> int:
        try:
            return int(float(raw_value))
        except (TypeError, ValueError):
            return 0

    def _normalize_handle(self, raw_value: str) -> str:
        value = str(raw_value).strip().lstrip("@")
        if not value:
            return ""
        return re.sub(r"[^A-Za-z0-9._]+", "", value).strip(".")

    def _parse_monitored_accounts(self, raw_json: str | None) -> list[str]:
        if not raw_json or not raw_json.strip():
            return []

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.warning("TikTok monitored accounts JSON is invalid: %s", exc)
            return []

        handles: list[str] = []
        if isinstance(payload, list):
            for item in payload:
                raw_handle = ""
                if isinstance(item, str):
                    raw_handle = item
                elif isinstance(item, dict):
                    raw_handle = str(
                        item.get("handle")
                        or item.get("username")
                        or item.get("account")
                        or ""
                    )
                handle = self._normalize_handle(raw_handle)
                if handle and handle not in handles:
                    handles.append(handle)
        else:
            logger.warning("TikTok monitored accounts JSON must be a list")

        return handles

    def _extract_script_json(self, html_text: str, script_id: str) -> dict[str, Any] | None:
        pattern = re.compile(
            rf'<script[^>]+id=["\']{re.escape(script_id)}["\'][^>]*>(?P<payload>.*?)</script>',
            flags=re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(html_text)
        if not match:
            return None
        payload = match.group("payload").strip()
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            logger.debug("Could not parse %s payload as JSON", script_id)
            return None

    def _looks_like_post(self, node: dict[str, Any]) -> bool:
        if "id" not in node:
            return False
        if "desc" in node or "description" in node:
            return True
        if any(
            key in node
            for key in ("textExtra", "video", "stats", "author", "authorId", "shareMeta", "itemInfos")
        ):
            return True
        if "createTime" in node and any(key in node for key in ("video", "author", "authorId", "music")):
            return True
        stats = node.get("stats")
        if isinstance(stats, dict) and any(
            k in stats for k in ("diggCount", "commentCount", "shareCount", "collectCount")
        ):
            return True
        return False

    def _iter_post_candidates(self, node: Any):  # type: ignore[no-untyped-def]
        if isinstance(node, dict):
            item_struct = node.get("itemStruct")
            if isinstance(item_struct, dict):
                yield item_struct
            if self._looks_like_post(node):
                yield node
            for value in node.values():
                yield from self._iter_post_candidates(value)
        elif isinstance(node, list):
            for item in node:
                yield from self._iter_post_candidates(item)

    def _parse_epoch(self, raw_value: Any) -> datetime:
        value = str(raw_value or "").strip()
        if not value:
            return datetime.now(UTC)
        try:
            return datetime.fromtimestamp(int(float(value)), tz=UTC)
        except (TypeError, ValueError, OSError):
            return datetime.now(UTC)

    def _extract_hashtags(self, caption: str, candidate: dict[str, Any]) -> list[str]:
        tags: list[str] = []
        text_extra = candidate.get("textExtra")
        if isinstance(text_extra, list):
            for item in text_extra:
                if not isinstance(item, dict):
                    continue
                raw_name = (
                    item.get("hashtagName")
                    or item.get("tagName")
                    or item.get("hashtag")
                    or ""
                )
                tag = str(raw_name).strip().lstrip("#").lower()
                if tag and tag not in tags:
                    tags.append(tag)

        for match in _HASHTAG_PATTERN.findall(caption):
            tag = match.strip().lstrip("#").lower()
            if tag and tag not in tags:
                tags.append(tag)

        return tags

    def _extract_caption(self, candidate: dict[str, Any]) -> str:
        # TikTok payloads vary by script/root; try a few common caption fields.
        text_candidates: list[Any] = [
            candidate.get("desc"),
            candidate.get("description"),
            candidate.get("title"),
            candidate.get("text"),
            candidate.get("caption"),
        ]

        share_meta = candidate.get("shareMeta")
        if isinstance(share_meta, dict):
            text_candidates.extend([share_meta.get("desc"), share_meta.get("title")])

        item_infos = candidate.get("itemInfos")
        if isinstance(item_infos, dict):
            text_candidates.extend(
                [
                    item_infos.get("text"),
                    item_infos.get("desc"),
                    item_infos.get("description"),
                ]
            )

        for raw_value in text_candidates:
            text = str(raw_value or "").strip()
            if text:
                return text
        return ""

    def _post_quality(self, post: ScrapedPost) -> tuple[int, int, int]:
        return (
            1 if post.content.strip() else 0,
            len(post.hashtags),
            post.engagement_total,
        )

    def _post_from_candidate(self, candidate: dict[str, Any], fallback_handle: str) -> ScrapedPost | None:
        post_id = str(candidate.get("id", "")).strip()
        if not post_id:
            return None

        caption = self._extract_caption(candidate)

        author_field = candidate.get("author")
        if isinstance(author_field, dict):
            author_handle = str(
                author_field.get("uniqueId")
                or author_field.get("nickname")
                or author_field.get("username")
                or fallback_handle
            ).strip()
        elif isinstance(author_field, str):
            author_handle = author_field.strip()
        else:
            author_handle = fallback_handle
        author_handle = self._normalize_handle(author_handle) or fallback_handle

        stats = candidate.get("stats")
        if not isinstance(stats, dict):
            stats = {}

        hashtags = self._extract_hashtags(caption, candidate)
        posted_at = self._parse_epoch(candidate.get("createTime"))
        like_count = self._safe_int(stats.get("diggCount", 0) or 0)
        share_count = self._safe_int(stats.get("shareCount", 0) or 0)
        comment_count = self._safe_int(stats.get("commentCount", 0) or 0)
        save_count = self._safe_int(stats.get("collectCount", 0) or 0)

        return ScrapedPost(
            post_id=post_id,
            platform="tiktok",
            author_id=str(candidate.get("authorId") or ""),
            author_handle=author_handle,
            content=caption,
            lang="",
            like_count=like_count,
            retweet_count=share_count,
            reply_count=comment_count,
            quote_count=save_count,
            posted_at=posted_at,
            source_url=f"https://www.tiktok.com/@{author_handle}/video/{post_id}",
            hashtags=hashtags,
        )

    def _parse_posts_from_payload(
        self,
        payload: dict[str, Any],
        *,
        fallback_handle: str,
        limit: int,
    ) -> list[ScrapedPost]:
        posts_by_id: dict[str, ScrapedPost] = {}
        for candidate in self._iter_post_candidates(payload):
            if not isinstance(candidate, dict):
                continue
            post = self._post_from_candidate(candidate, fallback_handle)
            if post is None:
                continue
            existing = posts_by_id.get(post.post_id)
            if existing is None or self._post_quality(post) > self._post_quality(existing):
                posts_by_id[post.post_id] = post

        posts = list(posts_by_id.values())
        posts.sort(key=lambda p: p.posted_at, reverse=True)
        return posts[:limit]

    def _parse_posts_from_html(
        self,
        html_text: str,
        *,
        fallback_handle: str,
        limit: int,
    ) -> list[ScrapedPost]:
        sources: list[dict[str, Any]] = []
        for script_id in ("__UNIVERSAL_DATA_FOR_REHYDRATION__", "SIGI_STATE", "__NEXT_DATA__"):
            payload = self._extract_script_json(html_text, script_id)
            if payload is None:
                continue
            default_scope = payload.get("__DEFAULT_SCOPE__")
            if isinstance(default_scope, dict):
                sources.append(default_scope)
            sources.append(payload)

        for source in sources:
            posts = self._parse_posts_from_payload(source, fallback_handle=fallback_handle, limit=limit)
            if posts:
                posts.sort(key=lambda p: p.posted_at, reverse=True)
                return posts[:limit]
        return []

    def _extract_sec_uid_from_html(self, html_text: str) -> str:
        payload = self._extract_script_json(html_text, "__UNIVERSAL_DATA_FOR_REHYDRATION__")
        if not isinstance(payload, dict):
            return ""
        scope = payload.get("__DEFAULT_SCOPE__")
        if not isinstance(scope, dict):
            return ""
        user_detail = scope.get("webapp.user-detail")
        if not isinstance(user_detail, dict):
            return ""
        user_info = user_detail.get("userInfo")
        if not isinstance(user_info, dict):
            return ""
        user = user_info.get("user")
        if not isinstance(user, dict):
            return ""
        return str(user.get("secUid") or "").strip()

    def _parse_posts_from_item_list_response(
        self,
        payload: dict[str, Any],
        *,
        fallback_handle: str,
        limit: int,
    ) -> list[ScrapedPost]:
        item_list = payload.get("itemList")
        if not isinstance(item_list, list) or not item_list:
            return []

        posts_by_id: dict[str, ScrapedPost] = {}
        for item in item_list:
            if not isinstance(item, dict):
                continue
            post = self._post_from_candidate(item, fallback_handle)
            if post is None:
                continue
            existing = posts_by_id.get(post.post_id)
            if existing is None or self._post_quality(post) > self._post_quality(existing):
                posts_by_id[post.post_id] = post

        posts = list(posts_by_id.values())
        posts.sort(key=lambda p: p.posted_at, reverse=True)
        return posts[:limit]

    async def _fetch_posts_from_public_item_list_api(
        self,
        client: httpx.AsyncClient,
        *,
        html_text: str,
        fallback_handle: str,
        limit: int,
    ) -> list[ScrapedPost]:
        sec_uid = self._extract_sec_uid_from_html(html_text)
        if not sec_uid:
            return []

        params = {
            "aid": "1988",
            "count": str(max(1, min(limit, 35))),
            "cursor": "0",
            "secUid": sec_uid,
            "sourceType": "8",
            "needPinnedItemIds": "true",
        }

        try:
            response = await client.get("https://www.tiktok.com/api/post/item_list/", params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.info("TikTok fallback item_list request failed for @%s: %s", fallback_handle, exc)
            return []

        raw_text = response.text.strip()
        if not raw_text:
            return []
        try:
            payload = response.json()
        except ValueError:
            logger.info("TikTok fallback item_list returned non-JSON for @%s", fallback_handle)
            return []
        if not isinstance(payload, dict):
            return []

        return self._parse_posts_from_item_list_response(
            payload,
            fallback_handle=fallback_handle,
            limit=limit,
        )

    async def scrape_monitored_accounts(self, limit_per_account: int | None = None) -> list[ScrapedPost]:
        settings = get_settings()
        if not settings.tiktok_monitor_enabled:
            return []

        handles = self._parse_monitored_accounts(settings.tiktok_monitored_accounts_json)
        if not handles:
            return []

        safe_limit = max(1, min(limit_per_account or settings.tiktok_posts_per_account, 60))
        all_posts: list[ScrapedPost] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(
            timeout=settings.tiktok_request_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            for handle in handles:
                url = f"https://www.tiktok.com/@{handle}"
                response: httpx.Response | None = None
                last_error: Exception | None = None
                for attempt in range(2):
                    try:
                        response = await client.get(url)
                        response.raise_for_status()
                        last_error = None
                        break
                    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                        last_error = exc
                        if attempt == 0:
                            await asyncio.sleep(0.8)
                            continue
                        break
                    except httpx.HTTPError as exc:
                        last_error = exc
                        break

                if response is None:
                    logger.warning("TikTok scrape failed for @%s: %s", handle, last_error)
                    continue

                posts = self._parse_posts_from_html(
                    response.text,
                    fallback_handle=handle,
                    limit=safe_limit,
                )
                if not posts:
                    posts = await self._fetch_posts_from_public_item_list_api(
                        client,
                        html_text=response.text,
                        fallback_handle=handle,
                        limit=safe_limit,
                    )
                if posts:
                    logger.info("TikTok scrape: fetched %d posts from @%s", len(posts), handle)
                else:
                    logger.info("TikTok scrape: no parsable posts found for @%s", handle)
                for post in posts:
                    dedup_key = f"{post.platform}:{post.post_id}"
                    if dedup_key in seen_ids:
                        continue
                    seen_ids.add(dedup_key)
                    all_posts.append(post)
                await asyncio.sleep(0.6)

        return all_posts


tiktok_scraper_service = TikTokScraperService()
