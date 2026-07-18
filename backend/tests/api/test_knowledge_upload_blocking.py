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

    def stop_after_copy(_path):
        raise StopAfterCopy("copy completed")

    monkeypatch.setattr(upload_module.shutil, "copyfileobj", blocking_copy)
    monkeypatch.setattr(upload_module.os.path, "getsize", stop_after_copy)
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
