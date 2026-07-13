"""Aggregates all API v1 endpoint routers into a single router."""

from fastapi import APIRouter

from dash_backend.api.v1.endpoints import health, websocket

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(websocket.router)
