Executive subsystem
===================

Overview
--------
The Executive subsystem provides goal/task persistence, a worker that claims and executes tasks using registered Skills, and execution history for audit and diagnostics.

Key components
--------------
- models.py: SQLAlchemy models (Goal, Task, ExecutionHistory, Approval)
- service.py: Executive runtime (create/decompose/start tasks, worker loop, heartbeating, stuck task reset)
- planner.py: LLM-backed Planner abstraction to decompose goals into subtasks (with a heuristic fallback)
- router.py: FastAPI endpoints for creating/listing/starting goals and admin endpoints for operational tasks
- worker.py: CLI entrypoint for running the worker loop as a background process
- alembic/versions/*: Migrations to create executive tables and add FK/claim columns

Running migrations
------------------
1. Ensure you have a staging PostgreSQL database and the DASH_ environment variables set in your environment or .env file.
2. Confirm settings.database_url is set to a valid SQLAlchemy async URL (e.g., postgresql+asyncpg://user:pass@host:5432/dbname)
3. From the repository root, run:

    alembic upgrade head

Note: Alembic will use the application's alembic configuration. If you need to override the DB URL for a one-off run, set the DASH_DATABASE_URL env var accordingly.

Worker deployment
-----------------
- Development: run the worker in a terminal (recommended for testing):

    python -m apps.backend.dash_backend.executive.worker

- Windows (NSSM): see scripts/worker_service_windows.ps1 for an example NSSM install script.
- Linux (systemd): see scripts/worker_service_systemd.service for a service unit example. Copy to /etc/systemd/system/ and enable/start the service.

Operational endpoints
---------------------
- GET /api/v1/executive/admin/claimed-tasks  -- list currently claimed tasks and heartbeats
- POST /api/v1/executive/admin/reset-stuck   -- reset stuck tasks (stale heartbeats) to pending

Planner
-------
Planner.decompose uses the configured LLM provider via dash_backend.llm.service.collect_streamed_response. Planner expects the model to return a JSON array of task objects. The planner will fall back to a heuristic sentence-splitting decomposition if the model is unavailable or the response cannot be parsed.

Testing
-------
- Unit tests for the Planner are located under apps/backend/dash_backend/tests/test_executive_planner.py
- Integration tests for end-to-end goal->task->worker runs require a staging DB. Use the test DB configuration in your CI to run integration tests.

Security
--------
- The worker executes tasks by routing to registered Skills which must use ToolManager/ToolExecutor for all potentially dangerous operations. Do not bypass ToolManager.
- Approvals persist and can be consumed via existing approvals endpoints for confirmation flows.

Support
-------
Contact the project maintainer for deployment assistance and to provide staging DB credentials for CI integration.