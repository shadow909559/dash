"""Vision recognition routes: real object detection + face recognition.

All endpoints require the device token (these operate the local camera and
biometric-adjacent data — never public). Honesty contract: a missing model
is reported as a named reason, never papered over; every detection carries
its backend provenance.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/vision", tags=["Vision Recognition"])


@router.get("/watch/status")
async def watch_status(_user=Depends(get_current_user)):
    """The watcher's honest state: running, cycles, what it last saw, and
    every event it delivered (or could not deliver) and to where."""
    from dash_backend.vision.watcher import get_vision_watcher

    return get_vision_watcher().get_status()


@router.post("/watch/scan-now")
async def watch_scan_now(_user=Depends(get_current_user)):
    """Run one watch cycle immediately and return its full record —
    including the named cause when the camera or models are unavailable."""
    from dash_backend.vision.watcher import get_vision_watcher

    return await get_vision_watcher().scan_now()


class WatcherConfigIn(BaseModel):
    """Partial update: only the fields present are changed; all-or-nothing.

    notify_known_persons is STRICT: pydantic's lax mode would silently
    coerce "yes"/"on"/1 into true — a config lie (decisions.md #74).
    Numeric lax coercion ("6" → 6.0, "1" → 1) preserves the value and
    stays allowed.
    """

    interval_seconds: Optional[float] = Field(default=None, gt=0)
    repeat_cooldown_s: Optional[float] = Field(default=None, ge=0)
    camera_id: Optional[int] = None
    notify_known_persons: Optional[bool] = Field(default=None, strict=True)
    notify_cooldown_s: Optional[float] = Field(default=None, ge=0)


def _config_response(watcher: Any) -> dict[str, Any]:
    from dash_backend.vision import watcher as watcher_mod

    cfg = watcher.get_config()
    store = watcher._config_store
    cfg["limits"] = {
        "interval_seconds_min": watcher_mod.MIN_INTERVAL_S,
        "repeat_cooldown_s_min": 0.0,
        "camera_id_max": watcher_mod.MAX_CAMERA_ID,
        "notify_cooldown_s_min": 0.0,
    }
    cfg["defaults"] = {
        "interval_seconds": watcher_mod.DEFAULT_INTERVAL_S,
        "repeat_cooldown_s": watcher_mod.REPEAT_COOLDOWN_S,
        "notify_known_persons": False,
        "notify_cooldown_s": watcher_mod.NOTIFY_COOLDOWN_S,
    }
    cfg["config_file"] = str(store.path)
    if store.last_error:
        cfg["config_warning"] = store.last_error
    return cfg


@router.get("/watch/config")
async def get_watch_config(_user=Depends(get_current_user)):
    """The watcher's active configuration, where it persists, its limits,
    and a warning line when the stored file was corrupt and defaults won."""
    from dash_backend.vision.watcher import get_vision_watcher

    return _config_response(get_vision_watcher())


@router.put("/watch/config")
async def put_watch_config(
    body: WatcherConfigIn, _user=Depends(get_current_user)
):
    """Update interval, cooldown, and/or camera id — applied to the live
    watcher immediately (no restart) and persisted for future boots.

    All-or-nothing: any invalid field means nothing changes and every
    error comes back named. Pydantic catches shape/range problems; the
    watcher layer catches semantic ones (interval below the honest floor).
    """
    from dash_backend.vision.watcher import get_vision_watcher

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(422, "no settings provided")
    nulls = sorted(k for k, v in updates.items() if v is None)
    if nulls:
        raise HTTPException(
            422,
            f"explicit null not allowed for {', '.join(nulls)} — "
            "omit the field to leave it unchanged",
        )
    result = get_vision_watcher().configure(**updates)
    if not result.get("ok"):
        raise HTTPException(422, "; ".join(result.get("errors", ["invalid"])))
    return result["applied"]


class _PersonNotifyBody(BaseModel):
    notify: bool


@router.put("/persons/{person_id}/notify")
async def set_person_notify(
    person_id: str, body: _PersonNotifyBody, _user=Depends(get_current_user)
):
    """Per-person watcher preference: whether this person's recognition is
    reported onward (brain/bus/audit/workflows). The person stays enrolled
    and recognized either way — this only controls reporting."""
    from dash_backend.vision import recognition

    ok = recognition.get_face_service().set_person_notify(
        person_id, bool(body.notify)
    )
    if not ok:
        raise HTTPException(404, "person not found")
    return {"ok": True, "person_id": person_id, "notify": bool(body.notify)}


@router.get("/status")
async def vision_status(_user=Depends(get_current_user)):
    """Honest capability report: which models exist, what works, how to fix it."""
    from dash_backend.vision import recognition

    status = recognition.model_status()
    detector = recognition.get_object_detector()
    faces = recognition.get_face_service()
    return {
        **status,
        "object_detection": {
            "available": detector.available,
            "reason": "" if detector.available else detector.unavailable_reason,
        },
        "face_recognition": {
            "available": faces.available,
            "reasons": faces.unavailable_reasons(),
            "enrolled_persons": len(faces.list_persons()),
        },
        "opencv_installed": _cv2_available(),
        "privacy": "all inference runs locally; no image ever leaves this machine",
    }


def _cv2_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("cv2") is not None


@router.post("/analyze")
async def analyze_image(request: Request, _user=Depends(get_current_user)):
    """Analyze an uploaded image: objects + faces + recognized persons.

    Body: raw image bytes (jpeg/png/...). The reply always carries backend
    provenance; when models are missing the reason is named instead of
    returning invented detections.
    """
    from dash_backend.vision import recognition

    image_bytes = await request.body()
    if not image_bytes:
        raise HTTPException(400, "empty body — send raw image bytes")
    rgb = recognition.decode_to_rgb_array(image_bytes)
    if rgb is None:
        raise HTTPException(422, "image could not be decoded (jpeg/png/webp supported)")

    faces = recognition.get_face_service()
    detector = recognition.get_object_detector()
    result = faces.analyze_frame(rgb, include_objects=detector)
    return result.to_dict()


@router.post("/camera/analyze")
async def analyze_camera(camera_id: int = 0, _user=Depends(get_current_user)):
    """Capture one frame from the local camera and analyze it end-to-end.

    Honest failures: no OpenCV, no camera, or a missing model are each
    named with the actual cause and a fix hint — never lumped together and
    never papered over.
    """
    from dash_backend.vision.camera_vision import get_camera_vision
    from dash_backend.vision import recognition

    cap = await get_camera_vision().capture_result(camera_id)
    if not cap.ok:
        raise HTTPException(503, f"camera capture failed: {cap.error} — {cap.hint}")
    rgb = recognition.decode_to_rgb_array(cap.frame)
    if rgb is None:
        raise HTTPException(422, "captured frame could not be decoded")
    faces = recognition.get_face_service()
    detector = recognition.get_object_detector()
    result = faces.analyze_frame(rgb, include_objects=detector)
    return result.to_dict()


@router.post("/camera/enroll")
async def enroll_from_camera(
    name: str,
    camera_id: int = 0,
    _user=Depends(get_current_user),
):
    """Capture a frame from the local camera and enroll the clearest face
    under `name` — enrollment without needing an image file.

    Same honesty contract as /camera/analyze for capture failures; enroll
    returns 409 with the reason when no usable face is in frame or models
    are missing (the reason names which model to fetch).
    """
    from dash_backend.vision.camera_vision import get_camera_vision
    from dash_backend.vision import recognition

    if not name or not name.strip():
        raise HTTPException(422, "name is required")
    cap = await get_camera_vision().capture_result(camera_id)
    if not cap.ok:
        raise HTTPException(503, f"camera capture failed: {cap.error} — {cap.hint}")
    rgb = recognition.decode_to_rgb_array(cap.frame)
    if rgb is None:
        raise HTTPException(422, "captured frame could not be decoded")
    result = recognition.get_face_service().enroll(rgb, name)
    if not result.get("ok"):
        raise HTTPException(409, result.get("reason", "enrollment failed"))
    return result


@router.post("/enroll")
async def enroll_person(
    request: Request,
    name: str,
    person_id: Optional[str] = None,
    _user=Depends(get_current_user),
):
    """Enroll the clearest face in the uploaded image under `name`."""
    from dash_backend.vision import recognition

    image_bytes = await request.body()
    if not image_bytes:
        raise HTTPException(400, "empty body — send raw image bytes")
    rgb = recognition.decode_to_rgb_array(image_bytes)
    if rgb is None:
        raise HTTPException(422, "image could not be decoded")
    result = recognition.get_face_service().enroll(rgb, name, person_id)
    if not result.get("ok"):
        raise HTTPException(409, result.get("reason", "enrollment failed"))
    return result


@router.get("/persons")
async def list_persons(_user=Depends(get_current_user)):
    from dash_backend.vision import recognition

    return {"persons": recognition.get_face_service().list_persons()}


@router.get("/persons/{person_id}")
async def get_person(person_id: str, _user=Depends(get_current_user)):
    """One person's enrollment summary including their notify preference."""
    from dash_backend.vision import recognition

    for p in recognition.get_face_service().list_persons():
        if p.get("person_id") == person_id:
            return p
    raise HTTPException(404, "person not found")


@router.delete("/persons/{person_id}")
async def delete_person(person_id: str, _user=Depends(get_current_user)):
    from dash_backend.vision import recognition

    if not recognition.get_face_service().remove_person(person_id):
        raise HTTPException(404, "person not found")
    return {"ok": True}
