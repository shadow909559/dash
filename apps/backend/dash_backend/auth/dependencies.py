"""Authentication dependencies — single-user local device identity.

DASH is a personal single-user system with NO login UI. The Windows user
account/device is the identity boundary:

    request (Authorization: Bearer <device-token>)
        -> verify against the persistent installation identity
        -> map to the single auto-provisioned OWNER user
        -> protected endpoint

Rules:
- A missing or invalid device token yields HTTP 401. There is NO fallback
  that silently provisions a guest identity.
- The owner user exists purely as the data-ownership anchor for foreign keys.
  It cannot be used to log in (random unusable password hash).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger
from dash_backend.security.local_identity import verify_device_token

logger = get_logger(__name__)

# Single data-owner identity for this installation.
OWNER_USERNAME = "owner"
OWNER_EMAIL = "owner@local.dash"
OWNER_DISPLAY_NAME = "DASH Owner"

bearer_scheme = HTTPBearer(auto_error=False)

_401 = dict(status_code=status.HTTP_401_UNAUTHORIZED, detail="DASH device authentication required",
            headers={"WWW-Authenticate": "Bearer"})


def _extract_token(credentials: HTTPAuthorizationCredentials | None, websocket_token: str | None = None) -> str | None:
    if credentials and credentials.credentials:
        return credentials.credentials
    return websocket_token


async def _get_or_create_owner_user(session: AsyncSession) -> User:
    """Return the single owner user (created once, server-side)."""
    user = await session.scalar(select(User).where(User.username == OWNER_USERNAME))
    if user is not None:
        return user

    from dash_backend.auth.security import hash_password

    owner = User(
        email=OWNER_EMAIL,
        username=OWNER_USERNAME,
        # Unusable credential: no login path exists for this account.
        password_hash=hash_password(uuid.uuid4().hex + uuid.uuid4().hex),
        display_name=OWNER_DISPLAY_NAME,
        is_active=True,
    )
    session.add(owner)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        user = await session.scalar(select(User).where(User.username == OWNER_USERNAME))
        if user is not None:
            return user
        raise

    await session.refresh(owner)
    logger.info("Auto-provisioned DASH owner user (data anchor; no login credentials)")
    return owner


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Authorize via the local device identity; 401 otherwise."""
    token = _extract_token(credentials)
    if not verify_device_token(token):
        logger.warning("Unauthorized request: missing/invalid device token")
        raise HTTPException(**_401)
    return await _get_or_create_owner_user(session)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> str:
    """Authorized owner id; 401 otherwise."""
    user = await get_current_user(credentials, session)
    return str(user.id)


async def resolve_owner_user(session: AsyncSession) -> User:
    """Server-side helper (startup/WS after handshake auth): returns owner."""
    return await _get_or_create_owner_user(session)
