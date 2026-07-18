"""Bounded executor for synchronous work called from async code."""

import asyncio
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
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
_waiters_lock = threading.Lock()
_waiters: deque[Future[None]] = deque()


async def _acquire_capacity() -> None:
    """Acquire one slot fairly without polling or storing loop-bound state."""
    with _waiters_lock:
        if not _waiters and _capacity.acquire(blocking=False):
            return
        waiter: Future[None] = Future()
        _waiters.append(waiter)

    wrapped_waiter = asyncio.wrap_future(waiter)
    try:
        # Shield the concurrent waiter so cancellation cleanup remains under
        # ``_waiters_lock`` instead of racing Future.cancel from asyncio.
        await asyncio.shield(wrapped_waiter)
    except asyncio.CancelledError:
        with _waiters_lock:
            try:
                _waiters.remove(waiter)
            except ValueError:
                # The slot was already handed to this waiter.  Transfer it so
                # cancellation between grant and submission cannot leak it.
                _grant_next_or_release_locked()
            else:
                waiter.cancel()
        raise


def _grant_next_or_release_locked() -> None:
    """Transfer a slot to the oldest live waiter; caller owns the lock."""
    while _waiters:
        waiter = _waiters.popleft()
        if waiter.cancelled() or waiter.done():
            continue
        waiter.set_result(None)
        return
    _capacity.release()


def _release_capacity(_future: object) -> None:
    """Return or fairly transfer one slot after a future terminates."""
    with _waiters_lock:
        _grant_next_or_release_locked()


async def run_blocking(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run ``func`` in the shared bounded thread pool."""
    await _acquire_capacity()
    try:
        future = _executor.submit(partial(func, *args, **kwargs))
    except BaseException:
        # No concurrent future exists to own the acquired slot.
        _release_capacity(None)
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
