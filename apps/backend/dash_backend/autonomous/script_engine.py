"""Natural Language Script Engine — parse intent, write script, schedule or run.

Converts natural language requests like:
- "Every Friday at 5pm, back up my project folder"
- "When a new file appears in Downloads, organize it"
- "Every morning, check system health and report"

Into executable Python scripts that DASH can run or schedule.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ScriptIntent:
    """Parsed intent from a natural language request."""
    trigger: str  # "once", "daily", "interval", "watch"
    schedule: str  # "08:00", "3600", etc.
    action: str  # description of what to do
    target: str  # file/directory/service target
    confidence: float


# ── Intent patterns ──────────────────────────────────────────────

_INTENT_PATTERNS: list[tuple[str, str, str, float]] = [
    # Daily at specific time
    (r"every\s+day\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", "daily", "high", 0.9),
    (r"every\s+morning\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", "daily", "high", 0.9),
    (r"daily\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", "daily", "high", 0.9),
    
    # Weekly
    (r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", "weekly", "high", 0.85),
    
    # Interval
    (r"every\s+(\d+)\s+(minutes?|hours?|mins?)", "interval", "high", 0.9),
    (r"every\s+(\d+)\s+seconds?", "interval", "medium", 0.8),
    
    # File watch
    (r"when\s+(?:a\s+)?(?:new\s+)?file\s+(?:appears?|is\s+added|shows?\s+up)\s+(?:in|to)\s+(.+)", "watch", "high", 0.85),
    (r"watch\s+(.+)\s+for\s+(?:new\s+)?files?", "watch", "high", 0.85),
    
    # Once (immediately)
    (r"^(?:now|immediately|right\s+now|asap)$", "once", "high", 0.9),
    (r"^run\s+(.+)", "once", "high", 0.85),
]


def parse_intent(request: str) -> ScriptIntent | None:
    """Parse a natural language request into a script intent."""
    text = request.strip().lower()
    
    for pattern, trigger, _, confidence in _INTENT_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return ScriptIntent(
                trigger=trigger,
                schedule=_extract_schedule(trigger, m),
                action=text,
                target=m.group(1) if m.groups() else "",
                confidence=confidence,
            )
    
    return None


def _extract_schedule(trigger: str, match: re.Match) -> str:
    """Extract schedule string from regex match."""
    if trigger == "daily":
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        ampm = match.group(3) if match.lastindex and match.lastindex >= 3 else None
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"
    elif trigger == "interval":
        value = int(match.group(1))
        unit = match.group(2)
        if "hour" in unit:
            return str(value * 3600)
        elif "min" in unit:
            return str(value * 60)
        else:
            return str(value)
    return ""


# ── Script templates ─────────────────────────────────────────────

_SCRIPT_TEMPLATES: dict[str, str] = {
    "backup": '''
import shutil
import os
from datetime import datetime
from pathlib import Path

src = Path("{source}")
dst = Path("{dest}") / f"backup_{{datetime.now().strftime('%Y%m%d_%H%M%S')}}"
if src.is_dir():
    shutil.copytree(src, dst)
    print(f"Backed up {{src}} to {{dst}}")
elif src.is_file():
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Backed up {{src}} to {{dst}}")
else:
    print(f"Source not found: {{src}}")
''',
    "cleanup": '''
import os
from pathlib import Path
from datetime import datetime, timedelta

target = Path("{target}")
cutoff = datetime.now() - timedelta(days={days})
removed = 0
freed = 0

for f in target.rglob("*"):
    if f.is_file() and f.stat().st_mtime < cutoff.timestamp():
        size = f.stat().st_size
        f.unlink()
        removed += 1
        freed += size

print(f"Removed {{removed}} files, freed {{freed / 1024 / 1024:.1f}}MB")
''',
    "health_check": '''
import psutil
import json

cpu = psutil.cpu_percent(interval=1)
ram = psutil.virtual_memory()
disk = psutil.disk_usage("/")

report = {
    "cpu_percent": cpu,
    "ram_percent": ram.percent,
    "disk_percent": disk.percent,
    "disk_free_gb": round(disk.free / (1024**3), 1),
    "status": "healthy" if cpu < 80 and ram.percent < 85 else "warning",
}
print(json.dumps(report, indent=2))
''',
    "organize": '''
import shutil
from pathlib import Path

source = Path("{target}")
categories = {{
    "Documents": {{".pdf", ".doc", ".docx", ".txt", ".csv"}},
    "Images": {{".jpg", ".png", ".gif", ".svg"}},
    "Videos": {{".mp4", ".mkv", ".avi", ".mov"}},
    "Audio": {{".mp3", ".wav", ".flac"}},
    "Archives": {{".zip", ".rar", ".7z"}},
    "Code": {{".py", ".js", ".ts", ".go", ".rs"}},
}}

organized = 0
for f in source.iterdir():
    if f.is_file():
        ext = f.suffix.lower()
        for cat, exts in categories.items():
            if ext in exts:
                target_dir = source / cat
                target_dir.mkdir(exist_ok=True)
                shutil.move(str(f), str(target_dir / f.name))
                organized += 1
                break

print(f"Organized {{organized}} files into categories")
''',
}


def generate_script(intent: ScriptIntent) -> str:
    """Generate a Python script based on the parsed intent."""
    action = intent.action.lower()
    
    if "backup" in action:
        source = intent.target or str(__import__("pathlib").Path.home() / "Desktop")
        dest = str(__import__("pathlib").Path.home() / "Desktop" / "dash_backups")
        return _SCRIPT_TEMPLATES["backup"].format(source=source, dest=dest)
    elif "clean" in action or "remove" in action or "delete" in action:
        target = intent.target or str(__import__("pathlib").Path.home() / "AppData" / "Local" / "Temp")
        return _SCRIPT_TEMPLATES["cleanup"].format(target=target, days=7)
    elif "health" in action or "status" in action or "check" in action:
        return _SCRIPT_TEMPLATES["health_check"]
    elif "organize" in action or "sort" in action:
        target = intent.target or str(__import__("pathlib").Path.home() / "Downloads")
        return _SCRIPT_TEMPLATES["organize"].format(target=target)
    else:
        # Generic script
        return f'''# Auto-generated script for: {intent.action}
import os
import json
from pathlib import Path
from datetime import datetime

print(f"Script executed at {{datetime.now()}}")
print(f"Intent: {intent.action}")
print(f"Target: {intent.target}")
'''
