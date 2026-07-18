"""Behavioral tests for the shared bounded blocking executor."""

import asyncio
import threading

import pytest

from app.core import blocking_executor
from app.core.blocking_executor import run_blocking


async def _wait_until(predicate, timeout: float = 1.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_heartbeat_runs_while_sync_task_is_blocked():
    release = threading.Event()
    started = threading.Event()
    heartbeat_ran = asyncio.Event()

    def blocking_task() -> str:
        started.set()
        release.wait()
        return "done"

    task = asyncio.create_task(run_blocking(blocking_task))
    try:
        assert await asyncio.to_thread(started.wait, 1.0)
        await asyncio.sleep(0)
        heartbeat_ran.set()
        assert heartbeat_ran.is_set()
    finally:
        release.set()

    assert await task == "done"


@pytest.mark.asyncio
async def test_cancelling_callers_does_not_exceed_real_worker_limit():
    """Cancelling awaiters must not release capacity while workers still run."""
    lock = threading.Lock()
    first_wave_started = threading.Event()
    release_workers = threading.Event()
    state = {"current": 0, "max_seen": 0, "started": 0}

    def tracked_task() -> None:
        with lock:
            state["current"] += 1
            state["started"] += 1
            state["max_seen"] = max(state["max_seen"], state["current"])
            if state["started"] >= 4:
                first_wave_started.set()
        release_workers.wait()
        with lock:
            state["current"] -= 1

    first_wave = [asyncio.create_task(run_blocking(tracked_task)) for _ in range(4)]
    second_wave = []
    try:
        assert await asyncio.to_thread(first_wave_started.wait, 1.0)

        for task in first_wave:
            task.cancel()
        cancelled = await asyncio.gather(*first_wave, return_exceptions=True)
        assert all(isinstance(item, asyncio.CancelledError) for item in cancelled)

        second_wave = [
            asyncio.create_task(run_blocking(tracked_task)) for _ in range(4)
        ]
        await asyncio.sleep(0)
        await asyncio.to_thread(lambda: None)
    finally:
        release_workers.set()
        await asyncio.gather(*second_wave, return_exceptions=True)

    assert state["started"] == 8
    assert state["max_seen"] <= blocking_executor.BLOCKING_MAX_WORKERS
    assert state["current"] == 0


@pytest.mark.asyncio
async def test_executor_can_be_used_by_three_sequential_asyncio_runs():
    def use_three_event_loops():
        return [
            asyncio.run(run_blocking(lambda item=value: item))
            for value in range(3)
        ]

    assert await asyncio.to_thread(use_three_event_loops) == [0, 1, 2]


@pytest.mark.asyncio
async def test_more_than_total_capacity_keeps_loop_responsive_and_queue_bounded(
    monkeypatch,
):
    release = threading.Event()
    first_workers_started = threading.Event()
    twelve_submitted = threading.Event()
    lock = threading.Lock()
    state = {"current": 0, "max_seen": 0, "started": 0, "submitted": 0}
    original_submit = blocking_executor._executor.submit

    def recording_submit(*args, **kwargs):
        future = original_submit(*args, **kwargs)
        with lock:
            state["submitted"] += 1
            if state["submitted"] == 12:
                twelve_submitted.set()
        return future

    monkeypatch.setattr(blocking_executor._executor, "submit", recording_submit)

    def tracked_task(value: int) -> int:
        with lock:
            state["current"] += 1
            state["started"] += 1
            state["max_seen"] = max(state["max_seen"], state["current"])
            if state["started"] == 4:
                first_workers_started.set()
        release.wait()
        with lock:
            state["current"] -= 1
        return value

    tasks = [asyncio.create_task(run_blocking(tracked_task, i)) for i in range(13)]
    heartbeat_ticks = 0

    async def heartbeat() -> None:
        nonlocal heartbeat_ticks
        while not twelve_submitted.is_set():
            heartbeat_ticks += 1
            await asyncio.sleep(0)
        heartbeat_ticks += 1

    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        assert await asyncio.to_thread(first_workers_started.wait, 1.0)
        assert await asyncio.to_thread(twelve_submitted.wait, 1.0)
        await heartbeat_task
        await asyncio.sleep(0)

        assert heartbeat_ticks > 0
        assert state["submitted"] == (
            blocking_executor.BLOCKING_MAX_WORKERS
            + blocking_executor.BLOCKING_MAX_PENDING
        )
        assert blocking_executor._executor._work_queue.qsize() <= (
            blocking_executor.BLOCKING_MAX_PENDING
        )
    finally:
        release.set()

    assert await asyncio.gather(*tasks) == list(range(13))
    assert state["started"] == 13
    assert state["max_seen"] <= blocking_executor.BLOCKING_MAX_WORKERS


@pytest.mark.asyncio
async def test_cancelling_queued_future_prevents_sync_call(monkeypatch):
    release = threading.Event()
    first_workers_started = threading.Event()
    lock = threading.Lock()
    started = 0
    queued_function_ran = threading.Event()
    submitted_futures = []
    original_submit = blocking_executor._executor.submit

    def recording_submit(*args, **kwargs):
        future = original_submit(*args, **kwargs)
        submitted_futures.append(future)
        return future

    monkeypatch.setattr(blocking_executor._executor, "submit", recording_submit)

    def occupy_worker() -> None:
        nonlocal started
        with lock:
            started += 1
            if started == blocking_executor.BLOCKING_MAX_WORKERS:
                first_workers_started.set()
        release.wait()

    workers = [
        asyncio.create_task(run_blocking(occupy_worker))
        for _ in range(blocking_executor.BLOCKING_MAX_WORKERS)
    ]
    queued_task = None
    try:
        assert await asyncio.to_thread(first_workers_started.wait, 1.0)
        queued_task = asyncio.create_task(run_blocking(queued_function_ran.set))
        await _wait_until(lambda: len(submitted_futures) == 5)

        queued_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued_task

        assert submitted_futures[-1].cancelled()
        assert not queued_function_ran.is_set()
    finally:
        release.set()
        await asyncio.gather(*workers)
        if queued_task is not None and not queued_task.done():
            queued_task.cancel()


@pytest.mark.asyncio
async def test_sync_exception_return_value_and_kwargs_are_preserved():
    marker = object()

    def combine(base: str, *, suffix: str):
        if base == "raise":
            raise ValueError("parse failed")
        return marker, f"{base}-{suffix}"

    result = await run_blocking(combine, "doc", suffix="parsed")
    assert result == (marker, "doc-parsed")

    with pytest.raises(ValueError, match="parse failed"):
        await run_blocking(combine, "raise", suffix="ignored")


@pytest.mark.asyncio
async def test_completed_future_releases_capacity_exactly_once(monkeypatch):
    class RecordingCapacity:
        def __init__(self):
            self.release_count = 0

        def acquire(self, *, blocking):
            assert blocking is False
            return True

        def release(self):
            self.release_count += 1

    capacity = RecordingCapacity()
    monkeypatch.setattr(blocking_executor, "_capacity", capacity)

    assert await run_blocking(lambda: "value") == "value"
    assert capacity.release_count == 1
