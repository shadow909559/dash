"""Generated bench boot: isolated DASH backend for latency benchmarking.

Usage: python scripts/_bench_boot.py <port> <state-dir-name>
"""
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8017
STATE = Path = __import__("pathlib").Path(
    os.environ.get(
        "DASH_BENCH_STATE",
        rf"C:/Users/Asus/AppData/Local/Temp/dash_bench_{PORT}/state",
    )
)
STATE.mkdir(parents=True, exist_ok=True)
os.environ["DASH_DATABASE_URL"] = f"sqlite+aiosqlite:///{(STATE / 'dash.db').as_posix()}"
os.environ["DASH_WORKFLOW_STATE"] = str(STATE / "workflow_state.json")
os.environ["DASH_TASK_STATE"] = str(STATE / "task_state.json")
os.environ.setdefault("DASH_FILES_SANDBOX", str(STATE / "sandbox"))  # isolated FS writes
os.environ.setdefault("DASH_TASK_MODEL", "llama3.2:1b")  # structured-task JSON on 7.4GB RAM
os.environ["DASH_GUARDIAN_ENABLED"] = "0"
os.environ["DASH_BRAIN_AUTONOMY"] = "0"
os.environ["DASH_VISION_WATCHER_ENABLED"] = "0"
os.environ["DASH_WAKE_LOOP_ENABLED"] = "0"
os.environ["DASH_AUDIT_LOG_DIR"] = str(STATE / "audit_logs")
os.environ["DASH_BRAIN_BACKEND_URL"] = f"http://127.0.0.1:{PORT}/health"
os.environ["DASH_IDENTITY_FILE"] = str(STATE / "identity.json")
os.environ["DASH_CORS_ORIGINS_RAW"] = "http://localhost:5188,http://127.0.0.1:5188,*"
REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import uvicorn  # noqa: E402

from dash_backend.main import create_app  # noqa: E402

uvicorn.run(create_app(), host="127.0.0.1", port=PORT, log_level="warning")
