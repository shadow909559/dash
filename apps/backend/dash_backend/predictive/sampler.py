"""Background device sampler for predictive problem detection.

Records periodic CPU / RAM / disk samples so the predictive engine has
enough history to produce honest trend projections (e.g. "disk is filling
at X GB/day").  The sampler is a lightweight async task started by the
FastAPI lifespan and cancelled on shutdown.

Key properties:
- Never raises (best-effort logging on failure)
- Runs every `interval_seconds` (default 300 = 5 minutes)
- Reads only the fields the predictive predictors actually use
- Uses the same SampleStore the predictive engine writes to, so endpoint
  calls and the background sampler share one history file
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from dash_backend.logging_config import get_logger
from dash_backend.predictive.history import SampleStore

logger = get_logger(__name__)

_DEFAULT_INTERVAL = 300  # 5 minutes


def _collect_sample() -> Optional[dict]:
    """Read current device metrics via psutil.  Never raises.

    Returns a dict matching the SampleStore schema, or None if psutil
    is unavailable.
    """
    try:
        import psutil  # type: ignore[import-untyped]

        sample: dict = {"ts": time.time()}
        sample["cpu_pct"] = round(psutil.cpu_percent(interval=0.1), 1)

        mem = psutil.virtual_memory()
        sample["ram_pct"] = round(mem.percent, 1)

        try:
            disk = psutil.disk_usage("/")
            sample["disk_pct"] = round(disk.percent, 1)
            sample["disk_free_gb"] = round(disk.free / (1024 ** 3), 1)
        except Exception:
            pass  # disk may not be available on all platforms

        return sample
    except ImportError:
        logger.debug("psutil not installed; device sampler disabled")
        return None
    except Exception as exc:
        logger.debug("Device sample collection failed: %s", exc)
        return None


class DeviceSampler:
    """Periodically samples device metrics into the predictive history store.

    Usage::

        sampler = DeviceSampler()
        task = asyncio.create_task(sampler.run())
        # ... later, on shutdown:
        sampler.stop()
        task.cancel()
    """

    def __init__(
        self,
        interval_seconds: float = _DEFAULT_INTERVAL,
        store: Optional[SampleStore] = None,
    ) -> None:
        self._interval = interval_seconds
        self._store = store or SampleStore()
        self._stop = asyncio.Event()

    async def run(self) -> None:
        """Main loop.  Runs until stop() is called or the task is cancelled."""
        logger.info(
            "Device sampler started (interval=%ds)", int(self._interval)
        )
        # Take one immediate sample on startup so the history is not empty.
        self._tick()
        while not self._stop.is_set():
            # Use asyncio.sleep (cooperative) so other tasks interleave.
            # Check the stop event in small increments so shutdown is responsive.
            elapsed = 0.0
            while elapsed < self._interval and not self._stop.is_set():
                chunk = min(1.0, self._interval - elapsed)
                await asyncio.sleep(chunk)
                elapsed += chunk
            if not self._stop.is_set():
                self._tick()
        logger.info("Device sampler stopped")

    def _tick(self) -> None:
        """Collect one sample and persist it."""
        sample = _collect_sample()
        if sample is not None:
            self._store.append(sample)

    def stop(self) -> None:
        """Signal the run loop to exit after the current interval."""
        self._stop.set()


_sampler: Optional[DeviceSampler] = None
_sampler_task: Optional[asyncio.Task] = None


def get_device_sampler() -> DeviceSampler:
    """Return the global sampler singleton."""
    global _sampler
    if _sampler is None:
        _sampler = DeviceSampler()
    return _sampler


def start_device_sampler() -> Optional[asyncio.Task]:
    """Start the background sampler.  Called from the FastAPI lifespan."""
    global _sampler_task
    sampler = get_device_sampler()
    _sampler_task = asyncio.create_task(sampler.run())
    return _sampler_task


def stop_device_sampler() -> None:
    """Stop the background sampler.  Called from the FastAPI lifespan shutdown."""
    global _sampler, _sampler_task
    if _sampler is not None:
        _sampler.stop()
    _sampler = None
    _sampler_task = None
