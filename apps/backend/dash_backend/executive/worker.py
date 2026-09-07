from __future__ import annotations

import asyncio
from dash_backend.executive.service import worker_loop
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Executive worker terminated by KeyboardInterrupt")
