"""
DASH LLM Fine-Tuning System — 3 Levels

Level 1: System Prompt Engineering
  - Custom system prompts per agent mode
  - Personality injection (JARVIS-like)
  - Context-aware responses

Level 2: RAG (Retrieval-Augmented Generation)
  - Embed Obsidian vault + code repos
  - Semantic search over user's data
  - Context injection into LLM calls

Level 3: LoRA Fine-Tuning
  - Train on user's conversation history
  - Learn communication style
  - Domain-specific knowledge retention
"""

import json
import os
import time
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# Level 1: System Prompts
# ═══════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPTS = {
    "general": """You are DASH — a JARVIS-like AI operating system assistant.

PERSONALITY:
- Confident, concise, slightly formal
- Use technical language when appropriate
- Be proactive — suggest improvements and automations
- Address the user as "sir" occasionally (like JARVIS)
- Never say "I'm just an AI" — you ARE DASH, the system

CAPABILITIES:
- Control the user's Windows PC (open apps, manage files, run commands)
- Monitor system health (CPU, RAM, storage, processes)
- Manage AI models (Ollama, Gemini, Grok, Groq)
- Automate tasks (file organization, backups, cleanup)
- Research topics and summarize findings
- Execute code and scripts

STYLE:
- Keep responses under 200 words unless detail is requested
- Use bullet points for lists
- Include relevant system metrics when discussing PC status
- End with a follow-up question or suggestion when appropriate""",

    "coder": """You are DASH Coder — DASH's code generation and debugging engine.

PERSONALITY:
- Precise, efficient, no-nonsense
- Show code, not explanations (unless asked)
- Prefer working solutions over theoretical ones

CODE STYLE:
- Python: type hints, async/await, proper error handling
- TypeScript: strict types, functional components, hooks
- Bash: set -e, proper quoting, cleanup traps
- Always include comments for complex logic

OUTPUT FORMAT:
- Code block first, explanation after
- Include file paths when creating new files
- Show both the code AND how to run it
- If debugging: show the fix, explain the root cause

CONSTRAINTS:
- Never use print() for debugging in production — use logging
- Never hardcode credentials or secrets
- Always handle errors gracefully
- Prefer standard library over external packages when possible""",

    "planner": """You are DASH Planner — DASH's task decomposition and project planning engine.

PERSONALITY:
- Methodical, organized, forward-thinking
- Break complex goals into clear, actionable steps
- Identify dependencies and blockers early

PLANNING STYLE:
- Start with the end goal
- Work backwards to identify prerequisites
- Group related tasks
- Estimate effort (S/M/L/XL)
- Identify risks and mitigations

OUTPUT FORMAT:
```
GOAL: [clear objective]
STEPS:
1. [task] — [effort] — [dependency]
2. [task] — [effort] — [dependency]
...
RISKS:
- [risk] → [mitigation]
```

CONSTRAINTS:
- Never skip error handling in the plan
- Always include a verification step
- Consider rollback strategies for destructive operations""",

    "research": """You are DASH Research — DASH's information gathering and analysis engine.

PERSONALITY:
- Thorough, curious, evidence-based
- Cite sources when possible
- Distinguish facts from opinions

RESEARCH STYLE:
- Start with a clear summary (1-2 sentences)
- Provide detailed analysis with evidence
- Include comparisons when relevant
- End with actionable recommendations

OUTPUT FORMAT:
**Summary:** [1-2 sentence overview]
**Analysis:** [detailed findings]
**Comparison:** [if applicable, table format]
**Recommendation:** [what to do next]

CONSTRAINTS:
- Never make up sources or statistics
- Clearly state when information is uncertain
- Prefer primary sources over secondary
- Update recommendations based on new data""",

    "executor": """You are DASH Executor — DASH's task execution engine.

PERSONALITY:
- Direct, action-oriented, results-focused
- Execute immediately, report results clearly
- No unnecessary explanations

EXECUTION STYLE:
- Parse the user's intent immediately
- Use available tools (filesystem, processes, browser, clipboard)
- Execute the action
- Report: what was done, result, any issues

OUTPUT FORMAT:
✅ [action completed]
📊 [result summary]
⚠️ [any issues or warnings]

CONSTRAINTS:
- Always confirm before destructive operations (delete, overwrite)
- Log all actions for audit trail
- Handle errors gracefully — never crash
- If an action fails, suggest an alternative""",
}


@dataclass
class SystemPromptConfig:
    """Configuration for system prompt injection."""
    mode: str = "general"
    custom_instructions: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    include_tools: bool = True
    include_memory: bool = True
    include_context: bool = True


class PromptEngine:
    """Manages system prompts for all agent modes."""

    def __init__(self):
        self._custom_prompts: dict[str, str] = {}
        self._custom_instructions: dict[str, str] = {}
        self._load_custom_prompts()

    def _load_custom_prompts(self):
        """Load custom prompts from config file."""
        config_path = Path(os.getenv("DASH_DATA_DIR", ".")) / "prompts.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    self._custom_prompts = data.get("prompts", {})
                    self._custom_instructions = data.get("instructions", {})
            except Exception as e:
                logger.warning("Failed to load custom prompts: %s", e)

    def get_system_prompt(self, mode: str, context: Optional[dict] = None) -> str:
        """Get the system prompt for a given agent mode."""
        base_prompt = self._custom_prompts.get(mode, AGENT_SYSTEM_PROMPTS.get(mode, AGENT_SYSTEM_PROMPTS["general"]))

        # Add custom instructions if any
        custom = self._custom_instructions.get(mode, "")
        if custom:
            base_prompt += f"\n\nCUSTOM INSTRUCTIONS:\n{custom}"

        # Add context if provided
        if context:
            context_str = self._build_context(context)
            if context_str:
                base_prompt += f"\n\nCURRENT CONTEXT:\n{context_str}"

        return base_prompt

    def _build_context(self, context: dict) -> str:
        """Build context string from system state."""
        parts = []
        if "system_metrics" in context:
            m = context["system_metrics"]
            parts.append(f"System: CPU {m.get('cpu', '?')}%, RAM {m.get('ram', '?')}%, Disk {m.get('disk', '?')}%")
        if "recent_files" in context:
            parts.append(f"Recent files: {', '.join(context['recent_files'][:5])}")
        if "active_apps" in context:
            parts.append(f"Running apps: {', '.join(context['active_apps'][:5])}")
        if "time" in context:
            parts.append(f"Time: {context['time']}")
        return "\n".join(parts)

    def set_custom_prompt(self, mode: str, prompt: str):
        """Set a custom system prompt for a mode."""
        self._custom_prompts[mode] = prompt
        self._save_custom_prompts()

    def set_custom_instructions(self, mode: str, instructions: str):
        """Add custom instructions to a mode."""
        self._custom_instructions[mode] = instructions
        self._save_custom_prompts()

    def _save_custom_prompts(self):
        """Save custom prompts to config file."""
        config_path = Path(os.getenv("DASH_DATA_DIR", ".")) / "prompts.json"
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump({
                    "prompts": self._custom_prompts,
                    "instructions": self._custom_instructions,
                }, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save custom prompts: %s", e)

    def get_config(self, mode: str) -> SystemPromptConfig:
        """Get default config for a mode."""
        configs = {
            "general": SystemPromptConfig(mode="general", temperature=0.7, max_tokens=2048),
            "coder": SystemPromptConfig(mode="coder", temperature=0.3, max_tokens=4096),
            "planner": SystemPromptConfig(mode="planner", temperature=0.5, max_tokens=2048),
            "research": SystemPromptConfig(mode="research", temperature=0.6, max_tokens=3072),
            "executor": SystemPromptConfig(mode="executor", temperature=0.2, max_tokens=1024),
        }
        return configs.get(mode, configs["general"])


# ═══════════════════════════════════════════════════════════════
# Level 2: RAG (Retrieval-Augmented Generation)
# ═══════════════════════════════════════════════════════════════

@dataclass
class DocumentChunk:
    """A chunk of text with embedding for RAG."""
    id: str
    content: str
    source: str  # file path or URL
    chunk_index: int
    embedding: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class RAGEngine:
    """Retrieval-Augmented Generation engine for DASH."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("DASH_RAG_DB", "dash_rag.db")
        self._chunks: list[DocumentChunk] = []
        self._initialized = False

    async def initialize(self):
        """Initialize the RAG engine with existing data."""
        if self._initialized:
            return
        # Load existing chunks from DB
        await self._load_chunks()
        self._initialized = True
        logger.info("RAG engine initialized with %d chunks", len(self._chunks))

    async def _load_chunks(self):
        """Load chunks from SQLite database."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    source TEXT,
                    chunk_index INTEGER,
                    embedding BLOB,
                    metadata TEXT
                )
            """)
            cursor.execute("SELECT id, content, source, chunk_index, embedding, metadata FROM rag_chunks")
            for row in cursor.fetchall():
                embedding = json.loads(row[4]) if row[4] else []
                metadata = json.loads(row[5]) if row[5] else {}
                self._chunks.append(DocumentChunk(
                    id=row[0], content=row[1], source=row[2],
                    chunk_index=row[3], embedding=embedding, metadata=metadata,
                ))
            conn.close()
        except Exception as e:
            logger.warning("Failed to load RAG chunks: %s", e)

    async def ingest_file(self, file_path: str, chunk_size: int = 500, overlap: int = 50) -> int:
        """Ingest a file into the RAG database."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            logger.warning("Failed to read file %s: %s", file_path, e)
            return 0

        # Split into chunks
        chunks = []
        words = content.split()
        for i in range(0, len(words), chunk_size - overlap):
            chunk_text = " ".join(words[i:i + chunk_size])
            chunk_id = hashlib.md5(f"{file_path}:{i}".encode()).hexdigest()
            chunks.append(DocumentChunk(
                id=chunk_id,
                content=chunk_text,
                source=file_path,
                chunk_index=i // (chunk_size - overlap),
            ))

        # Generate embeddings
        for chunk in chunks:
            chunk.embedding = await self._generate_embedding(chunk.content)

        # Store in database
        await self._store_chunks(chunks)
        self._chunks.extend(chunks)
        return len(chunks)

    async def ingest_directory(self, dir_path: str, extensions: Optional[list[str]] = None) -> int:
        """Ingest all files in a directory."""
        extensions = extensions or [".md", ".txt", ".py", ".ts", ".js", ".json", ".yaml", ".yml"]
        total_chunks = 0
        for root, dirs, files in os.walk(dir_path):
            # Skip hidden dirs and node_modules
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    chunks = await self.ingest_file(file_path)
                    total_chunks += chunks
        return total_chunks

    async def search(self, query: str, top_k: int = 5) -> list[DocumentChunk]:
        """Search for relevant chunks using cosine similarity."""
        query_embedding = await self._generate_embedding(query)

        # Calculate cosine similarity
        scored = []
        for chunk in self._chunks:
            if not chunk.embedding:
                continue
            similarity = self._cosine_similarity(query_embedding, chunk.embedding)
            scored.append((similarity, chunk))

        # Sort by similarity and return top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding using Ollama's nomic-embed-text model."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "http://127.0.0.1:11434/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text},
                )
                if response.status_code == 200:
                    return response.json().get("embedding", [])
        except Exception as e:
            logger.debug("Embedding generation failed: %s", e)
        return []

    async def _store_chunks(self, chunks: list[DocumentChunk]):
        """Store chunks in SQLite database."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    source TEXT,
                    chunk_index INTEGER,
                    embedding BLOB,
                    metadata TEXT
                )
            """)
            for chunk in chunks:
                cursor.execute(
                    "INSERT OR REPLACE INTO rag_chunks VALUES (?, ?, ?, ?, ?, ?)",
                    (chunk.id, chunk.content, chunk.source, chunk.chunk_index,
                     json.dumps(chunk.embedding), json.dumps(chunk.metadata)),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to store RAG chunks: %s", e)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b) or not a:
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)


# ═══════════════════════════════════════════════════════════════
# Level 3: LoRA Fine-Tuning (Training Pipeline)
# ═══════════════════════════════════════════════════════════════

@dataclass
class TrainingExample:
    """A single training example for LoRA fine-tuning."""
    instruction: str
    input: str
    output: str
    mode: str = "general"


class LoRATrainer:
    """LoRA fine-tuning pipeline for DASH."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.getenv("DASH_TRAINING_DIR", "dash_training")
        self.output_dir = os.path.join(self.data_dir, "lora_output")
        self.examples: list[TrainingExample] = []

    async def collect_conversations(self, db_path: str = "dash_dev.db") -> int:
        """Collect conversation history from the database for training."""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, created_at FROM messages
                WHERE role IN ('user', 'assistant', 'USER', 'ASSISTANT')
                ORDER BY created_at ASC
            """)
            rows = cursor.fetchall()
            conn.close()

            # Pair user/assistant messages (handle consecutive same-role, case-insensitive)
            examples = []
            i = 0
            while i < len(rows):
                if rows[i][0].lower() == "user":
                    # Find next assistant response
                    for j in range(i + 1, len(rows)):
                        if rows[j][0].lower() == "assistant":
                            user_text = rows[i][1]
                            assistant_text = rows[j][1]
                            # Skip error/timeout responses
                            if assistant_text and not assistant_text.startswith("I encountered an issue") and not assistant_text.startswith("I'm thinking about") and len(assistant_text) > 10:
                                examples.append(TrainingExample(
                                    instruction=user_text,
                                    input="",
                                    output=assistant_text,
                                ))
                            i = j + 1
                            break
                    else:
                        i += 1
                else:
                    i += 1

            self.examples = examples
            return len(examples)
        except Exception as e:
            logger.warning("Failed to collect conversations: %s", e)
            return 0

    def export_training_data(self, format: str = "alpaca") -> str:
        """Export training data in the specified format."""
        os.makedirs(self.data_dir, exist_ok=True)
        output_path = os.path.join(self.data_dir, f"training_data.{format}.json")

        if format == "alpaca":
            data = [
                {
                    "instruction": ex.instruction,
                    "input": ex.input,
                    "output": ex.output,
                }
                for ex in self.examples
            ]
        elif format == "chatml":
            data = [
                {
                    "messages": [
                        {"role": "user", "content": ex.instruction},
                        {"role": "assistant", "content": ex.output},
                    ]
                }
                for ex in self.examples
            ]
        else:
            data = [{"instruction": ex.instruction, "output": ex.output} for ex in self.examples]

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("Exported %d training examples to %s", len(self.examples), output_path)
        return output_path

    def generate_training_script(self, base_model: str = "llama3.2:1b") -> str:
        """Generate a Python script for LoRA fine-tuning using Unsloth."""
        script = f'''#!/usr/bin/env python3
"""
DASH LoRA Fine-Tuning Script
Uses Unsloth for efficient LoRA training on consumer hardware.

Requirements:
    pip install unsloth transformers datasets trl

Usage:
    python train_lora.py --epochs 3 --batch_size 4
"""

import argparse
import json
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="DASH LoRA Fine-Tuning")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--base_model", default="{base_model}")
    parser.add_argument("--training_data", default="{self.data_dir}/training_data.alpaca.json")
    parser.add_argument("--output_dir", default="{self.output_dir}")
    args = parser.parse_args()

    try:
        from unsloth import FastLanguageModel
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from datasets import load_dataset
    except ImportError:
        print("Install unsloth: pip install unsloth")
        return

    print(f"Loading base model: {{args.base_model}}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=2048,
        dtype=None,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.lora_alpha,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    dataset = load_dataset("json", data_files=args.training_data, split="train")

    def formatting_func(examples):
        texts = []
        for instruction, output in zip(examples["instruction"], examples["output"]):
            text = f"### Instruction:\\n{{instruction}}\\n\\n### Response:\\n{{output}}"
            texts.append(text)
        return {{"text": texts}}

    dataset = dataset.map(formatting_func, batched=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        args=TrainingArguments(
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=args.epochs,
            learning_rate=args.learning_rate,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            output_dir=args.output_dir,
            save_strategy="epoch",
            optim="adamw_8bit",
        ),
    )

    print("Starting training...")
    trainer.train()
    print(f"Training complete! Model saved to {{args.output_dir}}")

    # Export to GGUF for Ollama
    print("Exporting to GGUF...")
    model.save_pretrained_gguf(args.output_dir, tokenizer)

if __name__ == "__main__":
    import torch
    main()
'''
        script_path = os.path.join(self.data_dir, "train_lora.py")
        os.makedirs(self.data_dir, exist_ok=True)
        with open(script_path, "w") as f:
            f.write(script)
        return script_path


# ═══════════════════════════════════════════════════════════════
# Combined Fine-Tuning Manager
# ═══════════════════════════════════════════════════════════════

class FineTuningManager:
    """Manages all 3 levels of fine-tuning for DASH."""

    def __init__(self):
        self.prompt_engine = PromptEngine()
        self.rag_engine = RAGEngine()
        self.lora_trainer = LoRATrainer()

    async def initialize(self):
        """Initialize all fine-tuning systems."""
        await self.rag_engine.initialize()
        logger.info("Fine-tuning manager initialized")

    def get_enhanced_prompt(self, mode: str, query: str, context: Optional[dict] = None) -> str:
        """Get an enhanced system prompt with RAG context."""
        base_prompt = self.prompt_engine.get_system_prompt(mode, context)

        # TODO: Add RAG context here when search is wired
        # rag_results = await self.rag_engine.search(query)
        # if rag_results:
        #     context_str = "\\n\\nRELEVANT CONTEXT:\\n"
        #     for chunk in rag_results:
        #         context_str += f"- [{chunk.source}] {chunk.content[:200]}...\\n"
        #     base_prompt += context_str

        return base_prompt

    async def ingest_obsidian_vault(self, vault_path: Optional[str] = None) -> int:
        """Ingest the Obsidian vault into RAG."""
        vault_path = vault_path or os.getenv(
            "OBSIDIAN_VAULT_PATH",
            r"C:\Users\Asus\Documents\DASH-Vault\dash"
        )
        if not os.path.exists(vault_path):
            logger.warning("Obsidian vault not found at %s", vault_path)
            return 0
        return await self.rag_engine.ingest_directory(vault_path, [".md", ".txt"])

    async def ingest_code_repo(self, repo_path: str) -> int:
        """Ingest a code repository into RAG."""
        return await self.rag_engine.ingest_directory(repo_path, [".py", ".ts", ".js", ".jsx", ".tsx"])

    async def prepare_training_data(self) -> str:
        """Collect conversations and export training data."""
        count = await self.lora_trainer.collect_conversations()
        if count == 0:
            logger.warning("No conversations found for training")
            return ""
        return self.lora_trainer.export_training_data()

    def get_status(self) -> dict:
        """Get the current status of all fine-tuning systems."""
        return {
            "level1_prompt": {
                "status": "active",
                "modes": list(AGENT_SYSTEM_PROMPTS.keys()),
                "custom_prompts": len(self.prompt_engine._custom_prompts),
            },
            "level2_rag": {
                "status": "initialized" if self.rag_engine._initialized else "not_initialized",
                "chunks": len(self.rag_engine._chunks),
            },
            "level3_lora": {
                "status": "ready",
                "examples": len(self.lora_trainer.examples),
                "training_data": os.path.exists(os.path.join(self.lora_trainer.data_dir, "training_data.alpaca.json")),
            },
        }


# Singleton
_manager: Optional[FineTuningManager] = None


def get_fine_tuning_manager() -> FineTuningManager:
    global _manager
    if _manager is None:
        _manager = FineTuningManager()
    return _manager
