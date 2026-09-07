# DASH Orchestration Pipeline

The orchestrator is the central nervous system of DASH AI OS. It routes every user request through the full cognitive pipeline:

```
User -> Chat -> Brain -> Executive -> Planner -> Skill -> Tool -> Result -> Memory -> User
```

## Architecture

```
orchestrator/
  __init__.py             - Package exports
  pipeline.py             - Main orchestration pipeline
  master_orchestrator.py  - Master Orchestrator (decompose → agents → parallel → merge)
  decision_engine.py      - Query analysis and path selection
  task_planner.py         - Advanced goal decomposition + parallel layers
  execution_graph.py      - DAG-based task execution
  tool_chain.py           - Multi-tool chaining with output passing
  retry_manager.py        - Retry logic with exponential backoff
```

## Master Orchestrator

The Master Orchestrator (`master_orchestrator.py`) is the top-level coordination
layer for complex, multi-step requests. It is purely additive and integrates the
existing planner, agents, tools, and brain:

    Request
      → DecisionEngine (reason about intent / required agents)
      → TaskPlanner (decompose into dependency layers)
      → Agent role assignment (coding / research / planning / desktop / browser /
        memory / execution)
      → Parallel execution (asyncio.gather within a layer)
      → Merge results (BrainService) → natural response
      → Self-reflection (log learnings)

### Usage

```python
from dash_backend.orchestrator import get_master_orchestrator

orchestrator = get_master_orchestrator()
async for event in orchestrator.run(
    request="Find my resume, improve it, convert to PDF and email it.",
    user_id="user-123",
):
    # event.type in (orchestrator.reasoning, orchestrator.plan_created,
    #                orchestrator.task_completed, orchestrator.completed, ...)
    print(event.type, event.data)
```

The orchestrator never hardcodes workflows — it reasons about each request,
decomposes it, assigns agents, and coordinates execution. Independent agents run
in parallel within a dependency layer, and results are merged into a short,
natural response (internal reasoning is not exposed).

## Pipeline Flow

1. **User sends a message** via WebSocket or REST API
2. **Pipeline receives the query** with context (history, memory, RAG, tools)
3. **Decision Engine** analyzes the query to select the optimal path:
   - `direct_answer` - Simple Q&A, greetings
   - `memory_only` - Query requires memory retrieval
   - `rag_only` - Query requires document retrieval  
   - `tool_only` - Query requires tool execution
   - `planner` - Complex multi-step task
   - `clarification` - Ambiguous query
   - `combined` - Multiple sources needed
4. **Execution** follows the selected path:
   - For tools: Dynamic selection, execution with retry, result formatting
   - For planner: Task decomposition -> Execution graph -> Parallel execution -> Result aggregation
   - For memory/RAG: Automatic retrieval -> Context injection -> Answer generation
5. **Post-processing**: Automatic memory storage, conversation summarization
6. **Result streamed back** to the client via WebSocket events

## Key Components

### DecisionEngine
Analyzes queries using keyword matching and LLM fallback to determine:
- Complexity (1-10 scale)
- Tool requirements  
- Memory relevance
- RAG relevance
- Ambiguity

### ExecutionGraph  
DAG-based task scheduler supporting:
- Dependency resolution between tasks
- Parallel execution layers
- Output passing between dependent tasks
- Automatic retry on failure
- Circuit breaker for stuck tasks

### ToolChain
Chains multiple tool executions:
- Sequential execution with output passing
- Template resolution (`{{key}}` syntax)
- Conditional branching based on results
- Fallback tools on failure
- Per-step timeout

### RetryManager
Configurable retry policies:
- Exponential backoff with jitter
- Linear and constant delay strategies
- Circuit breaker pattern
- Fallback strategies (default, function call, skip)
- Per-operation type policies (tool, LLM, memory, RAG)

## Integration

The pipeline is integrated into the WebSocket chat handler (`handle_chat_send`) and replaces the previous direct LLM + tool manager approach with a full cognitive pipeline that makes DASH behave like an autonomous AI assistant rather than a simple chatbot.

