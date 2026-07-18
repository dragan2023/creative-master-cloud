"""Bounded executor for synchronous work called from async code."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import threading
from typing import Any, Callable, TypeVar


T = TypeVar("T")

BLOCKING_MAX_WORKERS = 4
BLOCKING_MAX_PENDING = 8

# Backwards-compatible name used by existing callers and tests.
BLOCKING_CONCURRENCY_LIMIT = BLOCKING_MAX_WORKERS

_executor = ThreadPoolExecutor(
    max_workers=BLOCKING_MAX_WORKERS,
    thread_name_prefix="blocking",
)
_capacity = threading.BoundedSemaphore(
    BLOCKING_MAX_WORKERS + BLOCKING_MAX_PENDING
)


async def _acquire_capacity() -> None:
    """Wait for a submission slot without blocking the event-loop thread."""
    while not _capacity.acquire(blocking=False):
        await asyncio.sleep(0)


def _release_capacity(_future: object) -> None:
    """Return one slot after its concurrent future reaches a terminal state."""
    _capacity.release()


async def run_blocking(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run ``func`` in the shared bounded thread pool."""
    await _acquire_capacity()
    try:
        future = _executor.submit(partial(func, *args, **kwargs))
    except BaseException:
        # No concurrent future exists to own the acquired slot.
        _capacity.release()
        raise

    future.add_done_callback(_release_capacity)
    try:
        return await asyncio.wrap_future(future)
    except asyncio.CancelledError:
        future.cancel()
        raise


__all__ = [
    "run_blocking",
    "BLOCKING_MAX_WORKERS",
    "BLOCKING_MAX_PENDING",
    "BLOCKING_CONCURRENCY_LIMIT",
]
