"""Authentication dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.user import User
from dash_backend.auth.security import (
    InvalidTokenError,
    decode_access_token,
)
from dash_backend.auth.service import get_user_by_id
from dash_backend.db.session import get_db_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Resolve the current user from a bearer access token."""
    if credentials is None:
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise _unauthorized() from exc

    user = await get_user_by_id(session, payload["sub"])
    if user is None or not user.is_active:
        raise _unauthorized()

    return user


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
