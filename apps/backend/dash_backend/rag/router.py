"""FastAPI router for RAG endpoints."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.rag import schemas
from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.session import get_db_session
from dash_backend.rag import service as rag_service
from dash_backend.db.models.user import User

router = APIRouter(prefix="", tags=["rag"])


@router.post("/documents", response_model=schemas.DocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: schemas.DocumentCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.DocumentRead:
    doc = await rag_service.create_document(session, user.id, payload.content, filename=payload.filename, metadata=payload.metadata)
    # asynchronous processing (chunking + embeddings) - process now (synchronous) for simplicity
    await rag_service.process_document(session, doc.id)
    return schemas.DocumentRead.model_validate(doc)


@router.get("/documents", response_model=List[schemas.DocumentRead])
async def list_documents(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> List[schemas.DocumentRead]:
    stmt = await session.execute(
        "SELECT id FROM documents WHERE user_id = :uid ORDER BY created_at DESC",
        {"uid": str(user.id)},
    )
    rows = stmt.fetchall()
    docs = []
    for (did,) in rows:
        d = await session.get(rag_service.models.Document, did)
        if d:
            docs.append(d)
    return [schemas.DocumentRead.model_validate(d) for d in docs]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    doc = await session.get(rag_service.models.Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your document")
    await session.delete(doc)
    await session.commit()
    return None


@router.post("/search", response_model=schemas.SearchResponse)
async def search(
    payload: schemas.SearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.SearchResponse:
    results = await rag_service.search_documents(session, user.id, payload.query, top_k=payload.top_k)
    items = []
    for chunk, score in results:
        # attempt to fetch filename
        filename = None
        try:
            filename = getattr(chunk, "document", None) and getattr(chunk.document, "filename", None)
        except Exception:
            filename = None
        items.append(
            schemas.SearchResultItem(
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                score=score,
            )
        )
    return schemas.SearchResponse(items=items, query=payload.query)
