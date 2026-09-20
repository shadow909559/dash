"""Wake-word loop API: honest status + explicit start/stop control.

The loop holds the microphone, so control is deliberately manual and
visible: status always reports the real state (including failures), and
start/stop are explicit authenticated actions. Nothing auto-starts here.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dash_backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/voice/wake", tags=["Voice"])


class WakeLoopRequest(BaseModel):
    enabled: Optional[bool] = None


@router.get("/status")
async def wake_status(_user=Depends(get_current_user)):
    """The loop's honest state: running or not, why not, counters."""
    from dash_backend.voice_system.always_listening import get_wake_loop

    return get_wake_loop().get_status()


@router.post("/control")
async def wake_control(body: WakeLoopRequest, _user=Depends(get_current_user)):
    """Start or stop the always-listening loop on request.

    Start is refused with a real reason when disabled by env (the loop holds
    the microphone) or when the mic cannot be opened; the refusal reason is
    the backend's own words, verbatim.
    """
    from dash_backend.voice_system.always_listening import get_wake_loop

    loop = get_wake_loop()
    if body.enabled is True:
        result = await loop.start()
        if not result.get("ok"):
            raise HTTPException(status_code=409, detail=result.get("reason", "cannot start"))
        return {"ok": True, "state": "listening"}
    if body.enabled is False:
        return await loop.stop()
    return {"ok": False, "reason": "nothing requested; pass enabled=true or enabled=false"}
