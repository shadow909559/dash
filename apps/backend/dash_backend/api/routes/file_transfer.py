"""REST API routes for file transfer between phone and PC."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/transfer", tags=["transfer"])


# ── Request / Response Models ────────────────────────────────


class FileTransferResponse(BaseModel):
    status: str = "ok"
    message: str = ""
    file_id: str = ""
    filename: str = ""
    size_bytes: int = 0
    path: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class FileDownloadRequest(BaseModel):
    path: str = Field(..., description="Path to file on PC to download")


class FileUploadRequest(BaseModel):
    filename: str = Field(..., description="Name of the file")
    data_base64: str = Field(..., description="Base64-encoded file data")
    destination: str = Field(default="downloads", description="Destination folder (downloads, documents, pictures, etc.)")


# ── Helper Functions ─────────────────────────────────────────


def _get_destination_folder(destination: str) -> Path:
    """Resolve destination folder name to actual path."""
    special_folders = {
        "downloads": Path.home() / "Downloads",
        "documents": Path.home() / "Documents",
        "pictures": Path.home() / "Pictures",
        "videos": Path.home() / "Videos",
        "music": Path.home() / "Music",
        "desktop": Path.home() / "Desktop",
    }
    
    dest_lower = destination.lower()
    if dest_lower in special_folders:
        return special_folders[dest_lower]
    
    # Use as-is if it's an absolute path, otherwise treat as relative to Downloads
    dest_path = Path(destination)
    if dest_path.is_absolute():
        return dest_path
    return Path.home() / "Downloads" / destination


# ── Endpoints ────────────────────────────────────────────────


# ── Transfer history (in-process, bounded) ───────────────────

_TRANSFER_HISTORY: list[dict[str, Any]] = []
_TRANSFER_HISTORY_MAX = 100


def _record_transfer(
    *, direction: str, file_id: str, filename: str, size_bytes: int,
    path: str, details: dict[str, Any] | None = None,
) -> None:
    """Append a transfer record to the bounded in-process history."""
    entry: dict[str, Any] = {
        "file_id": file_id,
        "direction": direction,  # "upload" (phone->PC) or "download" (PC->phone)
        "filename": filename,
        "size_bytes": size_bytes,
        "path": path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details or {},
    }
    _TRANSFER_HISTORY.append(entry)
    del _TRANSFER_HISTORY[:-_TRANSFER_HISTORY_MAX]


@router.post("/upload", response_model=FileTransferResponse)
async def upload_file_to_pc(
    payload: FileUploadRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FileTransferResponse:
    """Upload a file from phone to PC."""
    try:
        import uuid
        
        # Decode base64 data
        try:
            file_bytes = base64.b64decode(payload.data_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 data")
        
        # Get destination folder
        dest_folder = _get_destination_folder(payload.destination)
        dest_folder.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = dest_folder / payload.filename
        file_path.write_bytes(file_bytes)
        
        file_id = str(uuid.uuid4())
        _record_transfer(
            direction="upload",
            file_id=file_id,
            filename=payload.filename,
            size_bytes=len(file_bytes),
            path=str(file_path),
            details={"destination": payload.destination},
        )
        
        logger.info("File uploaded from phone: %s -> %s (%d bytes)", 
                   payload.filename, file_path, len(file_bytes))
        
        return FileTransferResponse(
            status="ok",
            message=f"File uploaded successfully to {file_path}",
            file_id=file_id,
            filename=payload.filename,
            size_bytes=len(file_bytes),
            path=str(file_path),
            details={"destination": payload.destination},
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("File upload failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/download", response_model=FileTransferResponse)
async def download_file_from_pc(
    payload: FileDownloadRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FileTransferResponse:
    """Download a file from PC to phone (returns base64-encoded data)."""
    try:
        import uuid
        
        file_path = Path(payload.path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {payload.path}")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail=f"Not a file: {payload.path}")
        
        # Read file and encode as base64
        file_bytes = file_path.read_bytes()
        file_base64 = base64.b64encode(file_bytes).decode('utf-8')
        
        file_id = str(uuid.uuid4())
        _record_transfer(
            direction="download",
            file_id=file_id,
            filename=file_path.name,
            size_bytes=len(file_bytes),
            path=str(file_path),
        )
        
        logger.info("File downloaded from PC: %s (%d bytes)", payload.path, len(file_bytes))
        
        return FileTransferResponse(
            status="ok",
            message=f"File downloaded successfully",
            file_id=file_id,
            filename=file_path.name,
            size_bytes=len(file_bytes),
            path=str(file_path),
            details={"data_base64": file_base64},
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("File download failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/upload/multipart", response_model=FileTransferResponse)
async def upload_file_multipart(
    file: UploadFile = File(...),
    destination: str = Query("downloads", description="Destination folder"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FileTransferResponse:
    """Upload a file from phone to PC using multipart form data."""
    try:
        import uuid
        
        # Read file data
        file_bytes = await file.read()
        
        # Get destination folder
        dest_folder = _get_destination_folder(destination)
        dest_folder.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = dest_folder / (file.filename or "uploaded_file")
        file_path.write_bytes(file_bytes)
        
        file_id = str(uuid.uuid4())
        _record_transfer(
            direction="upload",
            file_id=file_id,
            filename=file.filename or "uploaded_file",
            size_bytes=len(file_bytes),
            path=str(file_path),
            details={"destination": destination},
        )
        
        logger.info("File uploaded via multipart: %s -> %s (%d bytes)", 
                   file.filename, file_path, len(file_bytes))
        
        return FileTransferResponse(
            status="ok",
            message=f"File uploaded successfully to {file_path}",
            file_id=file_id,
            filename=file.filename or "uploaded_file",
            size_bytes=len(file_bytes),
            path=str(file_path),
            details={"destination": destination},
        )
        
    except Exception as exc:
        logger.exception("Multipart file upload failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/destinations", response_model=dict[str, str])
async def list_destinations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """List available destination folders for file transfer."""
    special_folders = {
        "downloads": str(Path.home() / "Downloads"),
        "documents": str(Path.home() / "Documents"),
        "pictures": str(Path.home() / "Pictures"),
        "videos": str(Path.home() / "Videos"),
        "music": str(Path.home() / "Music"),
        "desktop": str(Path.home() / "Desktop"),
    }
    
    # Only return folders that exist
    available = {}
    for name, path in special_folders.items():
        if Path(path).exists():
            available[name] = path
    
    return available


@router.get("/recent", response_model=list[dict[str, Any]])
async def list_recent_transfers(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """List recent file transfers (most recent first)."""
    return list(reversed(_TRANSFER_HISTORY))[:limit]
