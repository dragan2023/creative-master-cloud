"""The async upload handler must not copy large files on the event loop."""

import asyncio
from io import BytesIO
import importlib
from types import SimpleNamespace
import threading

import pytest


upload_module = importlib.import_module(
    "app.api.v1.endpoints.knowledge._upload"
)


class StopAfterCopy(RuntimeError):
    pass


class RequestOwnedStream(BytesIO):
    """Model FastAPI closing UploadFile as soon as the handler task finishes."""

    pass


class FakeUploadDB:
    def __init__(
        self,
        *,
        commit_error=None,
        refresh_error=None,
        rollback_error=None,
        block_commit=False,
    ):
        self.commit_error = commit_error
        self.refresh_error = refresh_error
        self.rollback_error = rollback_error
        self.block_commit = block_commit
        self.commit_started = asyncio.Event()
        self.commit_release = asyncio.Event()
        self.rollback_count = 0
        self.commit_count = 0
        self.added = []

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commit_count += 1
        self.commit_started.set()
        if self.block_commit:
            await self.commit_release.wait()
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self):
        self.rollback_count += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    async def refresh(self, value):
        if self.refresh_error is not None:
            raise self.refresh_error
        value.id = 101


def _configure_upload_test(monkeypatch, tmp_path):
    monkeypatch.setattr(upload_module, "kb_processing_progress", {})
    monkeypatch.setattr(
        upload_module,
        "settings",
        SimpleNamespace(
            ALLOWED_EXTENSIONS={".txt"},
            MAX_UPLOAD_SIZE=1024,
            get_chroma_dir=lambda: str(tmp_path),
        ),
    )


def _start_upload(db):
    upload = SimpleNamespace(filename="notes.txt", size=7, file=BytesIO(b"content"))
    return asyncio.create_task(
        upload_module.upload_knowledge_base_handler(
            background_tasks=None,
            name="notes",
            file=upload,
            description="",
            category="general",
            current_user=SimpleNamespace(id=9),
            db=db,
        )
    )


@pytest.mark.asyncio
async def test_upload_copy_allows_event_loop_heartbeat(monkeypatch, tmp_path):
    started = threading.Event()
    release = threading.Event()
    heartbeat_signal = threading.Event()
    heartbeat_before_release = []

    def blocking_copy(source, target):
        started.set()
        release.wait()
        target.write(source.read())

    def watchdog():
        assert started.wait(1.0)
        heartbeat_before_release.append(heartbeat_signal.wait(0.1))
        release.set()

    monkeypatch.setattr(upload_module.shutil, "copyfileobj", blocking_copy)
    monkeypatch.setattr(upload_module, "kb_processing_progress", {})
    monkeypatch.setattr(
        upload_module,
        "settings",
        SimpleNamespace(
            ALLOWED_EXTENSIONS={".txt"},
            MAX_UPLOAD_SIZE=1024,
            get_chroma_dir=lambda: str(tmp_path),
        ),
    )

    watchdog_thread = threading.Thread(target=watchdog, name="upload-test-watchdog")
    watchdog_thread.start()

    async def heartbeat():
        assert await asyncio.to_thread(started.wait, 1.0)
        await asyncio.sleep(0)
        heartbeat_signal.set()

    upload = SimpleNamespace(filename="notes.txt", size=7, file=BytesIO(b"content"))
    db = FakeUploadDB(refresh_error=StopAfterCopy("copy completed"))
    handler_task = asyncio.create_task(
        upload_module.upload_knowledge_base_handler(
            background_tasks=None,
            name="notes",
            file=upload,
            description="",
            category="general",
            current_user=SimpleNamespace(id=9),
            db=db,
        )
    )
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        with pytest.raises(StopAfterCopy, match="copy completed"):
            await handler_task
        await heartbeat_task
    finally:
        release.set()
        await asyncio.to_thread(watchdog_thread.join, 1.0)

    assert not watchdog_thread.is_alive()
    assert heartbeat_before_release == [True]
    upload_files = list((tmp_path / "uploads").iterdir())
    assert len(upload_files) == 1
    assert upload_files[0].suffix == ".txt"
    assert upload_files[0].read_bytes() == b"content"
    assert list((tmp_path / "uploads").glob("*.part")) == []


@pytest.mark.asyncio
async def test_cancelling_upload_waits_for_copy_and_removes_all_files(
    monkeypatch,
    tmp_path,
):
    copy_started = threading.Event()
    release_copy = threading.Event()
    copy_finished = threading.Event()
    source_closed_in_worker = []

    def gated_copy(source, target):
        copy_started.set()
        release_copy.wait()
        source_closed_in_worker.append(source.closed)
        target.write(source.read())
        copy_finished.set()

    monkeypatch.setattr(upload_module.shutil, "copyfileobj", gated_copy)
    monkeypatch.setattr(upload_module, "kb_processing_progress", {})
    monkeypatch.setattr(
        upload_module,
        "settings",
        SimpleNamespace(
            ALLOWED_EXTENSIONS={".txt"},
            MAX_UPLOAD_SIZE=1024,
            get_chroma_dir=lambda: str(tmp_path),
        ),
    )

    source = RequestOwnedStream(b"content")
    upload = SimpleNamespace(filename="notes.txt", size=7, file=source)
    handler_task = asyncio.create_task(
        upload_module.upload_knowledge_base_handler(
            background_tasks=None,
            name="notes",
            file=upload,
            description="",
            category="general",
            current_user=SimpleNamespace(id=9),
            db=None,
        )
    )
    handler_task.add_done_callback(lambda _task: source.close())

    try:
        assert await asyncio.to_thread(copy_started.wait, 1.0)
        handler_task.cancel()
        await asyncio.sleep(0)
        assert not handler_task.done()
    finally:
        release_copy.set()

    with pytest.raises(asyncio.CancelledError):
        await handler_task
    assert await asyncio.to_thread(copy_finished.wait, 1.0)
    assert source_closed_in_worker == [False]
    upload_dir = tmp_path / "uploads"
    assert list(upload_dir.glob("*.part")) == []
    assert list(upload_dir.glob("*.txt")) == []


@pytest.mark.asyncio
async def test_copy_failure_removes_temporary_and_final_files(monkeypatch, tmp_path):
    def failing_copy(source, target):
        target.write(source.read(3))
        raise OSError("disk write failed")

    monkeypatch.setattr(upload_module.shutil, "copyfileobj", failing_copy)
    monkeypatch.setattr(upload_module, "kb_processing_progress", {})
    monkeypatch.setattr(
        upload_module,
        "settings",
        SimpleNamespace(
            ALLOWED_EXTENSIONS={".txt"},
            MAX_UPLOAD_SIZE=1024,
            get_chroma_dir=lambda: str(tmp_path),
        ),
    )
    upload = SimpleNamespace(filename="notes.txt", size=7, file=BytesIO(b"content"))

    with pytest.raises(OSError, match="disk write failed"):
        await upload_module.upload_knowledge_base_handler(
            background_tasks=None,
            name="notes",
            file=upload,
            description="",
            category="general",
            current_user=SimpleNamespace(id=9),
            db=None,
        )

    upload_dir = tmp_path / "uploads"
    assert list(upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_cancelling_during_commit_rolls_back_and_removes_owned_file(
    monkeypatch,
    tmp_path,
):
    _configure_upload_test(monkeypatch, tmp_path)
    cleanup_started = threading.Event()
    cleanup_release = threading.Event()
    original_remove = upload_module._remove_file_if_exists

    def gated_remove(path):
        cleanup_started.set()
        cleanup_release.wait()
        original_remove(path)

    monkeypatch.setattr(upload_module, "_remove_file_if_exists", gated_remove)
    db = FakeUploadDB(block_commit=True)
    handler_task = _start_upload(db)

    try:
        await asyncio.wait_for(db.commit_started.wait(), 1.0)
        handler_task.cancel()
        assert await asyncio.to_thread(cleanup_started.wait, 1.0)
        handler_task.cancel()
        await asyncio.sleep(0)
        assert not handler_task.done()
    finally:
        cleanup_release.set()

    with pytest.raises(asyncio.CancelledError):
        await handler_task

    upload_dir = tmp_path / "uploads"
    assert db.rollback_count == 1
    assert list(upload_dir.glob("*.part")) == []
    assert list(upload_dir.glob("*.txt")) == []


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_removes_file_and_preserves_exception(
    monkeypatch,
    tmp_path,
):
    _configure_upload_test(monkeypatch, tmp_path)
    commit_error = RuntimeError("commit failed")
    db = FakeUploadDB(
        commit_error=commit_error,
        rollback_error=RuntimeError("rollback failed"),
    )

    with pytest.raises(RuntimeError) as caught:
        await _start_upload(db)

    upload_dir = tmp_path / "uploads"
    assert caught.value is commit_error
    assert db.rollback_count == 1
    assert list(upload_dir.glob("*.part")) == []
    assert list(upload_dir.glob("*.txt")) == []


@pytest.mark.asyncio
async def test_refresh_failure_after_commit_keeps_db_owned_file_without_rollback(
    monkeypatch,
    tmp_path,
):
    _configure_upload_test(monkeypatch, tmp_path)
    refresh_error = RuntimeError("refresh failed")
    db = FakeUploadDB(refresh_error=refresh_error)

    with pytest.raises(RuntimeError) as caught:
        await _start_upload(db)

    upload_dir = tmp_path / "uploads"
    final_files = list(upload_dir.glob("*.txt"))
    assert caught.value is refresh_error
    assert db.rollback_count == 0
    assert list(upload_dir.glob("*.part")) == []
    assert len(final_files) == 1
    assert final_files[0].read_bytes() == b"content"


@pytest.mark.asyncio
async def test_queue_failure_marks_committed_record_failed_with_error_code(
    monkeypatch,
    tmp_path,
):
    _configure_upload_test(monkeypatch, tmp_path)
    state_module = importlib.import_module("app.api.v1.endpoints.knowledge._state")
    progress_store = {}
    monkeypatch.setattr(upload_module, "kb_processing_progress", progress_store)
    monkeypatch.setattr(state_module, "kb_processing_progress", progress_store)
    monkeypatch.setattr(state_module, "_sync_update_kb_progress", lambda *_args: None)
    db = FakeUploadDB()

    class FailingPool:
        def submit(self, _function):
            raise RuntimeError("worker queue unavailable")

    monkeypatch.setattr(upload_module, "kb_thread_pool", FailingPool())

    with pytest.raises(RuntimeError, match="worker queue unavailable"):
        await _start_upload(db)

    record = db.added[0]
    progress = upload_module.kb_processing_progress[record.id]
    assert record.status == upload_module.KnowledgeBaseStatus.FAILED
    assert record.document_count == 0
    assert progress["status"] == "failed"
    assert progress["error"].startswith("KB-QUEUE-001:")
    assert db.commit_count == 2
