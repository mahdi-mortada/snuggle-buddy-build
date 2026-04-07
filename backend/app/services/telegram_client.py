from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
import re

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from telethon import TelegramClient
    from telethon.errors import ChannelPrivateError, RPCError, UsernameInvalidError, UsernameNotOccupiedError
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel

    TELETHON_AVAILABLE = True
except ImportError:  # pragma: no cover
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


class TelegramClientService:
    @asynccontextmanager
    async def client(self):
        settings = get_settings()
        if not TELETHON_AVAILABLE:
            raise TelegramValidationError(
                "Telegram validation is unavailable because Telethon is not installed.",
                reason="telegram_unavailable",
                status_code=503,
            )
        if settings.telegram_api_id <= 0 or not settings.telegram_api_hash.strip() or not settings.telegram_session_string.strip():
            raise TelegramValidationError(
                "Telegram validation is not configured.",
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
                    "Telegram validation session is not authorized.",
                    reason="telegram_unavailable",
                    status_code=503,
                )
            yield client
        finally:
            await client.disconnect()

    async def resolve_public_channel(self, username: str) -> TelegramEntityResult:
        normalized_username = username.strip().lstrip("@").lower()
        if not TELEGRAM_IDENTIFIER_PATTERN.fullmatch(normalized_username):
            raise TelegramValidationError(
                "Invalid format",
                reason="invalid_format",
            )

        try:
            async with self.client() as client:
                entity = await client.get_entity(normalized_username)

                if not isinstance(entity, Channel):
                    raise TelegramValidationError(
                        "Not a valid channel",
                        reason="not_a_channel",
                    )
                if not bool(getattr(entity, "broadcast", False)):
                    raise TelegramValidationError(
                        "Not a valid channel",
                        reason="not_a_channel",
                    )

                resolved_username = str(getattr(entity, "username", "") or "").strip().lstrip("@").lower()
                if not resolved_username:
                    raise TelegramValidationError(
                        "Channel is private or inaccessible",
                        reason="private_inaccessible",
                    )

                try:
                    await client.get_messages(entity, limit=1)
                except Exception as exc:
                    raise TelegramValidationError(
                        "Channel not readable",
                        reason="fetch_failed",
                    ) from exc
        except UsernameInvalidError as exc:
            raise TelegramValidationError("Invalid format", reason="invalid_format") from exc
        except UsernameNotOccupiedError as exc:
            raise TelegramValidationError("Channel does not exist", reason="not_found") from exc
        except ChannelPrivateError as exc:
            raise TelegramValidationError(
                "Channel is private or inaccessible",
                reason="private_inaccessible",
            ) from exc
        except TelegramValidationError:
            raise
        except ValueError as exc:
            raise TelegramValidationError("Channel does not exist", reason="not_found") from exc
        except RPCError as exc:
            logger.warning("Telegram RPC validation failed for @%s: %s", normalized_username, exc)
            raise TelegramValidationError(
                "Telegram validation failed. Try again in a moment.",
                reason="telegram_unavailable",
                status_code=503,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected Telegram validation failure for @%s", normalized_username)
            raise TelegramValidationError(
                "Telegram validation failed. Try again in a moment.",
                reason="telegram_unavailable",
                status_code=503,
            ) from exc

        telegram_id = getattr(entity, "id", None)
        if telegram_id is None:
            raise TelegramValidationError(
                "Channel is private or inaccessible",
                reason="private_inaccessible",
            )

        title = str(getattr(entity, "title", "") or resolved_username).strip() or resolved_username
        return TelegramEntityResult(
            title=title,
            username=resolved_username,
            telegram_id=int(telegram_id),
        )


telegram_client_service = TelegramClientService()
