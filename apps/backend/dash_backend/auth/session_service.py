"""Session lifecycle service.

Tracks active sessions created when tokens are issued (register, login, refresh).
Each session stores a hash of the refresh token, device metadata, and expiry.

Sessions are the authoritative record for "who is logged in from where" and
support per-session revocation and bulk revocation on logout.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.config import get_settings
from dash_backend.db.models.refresh_tokens import RefreshToken
from dash_backend.db.models.session import Session
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def _hash_refresh_token(token: str) -> str:
    """Hash a refresh token for session lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    refresh_token: str,
    *,
    device_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Session:
    """Record a new session when tokens are issued.

    The session stores a hash of the refresh token so it can be correlated
    with refresh/revocation operations. Raw tokens are never persisted.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)

    session_record = Session(
        user_id=user_id,
        device_id=device_id,
        token_hash=_hash_refresh_token(refresh_token),
        expires_at=expires_at,
    )
    db.add(session_record)
    await db.commit()
    await db.refresh(session_record)

    logger.info(
        "Session created id=%s user=%s expires=%s",
        session_record.id,
        user_id,
        expires_at.isoformat(),
    )
    return session_record


async def list_user_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_revoked: bool = False,
) -> List[Session]:
    """List all sessions for a user, optionally including revoked ones.

    Returns sessions sorted by created_at descending (newest first).
    """
    stmt = (
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.created_at.desc())
    )
    if not include_revoked:
        stmt = stmt.where(Session.revoked_at.is_(None))

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_session_by_refresh_token(
    db: AsyncSession,
    refresh_token: str,
) -> Optional[Session]:
    """Look up the session associated with a refresh token hash."""
    token_hash = _hash_refresh_token(refresh_token)
    stmt = select(Session).where(Session.token_hash == token_hash)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Revoke a single session. Returns True if revoked, False if not found.

    Also revokes the associated refresh token so it cannot be used again.
    """
    stmt = (
        select(Session)
        .where(Session.id == session_id, Session.user_id == user_id)
    )
    result = await db.execute(stmt)
    session_record = result.scalar_one_or_none()

    if session_record is None:
        return False

    if session_record.revoked_at is not None:
        # Already revoked
        return True

    now = datetime.now(UTC)
    session_record.revoked_at = now

    # Also revoke the associated refresh token by hash
    refresh_stmt = (
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == session_record.token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    refresh_result = await db.execute(refresh_stmt)
    refresh_token = refresh_result.scalar_one_or_none()
    if refresh_token is not None:
        refresh_token.revoked_at = now

    await db.commit()
    logger.info("Session revoked id=%s user=%s", session_id, user_id)
    return True


async def revoke_all_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    except_session_id: Optional[uuid.UUID] = None,
) -> int:
    """Revoke all sessions for a user (logout). Returns count revoked.

    Optionally excludes one session (the current one) for selective logout.
    Also revokes all associated refresh tokens.
    """
    now = datetime.now(UTC)

    # Find active sessions
    stmt = (
        select(Session)
        .where(
            Session.user_id == user_id,
            Session.revoked_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    sessions = list(result.scalars().all())

    revoked_count = 0
    token_hashes_to_revoke: List[str] = []

    for sess in sessions:
        if except_session_id and sess.id == except_session_id:
            continue
        sess.revoked_at = now
        token_hashes_to_revoke.append(sess.token_hash)
        revoked_count += 1

    # Bulk revoke associated refresh tokens
    if token_hashes_to_revoke:
        refresh_stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash.in_(token_hashes_to_revoke),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.execute(refresh_stmt)

    await db.commit()
    logger.info("Revoked %d sessions for user %s", revoked_count, user_id)
    return revoked_count


def _naive_utc(dt) -> datetime | None:
    """Normalize a datetime to naive UTC (sqlite round-trips aware as naive)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


async def is_session_valid(db: AsyncSession, session_id: uuid.UUID) -> bool:
    """Check if a session is still valid (not revoked, not expired)."""
    stmt = select(Session).where(Session.id == session_id)
    result = await db.execute(stmt)
    session_record = result.scalar_one_or_none()

    if session_record is None:
        return False
    if session_record.revoked_at is not None:
        return False
    expires = _naive_utc(session_record.expires_at)
    if expires is not None and expires < datetime.now(UTC).replace(tzinfo=None):
        return False
    return True


def session_to_dict(session_record: Session) -> Dict[str, Any]:
    """Serialize a session for API responses. Exposes no secrets."""
    expires = _naive_utc(session_record.expires_at)
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    return {
        "id": str(session_record.id),
        "user_id": str(session_record.user_id),
        "device_id": str(session_record.device_id) if session_record.device_id else None,
        "created_at": session_record.created_at.isoformat() if session_record.created_at else None,
        "expires_at": session_record.expires_at.isoformat() if session_record.expires_at else None,
        "revoked_at": session_record.revoked_at.isoformat() if session_record.revoked_at else None,
        "is_active": session_record.revoked_at is None and (
            expires is None or expires >= now_naive
        ),
    }
