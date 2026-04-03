from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    page: int
    per_page: int
    total: int
