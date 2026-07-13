# DASH Backend

FastAPI backend for the DASH AI assistant.

## Development

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
uvicorn dash_backend.main:app --reload
```

## Endpoints

- `GET /api/v1/health` — Health check
- `WS /api/v1/ws` — Basic WebSocket echo
