"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    revoke_all_refresh_tokens,
)
from dash_backend.db.session import get_db_session
from dash_backend.security.rate_limiter import auth_rate_limit
from dash_backend.security.local_identity import get_identity
from dash_backend.services.audit_logs import SecurityEventType, get_audit_service

router = APIRouter()


def _client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract IP and user-agent from a request for session metadata."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
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

    get_audit_service().log(
        SecurityEventType.REGISTER,
        user_id=str(user.id),
        action="register",
        category="auth",
        status="success",
        severity="INFO",
    )
    ip, ua = _client_info(request)
    return await issue_token_response(session, user, ip_address=ip, user_agent=ua)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: None = Depends(auth_rate_limit),
) -> TokenResponse:
    """Authenticate a user and issue authentication tokens."""
    user = None
    try:
        user = await authenticate_user(session, payload)
    except InvalidCredentialsError as exc:
        get_audit_service().log(
            SecurityEventType.LOGIN_FAILURE,
            action="login",
            category="auth",
            status="failure",
            details={"reason": "invalid_credentials"},
            severity="WARNING",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    get_audit_service().log(
        SecurityEventType.LOGIN_SUCCESS,
        user_id=str(user.id),
        action="login",
        category="auth",
        status="success",
        severity="INFO",
    )
    ip, ua = _client_info(request)
    return await issue_token_response(session, user, ip_address=ip, user_agent=ua)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Revoke all refresh tokens AND sessions for the current user.

    The access token remains valid until expiry (short-lived), but no new
    tokens can be issued. The frontend must clear local token storage.
    """
    count = await revoke_all_refresh_tokens(session, user.id)
    # Also revoke all active sessions
    try:
        from dash_backend.auth.session_service import revoke_all_sessions
        sessions_revoked = await revoke_all_sessions(session, user.id)
    except Exception:
        sessions_revoked = 0
    get_audit_service().log(
        SecurityEventType.LOGOUT,
        user_id=str(user.id),
        action="logout",
        category="auth",
        status="success",
        details={"tokens_revoked": count, "sessions_revoked": sessions_revoked},
        severity="INFO",
    )


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
        result = await refresh_tokens(session, payload.refresh_token)
        get_audit_service().log(
            SecurityEventType.TOKEN_REFRESH,
            user_id=str(result.user.id),
            action="refresh",
            category="auth",
            status="success",
            severity="INFO",
        )
        return result
    except InvalidCredentialsError as exc:
        get_audit_service().log(
            SecurityEventType.TOKEN_REFRESH_FAILED,
            action="refresh",
            category="auth",
            status="failure",
            details={"reason": "invalid_or_expired"},
            severity="WARNING",
        )
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
