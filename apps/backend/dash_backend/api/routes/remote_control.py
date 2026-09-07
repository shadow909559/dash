"""Remote control API routes.

Allows the Android companion (or any authenticated device) to:
- Check DASH service status (backend, Ollama, Qwen, Desktop)
- Request service startup (start Ollama, start backend, etc.)
- Request DASH restart
- Get full system status

These commands are authenticated and authorized via device tokens.
Destructive operations require approval.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dash_backend.logging_config import get_logger
from dash_backend.auth.dependencies import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/remote", tags=["remote-control"])


class ServiceName(str, Enum):
    BACKEND = "backend"
    OLLAMA = "ollama"
    DESKTOP = "desktop"
    ALL = "all"


class ServiceStatus(BaseModel):
    name: str
    running: bool
    healthy: bool = False
    pid: Optional[int] = None
    detail: str = ""


class SystemStatusResponse(BaseModel):
    backend: ServiceStatus
    ollama: ServiceStatus
    qwen: ServiceStatus
    desktop: ServiceStatus
    overall: str  # "ready", "degraded", "offline"


class WakeOnLanRequest(BaseModel):
    mac_address: str = Field(..., description="MAC address (AA:BB:CC:DD:EE:FF)")
    broadcast: Optional[str] = Field(default=None, description="Broadcast IP override")
    count: int = Field(default=3, ge=1, le=10, description="Number of packets")

class StartServiceRequest(BaseModel):
    service: ServiceName
    force: bool = Field(default=False, description="Force restart even if running")


class StartServiceResponse(BaseModel):
    success: bool
    message: str
    status: SystemStatusResponse


def _check_port(port: int) -> bool:
    """Check if a port is in use."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False


async def _get_backend_status() -> ServiceStatus:
    """Check if the DASH backend is healthy."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://127.0.0.1:8000/health")
            if r.status_code == 200:
                return ServiceStatus(
                    name="backend", running=True, healthy=True,
                    detail=r.json().get("version", "unknown"),
                )
    except Exception:
        pass
    return ServiceStatus(name="backend", running=False, healthy=False)


async def _get_ollama_status() -> ServiceStatus:
    """Check if Ollama is reachable."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://127.0.0.1:11434/api/tags")
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                return ServiceStatus(
                    name="ollama", running=True, healthy=True,
                    detail=f"{len(models)} models loaded",
                )
    except Exception:
        pass
    return ServiceStatus(name="ollama", running=False, healthy=False)


async def _get_qwen_status() -> ServiceStatus:
    """Check if Qwen model is available in Ollama."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://127.0.0.1:11434/api/tags")
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                qwen_available = any("qwen" in m.lower() for m in models)
                return ServiceStatus(
                    name="qwen", running=qwen_available, healthy=qwen_available,
                    detail="available" if qwen_available else "not found",
                )
    except Exception:
        pass
    return ServiceStatus(name="qwen", running=False, healthy=False)


async def _get_desktop_status() -> ServiceStatus:
    """Check if DASH Desktop (Electron) is running."""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq DASH Desktop.exe"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            running = "DASH Desktop.exe" in result.stdout
        else:
            result = subprocess.run(
                ["pgrep", "-f", "electron|DASH"],
                capture_output=True, text=True, timeout=5,
            )
            running = result.returncode == 0

        return ServiceStatus(
            name="desktop", running=running, healthy=running,
            detail="Electron process" if running else "not running",
        )
    except Exception as e:
        return ServiceStatus(name="desktop", running=False, healthy=False, detail=str(e))


async def _start_ollama() -> bool:
    """Start Ollama serve process."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        # Wait for it to become healthy (max 15s)
        import httpx
        for i in range(15):
            await asyncio.sleep(1)
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    r = await client.get("http://127.0.0.1:11434/api/tags")
                    if r.status_code == 200:
                        return True
            except Exception:
                pass

        return False
    except Exception as e:
        logger.exception("Failed to start Ollama: %s", e)
        return False


async def _start_backend() -> bool:
    """Start DASH backend if not running."""
    try:
        backend_healthy = await _get_backend_status()
        if backend_healthy.running:
            return True

        # Use the Windows scheduled task or direct Python invocation
        if sys.platform == "win32":
            # Try starting via scheduled task
            try:
                subprocess.run(
                    ["schtasks", "/Run", "/TN", "DASHCore"],
                    capture_output=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass

            # Wait for backend to become healthy
            for i in range(30):
                await asyncio.sleep(1)
                if (await _get_backend_status()).running:
                    return True
        else:
            # Unix: start via Python module
            subprocess.Popen(
                ["python", "-m", "uvicorn", "dash_backend.main:app",
                 "--host", "127.0.0.1", "--port", "8000"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for i in range(30):
                await asyncio.sleep(1)
                if (await _get_backend_status()).running:
                    return True

        return False
    except Exception as e:
        logger.exception("Failed to start backend: %s", e)
        return False


async def _get_system_status() -> SystemStatusResponse:
    """Get full system status."""
    backend = await _get_backend_status()
    ollama = await _get_ollama_status()
    qwen = await _get_qwen_status()
    desktop = await _get_desktop_status()

    if backend.healthy and ollama.healthy and qwen.healthy:
        overall = "ready"
    elif backend.healthy:
        overall = "degraded"
    else:
        overall = "offline"

    return SystemStatusResponse(
        backend=backend,
        ollama=ollama,
        qwen=qwen,
        desktop=desktop,
        overall=overall,
    )


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    user = Depends(get_current_user),
) -> SystemStatusResponse:
    """Get full DASH system status (backend, Ollama, Qwen, Desktop)."""
    return await _get_system_status()


@router.post("/wol")
async def wake_on_lan(
    req: WakeOnLanRequest,
    user = Depends(get_current_user),
) -> dict:
    """Send a Wake-on-LAN magic packet to power on a device."""
    from dash_backend.services.wol import send_wol
    result = await send_wol(
        mac_address=req.mac_address,
        broadcast=req.broadcast,
        count=req.count,
    )
    return result


@router.post("/start", response_model=StartServiceResponse)
async def start_service(
    req: StartServiceRequest,
    user = Depends(get_current_user),
) -> StartServiceResponse:
    """Request a DASH service to start. Requires authentication."""
    success = True
    message = ""

    if req.service == ServiceName.OLLAMA or req.service == ServiceName.ALL:
        if not (await _get_ollama_status()).running or req.force:
            started = await _start_ollama()
            if started:
                message += "Ollama started. "
            else:
                message += "Ollama start failed. "
                success = False

    if req.service == ServiceName.BACKEND or req.service == ServiceName.ALL:
        if not (await _get_backend_status()).running or req.force:
            started = await _start_backend()
            if started:
                message += "Backend started. "
            else:
                message += "Backend start failed. "
                success = False

    if req.service == ServiceName.DESKTOP or req.service == ServiceName.ALL:
        if not (await _get_desktop_status()).running or req.force:
            try:
                if sys.platform == "win32":
                    subprocess.Popen(
                        ["cmd", "/c", "start", "", r"C:\Users\Asus\Desktop\dash\apps\desktop\DASH Desktop.exe"],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    message += "Desktop launch requested. "
                else:
                    message += "Desktop auto-start only supported on Windows. "
            except Exception as e:
                message += f"Desktop start failed: {e}. "
                success = False

    if not message:
        message = "All requested services already running."

    status = await _get_system_status()
    return StartServiceResponse(success=success, message=message, status=status)


# ── Custom Wake Word ──────────────────────────────────────

_custom_wake_words: dict[str, str] = {}  # user_id -> custom phrase
DEFAULT_WAKE_PHRASE = "Hey DASH"


class WakeWordResponse(BaseModel):
    phrase: str = DEFAULT_WAKE_PHRASE


class WakeWordUpdate(BaseModel):
    phrase: str


@router.get("/wake-word", response_model=WakeWordResponse)
async def get_wake_word(
    user = Depends(get_current_user),
) -> WakeWordResponse:
    """Get the custom wake word phrase for the current user."""
    phrase = _custom_wake_words.get(str(user.id), DEFAULT_WAKE_PHRASE)
    return WakeWordResponse(phrase=phrase)


@router.put("/wake-word", response_model=WakeWordResponse)
async def update_wake_word(
    payload: WakeWordUpdate,
    user = Depends(get_current_user),
) -> WakeWordResponse:
    """Update the custom wake word phrase for the current user."""
    phrase = payload.phrase.strip() if payload.phrase else DEFAULT_WAKE_PHRASE
    _custom_wake_words[str(user.id)] = phrase
    logger.info("Wake word updated for user %s: %s", user.id, phrase)
    return WakeWordResponse(phrase=phrase)


def get_user_wake_word(user_id: str) -> str:
    """Get the custom wake word for a user (used by WebSocket handler)."""
    return _custom_wake_words.get(user_id, DEFAULT_WAKE_PHRASE)
