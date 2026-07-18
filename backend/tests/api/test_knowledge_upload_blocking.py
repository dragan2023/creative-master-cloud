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
