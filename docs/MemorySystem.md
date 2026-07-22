# Memory System

## Overview

DASH's memory system extracts, stores, and retrieves semantic information from conversations.

## Architecture

```
Conversation -> Memory Extraction -> Importance Scoring -> Storage
                                                              |
User Query -> Semantic Search -> Rank Results -> LLM Context
```

## Key Components

### Memory Service

- `add_memory()`: Store a new memory with importance score
- `search_memories()`: Semantic search across memories
- `get_recent_memories()`: Recent memories for context
- `get_important_memories()`: High-importance memories
- `summarize_conversation()`: Generate extractive summaries
- `extract_memories_from_conversation()`: Auto-extract key facts
- `build_memory_context()`: Build context string for LLM prompts
- `prune_memories()`: Remove low-importance old memories

### Memory Model

```python
class Memory(Base):
    id: UUID
    user_id: UUID (FK -> users)
    content: str
    category: str (fact, preference, project, person, etc.)
    importance: float (0.0 - 1.0)
    source_conversation_id: UUID (optional)
    last_accessed: datetime
    access_count: int
    created_at: datetime
    updated_at: datetime
```

## Memory Categories

| Category | Description | Example |
|----------|-------------|---------|
| `fact` | General facts about user | "User works at Acme Corp" |
| `preference` | User preferences | "User prefers dark mode" |
| `project` | Project information | "Working on DASH project" |
| `person` | People mentioned | "John is the team lead" |
| `goal` | User goals | "Wants to learn Rust" |
| `code` | Coding preferences | "Uses Python with type hints" |
| `personal` | Personal details | "Lives in New York" |
| `plugin` | Plugin-created memories | (varies) |

## Importance Scoring

- **1.0**: Critical (user identity, security preferences)
- **0.8**: Important (ongoing projects, key preferences)
- **0.5**: Normal (casual facts)
- **0.2**: Low (transient details)
- **0.0**: Deprecated (pruned automatically)

## Pruning

- Memories with importance < 0.1 older than 30 days
- Duplicate memories (content similarity > 90%)
- Low-importance memories when count exceeds 1000

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/memories` | List memories |
| POST | `/api/v1/memories` | Create memory |
| GET | `/api/v1/memories/search` | Search memories |
| GET | `/api/v1/memories/{id}` | Get memory |
| PUT | `/api/v1/memories/{id}` | Update memory |
| DELETE | `/api/v1/memories/{id}` | Delete memory |
