from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re

from app.models.source import SourceRecord, build_source_id
from app.services.local_store import LocalStoreConflictError, local_store
from app.services.system_event_logger import log_system_event
from app.services.telegram_client import TelegramValidationError, telegram_client_service

MAX_CUSTOM_SOURCES = 20
TELEGRAM_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


class SourceRegistryError(Exception):
    def __init__(self, message: str, *, reason: str = "invalid_request", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.status_code = status_code


@dataclass(slots=True)
class TelegramValidationResult:
    name: str
    username: str
    telegram_id: int


class SourceRegistryService:
    def list_sources(self) -> list[SourceRecord]:
        return sorted(
            local_store.list_sources(),
            key=lambda source: (not source.is_active, source.is_custom, source.name.lower(), source.username.lower()),
        )

    def list_active_sources(self, source_type: str | None = None) -> list[SourceRecord]:
        sources = [source for source in self.list_sources() if source.is_active]
        if source_type is not None:
            sources = [source for source in sources if source.source_type == source_type]
        return sources

    async def create_source(self, *, source_type: str, raw_input: str, name: str | None = None) -> SourceRecord:
        _ = name
        normalized_type = source_type.strip().lower() or "telegram"
        normalized_input = raw_input.strip()
        resolved_username: str | None = None
        resolved_telegram_id: int | None = None
        try:
            if normalized_type != "telegram":
                raise SourceRegistryError(
                    "Only Telegram sources can be added right now.",
                    reason="invalid_source_type",
                )

            username = self.extract_username(normalized_input)
            self._log_validation_start(normalized_input, username)
            validation = await self.validate_telegram_source(username)
            resolved_username = validation.username
            resolved_telegram_id = validation.telegram_id
            self._log_validation_success(validation.username, validation.telegram_id)
            self._ensure_not_duplicate(telegram_id=validation.telegram_id)

            existing_inactive_source = self._find_inactive_source_by_telegram_id(validation.telegram_id)
            if existing_inactive_source is not None:
                reactivated = local_store.update_source(
                    existing_inactive_source.id,
                    {
                        "source_type": "telegram",
                        "name": validation.name,
                        "username": validation.username,
                        "telegram_id": validation.telegram_id,
                        "is_active": True,
                        "is_custom": True,
                    },
                )
                self._log_add_success(reactivated, reason="reactivated")
                return reactivated

            self._ensure_custom_limit()

            source = SourceRecord(
                id=build_source_id("telegram", validation.telegram_id),
                source_type="telegram",
                name=validation.name,
                username=validation.username,
                telegram_id=validation.telegram_id,
                is_active=True,
                is_custom=True,
                created_at=datetime.now(UTC),
            )
            try:
                created = local_store.create_source(source)
            except LocalStoreConflictError as exc:
                self._log_duplicate_blocked(
                    validation.username,
                    validation.telegram_id,
                    reason="active_telegram_id",
                )
                raise SourceRegistryError("Channel already added", reason="duplicate") from exc
            self._log_add_success(created, reason="created")
            return created
        except SourceRegistryError as exc:
            if exc.reason in {"invalid_format", "not_found", "private_inaccessible", "not_a_channel", "fetch_failed", "telegram_unavailable"}:
                self._log_validation_failure(exc.reason)
            self._log_add_failure(normalized_input, exc.reason, username=resolved_username, telegram_id=resolved_telegram_id)
            raise
        except Exception as exc:
            self._log_validation_failure("unexpected_error", level="ERROR")
            self._log_add_failure(
                normalized_input,
                "unexpected_error",
                level="ERROR",
                username=resolved_username,
                telegram_id=resolved_telegram_id,
            )
            raise SourceRegistryError(
                "Telegram validation failed. Try again in a moment.",
                reason="unexpected_error",
                status_code=503,
            ) from exc

    def update_source(self, source_id: str, *, is_active: bool) -> SourceRecord:
        try:
            return local_store.update_source(source_id, {"is_active": is_active})
        except KeyError as exc:
            raise SourceRegistryError("Source not found.", reason="not_found", status_code=404) from exc

    def delete_source(self, source_id: str) -> SourceRecord:
        try:
            deleted = local_store.delete_source(source_id)
        except KeyError as exc:
            raise SourceRegistryError("Source not found.", reason="not_found", status_code=404) from exc
        self._log_delete_success(deleted)
        return deleted

    def extract_username(self, raw_input: str) -> str:
        value = raw_input.strip()
        if not value:
            raise SourceRegistryError(
                "Invalid format",
                reason="invalid_format",
            )

        identifier = (
            value
            .replace("https://t.me/s/", "")
            .replace("http://t.me/s/", "")
            .replace("https://www.t.me/s/", "")
            .replace("http://www.t.me/s/", "")
            .replace("https://t.me/", "")
            .replace("http://t.me/", "")
            .replace("https://www.t.me/", "")
            .replace("http://www.t.me/", "")
            .replace("t.me/s/", "")
            .replace("t.me/", "")
            .replace("@", "")
            .strip()
            .removesuffix("/")
        )

        normalized = re.sub(r"[^a-z0-9_]+", "", identifier.lower())
        if not TELEGRAM_IDENTIFIER_PATTERN.fullmatch(normalized):
            raise SourceRegistryError(
                "Invalid format",
                reason="invalid_format",
            )
        return normalized

    def normalize_telegram_input(self, raw_input: str) -> str:
        return self.extract_username(raw_input)

    async def validate_telegram_source(self, identifier: str) -> TelegramValidationResult:
        try:
            resolved = await telegram_client_service.resolve_public_channel(identifier)
        except TelegramValidationError as exc:
            raise SourceRegistryError(
                exc.message,
                reason=exc.reason,
                status_code=exc.status_code,
            ) from exc

        return TelegramValidationResult(
            name=resolved.title,
            username=resolved.username,
            telegram_id=resolved.telegram_id,
        )

    def _ensure_not_duplicate(self, *, telegram_id: int) -> None:
        for source in local_store.list_sources():
            if not source.is_active:
                continue
            if source.telegram_id is not None and source.telegram_id == telegram_id:
                self._log_duplicate_blocked(source.username, telegram_id, reason="active_telegram_id")
                raise SourceRegistryError("Channel already added", reason="duplicate")

    def _ensure_custom_limit(self) -> None:
        custom_count = sum(1 for source in local_store.list_sources() if source.is_custom and source.is_active)
        if custom_count >= MAX_CUSTOM_SOURCES:
            raise SourceRegistryError(
                f"Custom Telegram source limit reached ({MAX_CUSTOM_SOURCES}).",
                reason="limit_reached",
            )

    def _find_inactive_source_by_telegram_id(self, telegram_id: int) -> SourceRecord | None:
        existing = local_store.get_source_by_telegram_id(telegram_id)
        if existing is None or existing.is_active:
            return None
        return existing

    def _log_add_success(self, source: SourceRecord, *, reason: str) -> None:
        log_system_event(
            "INFO",
            "SOURCE_ADDED",
            {
                "name": source.name,
                "username": source.username,
                "telegram_id": source.telegram_id,
                "source_type": source.source_type,
                "reason": reason,
            },
        )

    def _log_add_failure(
        self,
        raw_input: str,
        reason: str,
        *,
        level: str = "WARN",
        username: str | None = None,
        telegram_id: int | None = None,
    ) -> None:
        log_system_event(
            level,
            "SOURCE_ADD_FAILED",
            {
                "input_value": raw_input,
                "username": username,
                "telegram_id": telegram_id,
                "reason": reason,
            },
        )

    def _log_duplicate_blocked(self, username: str, telegram_id: int, *, reason: str) -> None:
        log_system_event(
            "WARN",
            "DUPLICATE_BLOCKED",
            {
                "username": username,
                "telegram_id": telegram_id,
                "reason": reason,
            },
        )

    def _log_delete_success(self, source: SourceRecord) -> None:
        log_system_event(
            "INFO",
            "SOURCE_DELETED",
            {
                "username": source.username,
                "telegram_id": source.telegram_id,
                "reason": "deleted",
            },
        )

    def _log_validation_start(self, raw_input: str, username: str) -> None:
        log_system_event(
            "INFO",
            "VALIDATION_START",
            {
                "input_value": raw_input,
                "extracted_username": username,
            },
        )

    def _log_validation_success(self, username: str, telegram_id: int) -> None:
        log_system_event(
            "INFO",
            "VALIDATION_SUCCESS",
            {
                "username": username,
                "telegram_id": telegram_id,
            },
        )

    def _log_validation_failure(self, reason: str, *, level: str = "WARN") -> None:
        log_system_event(
            level,
            "VALIDATION_FAILED",
            {
                "reason": reason,
            },
        )


source_registry_service = SourceRegistryService()
