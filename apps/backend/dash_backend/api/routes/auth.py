"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
)
from dash_backend.db.session import get_db_session
from dash_backend.security.rate_limiter import auth_rate_limit

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
