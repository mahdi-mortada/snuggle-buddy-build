from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.user import UserRecord
from app.schemas.auth import LoginRequest, TokenOut, UserCreateRequest, UserOut
from app.schemas.common import ApiResponse
from app.services.auth_service import create_access_token, ensure_admin, get_current_user_email, hash_password, verify_password
from app.services.local_store import local_store

router = APIRouter()


def _current_user(email: str = Depends(get_current_user_email)) -> UserRecord:
    user = local_store.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/login", response_model=ApiResponse[TokenOut])
async def login(payload: LoginRequest) -> ApiResponse[TokenOut]:
    user = local_store.get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(user.email)
    return ApiResponse(data=TokenOut(access_token=token, user=UserOut.model_validate(user.model_dump())))


@router.post("/register", response_model=ApiResponse[UserOut])
async def register(payload: UserCreateRequest, current_user: UserRecord = Depends(_current_user)) -> ApiResponse[UserOut]:
    ensure_admin(current_user)
    if local_store.get_user_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    now = datetime.now(UTC)
    user = UserRecord(
        id=str(uuid4()),
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,  # type: ignore[arg-type]
        organization=payload.organization,
        created_at=now,
        updated_at=now,
    )
    local_store.create_user(user)
    return ApiResponse(data=UserOut.model_validate(user.model_dump()))


@router.get("/me", response_model=ApiResponse[UserOut])
async def me(current_user: UserRecord = Depends(_current_user)) -> ApiResponse[UserOut]:
    return ApiResponse(data=UserOut.model_validate(current_user.model_dump()))
