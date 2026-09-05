"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from dash_backend.auth.service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
    create_user,
    issue_token_response,
    refresh_tokens,
)
from dash_backend.db.session import get_db_session
from dash_backend.security.rate_limiter import auth_rate_limit
from dash_backend.security.local_identity import get_identity

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: None = Depends(auth_rate_limit),
) -> TokenResponse:
    """Register a new user and issue authentication tokens."""
    try:
        user = await create_user(session, payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or username already exists",
        ) from exc

    return await issue_token_response(session, user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: None = Depends(auth_rate_limit),
) -> TokenResponse:
    """Authenticate a user and issue authentication tokens."""
    try:
        user = await authenticate_user(session, payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return await issue_token_response(session, user)


@router.get("/me", response_model=UserRead)
async def current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the current authenticated user."""
    return user


class RefreshRequest(BaseModel):
    """Refresh token request payload."""
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: None = Depends(auth_rate_limit),
) -> TokenResponse:
    """Refresh access token using a valid refresh token."""
    try:
        return await refresh_tokens(session, payload.refresh_token)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ─── Device Pairing (for Android companion) ────────────────────────

class DevicePairRequest(BaseModel):
    """Android sends its device info; backend returns the local device token
    so the companion can authenticate all future REST/WebSocket requests.

    The pairing_code is a short shared secret configured via the
    DASH_PAIRING_CODE environment variable.  If unset, any non-empty code
    is accepted (single-user local trust model).
    """
    device_id: str = Field(..., description="Android device unique id")
    device_name: str = "DASH Companion"
    pairing_code: str = Field(..., min_length=1, description="Pairing code from DASH desktop")


class DevicePairResponse(BaseModel):
    device_token: str
    install_id: str
    server_url: str


@router.post("/device-pair", response_model=DevicePairResponse)
async def device_pair(
    payload: DevicePairRequest,
    _: None = Depends(auth_rate_limit),
) -> DevicePairResponse:
    """Pair an Android companion and return the local device token.

    The token grants full access to DASH (same trust as the desktop).
    The endpoint is intentionally unauthenticated — it is the ONLY way a
    remote companion can bootstrap trust.
    """
    import os

    expected_code = os.environ.get("DASH_PAIRING_CODE", "")
    if expected_code and payload.pairing_code != expected_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid pairing code",
        )

    identity = get_identity()
    return DevicePairResponse(
        device_token=identity.device_token,
        install_id=identity.install_id,
        server_url="/api/v1",
    )
