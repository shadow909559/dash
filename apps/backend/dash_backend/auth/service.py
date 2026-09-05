"""Authentication service functions."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.refresh_tokens import RefreshToken
from dash_backend.db.models.user import User
from dash_backend.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from dash_backend.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from dash_backend.config import get_settings


class AuthError(Exception):
    """Base authentication service error."""


class UserAlreadyExistsError(AuthError):
    """Raised when a user email or username is already registered."""


class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid."""


async def create_user(session: AsyncSession, payload: RegisterRequest) -> User:
    """Create a user account."""
    existing = await session.scalar(
        select(User).where(or_(User.email == payload.email, User.username == payload.username))
    )
    if existing is not None:
        raise UserAlreadyExistsError

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    session.add(user)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise UserAlreadyExistsError from exc

    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, payload: LoginRequest) -> User:
    """Return the user for valid login credentials."""
    user = await session.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active:
        raise InvalidCredentialsError
    if not verify_password(payload.password, user.password_hash):
        raise InvalidCredentialsError
    return user


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    """Look up a user by id."""
    import uuid
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    return await session.get(User, uid)


async def issue_token_response(session: AsyncSession, user: User) -> TokenResponse:
    """Issue access and refresh tokens for a user."""
    settings = get_settings()
    access_token, expires_in = create_access_token(str(user.id))
    refresh_token = create_refresh_token()
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(refresh_token_record)
    await session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


async def refresh_tokens(session: AsyncSession, refresh_token: str) -> TokenResponse:
    """Refresh access token using a valid refresh token."""
    from sqlalchemy import and_
    
    token_hash = hash_refresh_token(refresh_token)
    
    # Find valid, non-revoked refresh token
    refresh_record = await session.scalar(
        select(RefreshToken).where(
            and_(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
    )
    
    if refresh_record is None:
        raise InvalidCredentialsError
    
    # Get the user
    user = await session.get(User, refresh_record.user_id)
    if user is None or not user.is_active:
        raise InvalidCredentialsError
    
    # Revoke old refresh token
    refresh_record.revoked_at = datetime.now(UTC)
    
    # Issue new tokens
    return await issue_token_response(session, user)
