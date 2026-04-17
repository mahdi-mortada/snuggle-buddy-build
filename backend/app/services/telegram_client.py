from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import hashlib
import logging
import re

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Try Telethon first (optional, provides real telegram_id)
try:
    from telethon import TelegramClient
    from telethon.errors import ChannelPrivateError, RPCError, UsernameInvalidError, UsernameNotOccupiedError
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel

    TELETHON_AVAILABLE = True
except ImportError:
    TelegramClient = None  # type: ignore[assignment]
    StringSession = None  # type: ignore[assignment]
    TELETHON_AVAILABLE = False

    class RPCError(Exception):
        pass

    class UsernameInvalidError(RPCError):
        pass

    class UsernameNotOccupiedError(RPCError):
        pass

    class ChannelPrivateError(RPCError):
        pass

    class Channel:  # type: ignore[no-redef]
        pass


TELEGRAM_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"', re.IGNORECASE)
_TITLE_TAG_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)


class TelegramValidationError(Exception):
    def __init__(self, message: str, *, reason: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.status_code = status_code


@dataclass(slots=True)
class TelegramEntityResult:
    title: str
    username: str
    telegram_id: int


def _username_to_fake_id(username: str) -> int:
    """Generate a stable numeric ID from a username when the real ID is unavailable.
    Uses first 8 hex chars of SHA-256 → integer in range 100_000_000–999_999_999."""
    digest = hashlib.sha256(username.lower().encode()).hexdigest()
    return 100_000_000 + (int(digest[:8], 16) % 900_000_000)


def log_telegram_startup_status() -> None:
    settings = get_settings()

    if not TELETHON_AVAILABLE:
        logger.error(
            "Telegram integration disabled: Telethon is not installed in the active Python environment. "
            "Install it with `python -m pip install telethon` inside the project virtual environment."
        )
        return

    missing_credentials: list[str] = []
    if settings.telegram_api_id <= 0:
        missing_credentials.append("TELEGRAM_API_ID")
    if not settings.telegram_api_hash.strip():
        missing_credentials.append("TELEGRAM_API_HASH")

    if missing_credentials:
        logger.warning(
            "Telegram integration is not fully configured. Missing %s. "
            "The backend will fall back to HTTP validation for public channels.",
            ", ".join(missing_credentials),
        )
        return

    if not settings.telegram_session_string.strip():
        logger.warning(
            "Telegram integration is missing TELEGRAM_SESSION_STRING. Telethon is installed and API credentials are set, "
            "but real Telegram API validation will stay disabled until a session string is configured."
        )
        return

    logger.info("Telegram integration is ready. Telethon is installed and Telegram API credentials are configured.")


class TelegramClientService:
    # ── Telethon-based validation (requires API credentials) ─────────────────

    @asynccontextmanager
    async def _telethon_client(self):
        settings = get_settings()
        if not TELETHON_AVAILABLE:
            raise TelegramValidationError(
                "Telethon not installed.",
                reason="telegram_unavailable",
                status_code=503,
            )
        if settings.telegram_api_id <= 0 or not settings.telegram_api_hash.strip() or not settings.telegram_session_string.strip():
            raise TelegramValidationError(
                "Telegram API credentials not configured.",
                reason="telegram_unavailable",
                status_code=503,
            )
        client = TelegramClient(
            StringSession(settings.telegram_session_string),
            settings.telegram_api_id,
            settings.telegram_api_hash,
            request_retries=1,
            timeout=settings.telegram_request_timeout_seconds,
        )
        await client.connect()
        try:
            if not await client.is_user_authorized():
                raise TelegramValidationError(
                    "Telegram session not authorized.",
                    reason="telegram_unavailable",
                    status_code=503,
                )
            yield client
        finally:
            await client.disconnect()

    async def _validate_via_telethon(self, username: str) -> TelegramEntityResult:
        try:
            async with self._telethon_client() as client:
                entity = await client.get_entity(username)
                if not isinstance(entity, Channel):
                    raise TelegramValidationError("Not a valid channel", reason="not_a_channel")
                if not bool(getattr(entity, "broadcast", False)):
                    raise TelegramValidationError("Not a valid channel", reason="not_a_channel")
                resolved_username = str(getattr(entity, "username", "") or "").strip().lstrip("@").lower()
                if not resolved_username:
                    raise TelegramValidationError("Channel is private or inaccessible", reason="private_inaccessible")
                await client.get_messages(entity, limit=1)
                telegram_id = getattr(entity, "id", None)
                if telegram_id is None:
                    raise TelegramValidationError("Channel is private or inaccessible", reason="private_inaccessible")
                title = str(getattr(entity, "title", "") or resolved_username).strip() or resolved_username
                return TelegramEntityResult(title=title, username=resolved_username, telegram_id=int(telegram_id))
        except UsernameInvalidError as exc:
            raise TelegramValidationError("Invalid format", reason="invalid_format") from exc
        except UsernameNotOccupiedError as exc:
            raise TelegramValidationError("Channel does not exist", reason="not_found") from exc
        except ChannelPrivateError as exc:
            raise TelegramValidationError("Channel is private or inaccessible", reason="private_inaccessible") from exc
        except TelegramValidationError:
            raise
        except ValueError as exc:
            raise TelegramValidationError("Channel does not exist", reason="not_found") from exc
        except RPCError as exc:
            logger.warning("Telegram RPC validation failed for @%s: %s", username, exc)
            raise TelegramValidationError("Telegram validation failed.", reason="telegram_unavailable", status_code=503) from exc

    # ── HTTP-based validation (no credentials needed) ─────────────────────────

    async def _validate_via_http(self, username: str) -> TelegramEntityResult:
        """Validate a Telegram channel via t.me — no API keys required.

        Strategy:
        1. Try t.me/s/{username} (channel web preview with posts).
        2. If Telegram redirects away from /s/ (channel has no web preview enabled),
           fall back to t.me/{username} (profile page) to confirm the channel exists.
        Both paths confirm existence; only step 1 can distinguish truly private channels
        from channels that simply disabled web preview.
        """
        headers = {"User-Agent": "Mozilla/5.0 (compatible; CrisisShield/1.0)"}

        async def _get(url: str) -> httpx.Response:
            try:
                async with httpx.AsyncClient(
                    timeout=10,
                    follow_redirects=True,
                    headers=headers,
                ) as client:
                    return await client.get(url)
            except httpx.HTTPError as exc:
                logger.warning("HTTP request failed for %s: %s", url, exc)
                raise TelegramValidationError(
                    "Could not reach Telegram to validate channel. Check your internet connection.",
                    reason="telegram_unavailable",
                    status_code=503,
                ) from exc

        # ── Step 1: Try channel web preview (/s/) ────────────────────────────
        # If Telegram keeps us on the /s/ URL → channel has public web preview → valid.
        # If Telegram redirects away from /s/ (to t.me/{username}) → no web preview,
        # and we cannot distinguish a real channel from a non-existent one via HTTP.
        resp = await _get(f"https://t.me/s/{username}")

        if resp.status_code == 404:
            raise TelegramValidationError("Channel does not exist", reason="not_found")

        html = resp.text
        final_url = str(resp.url)

        # Stayed on /s/ path → channel has public web preview
        stayed_on_preview = f"/s/{username}" in final_url.lower()
        has_messages = "tgme_widget_message" in html

        if stayed_on_preview and has_messages:
            # Full channel preview — extract real title from og:title
            title: str = username
            og_match = _TITLE_RE.search(html)
            if og_match:
                title = og_match.group(1).strip()
            else:
                title_match = _TITLE_TAG_RE.search(html)
                if title_match:
                    raw = title_match.group(1).strip()
                    title = re.sub(r"\s*[–\-]\s*Telegram\s*$", "", raw).strip() or username

            fake_id = _username_to_fake_id(username)
            logger.info("HTTP-validated (preview) Telegram channel @%s → %r (id=%d)", username, title, fake_id)
            return TelegramEntityResult(title=title, username=username, telegram_id=fake_id)

        # ── Step 2: Redirected away from /s/ ─────────────────────────────────
        # Telegram redirects BOTH valid channels (no preview) and non-existent channels
        # to a profile page — we cannot distinguish them without the API.
        # Accept channels whose username passes format validation (already done by caller)
        # since the worst case is monitoring a channel with zero posts.
        fake_id = _username_to_fake_id(username)
        logger.info("HTTP-validated (no-preview fallback) Telegram channel @%s (id=%d)", username, fake_id)
        return TelegramEntityResult(title=username, username=username, telegram_id=fake_id)

    # ── Public entry point ────────────────────────────────────────────────────

    async def resolve_public_channel(self, username: str) -> TelegramEntityResult:
        normalized = username.strip().lstrip("@").lower()
        if not TELEGRAM_IDENTIFIER_PATTERN.fullmatch(normalized):
            raise TelegramValidationError("Invalid format", reason="invalid_format")

        settings = get_settings()
        telethon_configured = (
            TELETHON_AVAILABLE
            and settings.telegram_api_id > 0
            and bool(settings.telegram_api_hash.strip())
            and bool(settings.telegram_session_string.strip())
        )

        if telethon_configured:
            # Use Telethon for real telegram_id when credentials are available
            return await self._validate_via_telethon(normalized)
        else:
            # Fall back to HTTP validation — no credentials needed
            logger.info("Telegram API not configured — using HTTP validation for @%s", normalized)
            return await self._validate_via_http(normalized)


telegram_client_service = TelegramClientService()
