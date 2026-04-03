from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


UserRole = Literal["admin", "analyst", "viewer", "isf_officer"]


class UserRecord(BaseModel):
    id: str
    email: EmailStr
    hashed_password: str
    full_name: str
    role: UserRole = "analyst"
    organization: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
