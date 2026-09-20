"""Generated soak boot: isolated DASH backend on :8015."""
import os, sys
from pathlib import Path

STATE = Path(r"C:/Users/Asus/AppData/Local/Temp/dash_soak_run/state")
STATE.mkdir(parents=True, exist_ok=True)
os.environ["DASH_DATABASE_URL"] = f"sqlite+aiosqlite:///{(STATE / 'dash.db').as_posix()}"
os.environ["DASH_WORKFLOW_STATE"] = str(STATE / "workflow_state.json")
os.environ["DASH_GUARDIAN_ENABLED"] = "0"
os.environ["DASH_VISION_WATCHER_ENABLED"] = "0"
os.environ["DASH_AUDIT_LOG_DIR"] = str(STATE / "audit_logs")
os.environ["DASH_CORS_ORIGINS_RAW"] = "http://localhost:5188,http://127.0.0.1:5188,*"
REPO = Path(r"C:/Users/Asus/Desktop/dash/apps")
sys.path.insert(0, str(REPO / "apps" / "backend"))
os.chdir(REPO / "apps" / "backend")

import uvicorn
from dash_backend.main import create_app
uvicorn.run(create_app(), host="127.0.0.1", port=8015, log_level="warning")
