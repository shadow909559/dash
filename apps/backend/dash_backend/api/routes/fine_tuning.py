"""API endpoints for DASH 3-level LLM fine-tuning."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.llm.fine_tuner import get_fine_tuning_manager

router = APIRouter()


class PromptUpdateRequest(BaseModel):
    mode: str
    prompt: Optional[str] = None
    instructions: Optional[str] = None


class IngestRequest(BaseModel):
    path: str
    type: str = "directory"  # "directory" or "file"


class TrainRequest(BaseModel):
    epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 2e-4


@router.get("/fine-tuning/status")
async def get_status(user: User = Depends(get_current_user)):
    """Get status of all 3 fine-tuning levels."""
    manager = get_fine_tuning_manager()
    return manager.get_status()


@router.post("/fine-tuning/prompt")
async def update_prompt(request: PromptUpdateRequest, user: User = Depends(get_current_user)):
    """Update system prompt for an agent mode (Level 1)."""
    manager = get_fine_tuning_manager()
    if request.prompt:
        manager.prompt_engine.set_custom_prompt(request.mode, request.prompt)
    if request.instructions:
        manager.prompt_engine.set_custom_instructions(request.mode, request.instructions)
    return {"status": "updated", "mode": request.mode}


@router.get("/fine-tuning/prompt/{mode}")
async def get_prompt(mode: str, user: User = Depends(get_current_user)):
    """Get the system prompt for an agent mode."""
    manager = get_fine_tuning_manager()
    prompt = manager.prompt_engine.get_system_prompt(mode)
    config = manager.prompt_engine.get_config(mode)
    return {
        "mode": mode,
        "prompt": prompt,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }


@router.post("/fine-tuning/ingest")
async def ingest_data(request: IngestRequest, user: User = Depends(get_current_user)):
    """Ingest data into RAG database (Level 2)."""
    manager = get_fine_tuning_manager()
    if request.type == "directory":
        count = await manager.ingest_obsidian_vault(request.path) if "obsidian" in request.path.lower() or "vault" in request.path.lower() else await manager.rag_engine.ingest_directory(request.path)
    else:
        count = await manager.rag_engine.ingest_file(request.path)
    return {"status": "ingested", "chunks": count, "path": request.path}


@router.post("/fine-tuning/ingest-obsidian")
async def ingest_obsidian(user: User = Depends(get_current_user)):
    """Ingest the Obsidian vault into RAG."""
    manager = get_fine_tuning_manager()
    count = await manager.ingest_obsidian_vault()
    return {"status": "ingested", "chunks": count}


@router.post("/fine-tuning/ingest-repo")
async def ingest_repo(request: IngestRequest, user: User = Depends(get_current_user)):
    """Ingest a code repository into RAG."""
    manager = get_fine_tuning_manager()
    count = await manager.ingest_code_repo(request.path)
    return {"status": "ingested", "chunks": count}


@router.get("/fine-tuning/search")
async def search_rag(query: str, top_k: int = 5, user: User = Depends(get_current_user)):
    """Search the RAG database."""
    manager = get_fine_tuning_manager()
    results = await manager.rag_engine.search(query, top_k)
    return {
        "query": query,
        "results": [
            {
                "id": r.id,
                "content": r.content[:500],
                "source": r.source,
                "chunk_index": r.chunk_index,
            }
            for r in results
        ],
    }


@router.post("/fine-tuning/prepare-training")
async def prepare_training(user: User = Depends(get_current_user)):
    """Collect conversations and export training data (Level 3 prep)."""
    manager = get_fine_tuning_manager()
    path = await manager.prepare_training_data()
    return {"status": "prepared", "path": path, "examples": len(manager.lora_trainer.examples)}


@router.get("/fine-tuning/training-script")
async def get_training_script(user: User = Depends(get_current_user)):
    """Generate the LoRA training script."""
    manager = get_fine_tuning_manager()
    path = manager.lora_trainer.generate_training_script()
    return {"status": "generated", "path": path}
