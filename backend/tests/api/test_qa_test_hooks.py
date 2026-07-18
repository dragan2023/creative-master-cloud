from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException

from app.core.qa_test_gate import mount_qa_test_hooks
from app.api.v1.endpoints import qa_test_hooks
from app.models.writing_task import TaskStatus


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


@pytest.fixture(autouse=True)
def clear_qa_registry():
    qa_test_hooks._clear_qa_task_registry_for_tests()
    yield
    qa_test_hooks._clear_qa_task_registry_for_tests()


def test_production_runtime_never_mounts_qa_routes_even_when_flag_is_set():
    application = FastAPI()

    mounted = mount_qa_test_hooks(application, qa_flag="1", runtime_env="server")

    assert mounted is False
    assert not any("/qa-test-hooks" in route.path for route in application.routes)


def test_test_runtime_requires_explicit_qa_flag():
    application = FastAPI()

    mounted = mount_qa_test_hooks(application, qa_flag="0", runtime_env="test")

    assert mounted is False
    assert not any("/qa-test-hooks" in route.path for route in application.routes)


@pytest.mark.asyncio
async def test_non_qa_task_cannot_emit_terminal_status():
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await qa_test_hooks.emit_writing_task_complete(
            task_id=91,
            request=qa_test_hooks.EmitCompleteRequest(total_word_count=10),
            current_user=SimpleNamespace(id=7),
            db=db,
        )

    assert exc_info.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_user_normal_project_cannot_be_registered_as_qa_task():
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await qa_test_hooks.seed_running_writing_task(
            request=qa_test_hooks.SeedRunningTaskRequest(project_id=70, total_units=5),
            current_user=SimpleNamespace(id=7),
            db=db,
        )

    assert exc_info.value.status_code == 403
    db.execute.assert_not_awaited()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_cross_user_cannot_emit_or_cleanup_registered_qa_task():
    qa_test_hooks._register_qa_project(project_id=15, user_id=7)
    qa_test_hooks._register_qa_task(task_id=92, user_id=7, project_id=15)
    db = AsyncMock()
    foreign_user = SimpleNamespace(id=8)

    with pytest.raises(HTTPException) as emit_error:
        await qa_test_hooks.emit_writing_task_complete(
            task_id=92,
            request=qa_test_hooks.EmitCompleteRequest(total_word_count=10),
            current_user=foreign_user,
            db=db,
        )
    with pytest.raises(HTTPException) as cleanup_error:
        await qa_test_hooks.cleanup_qa_writing_task(
            task_id=92,
            current_user=foreign_user,
            db=db,
        )

    assert emit_error.value.status_code == 403
    assert cleanup_error.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_qa_terminal_emit_uses_production_status_change_path(monkeypatch):
    task = SimpleNamespace(
        id=93,
        user_id=7,
        project_id=15,
        status=TaskStatus.RUNNING,
        total_units=5,
        completed_units=0,
        end_time=None,
    )
    db = AsyncMock()
    db.execute.return_value = ScalarResult(task)
    manager = SimpleNamespace(
        send_status_change=AsyncMock(return_value=1),
        send_task_complete=AsyncMock(),
    )
    monkeypatch.setattr(qa_test_hooks, "get_websocket_manager", lambda: manager)
    qa_test_hooks._register_qa_project(project_id=15, user_id=7)
    qa_test_hooks._register_qa_task(task_id=93, user_id=7, project_id=15)

    response = await qa_test_hooks.emit_writing_task_complete(
        task_id=93,
        request=qa_test_hooks.EmitCompleteRequest(total_word_count=10),
        current_user=SimpleNamespace(id=7),
        db=db,
    )

    assert response.success is True
    assert task.status == TaskStatus.COMPLETED
    manager.send_status_change.assert_awaited_once_with(
        task_id=93,
        old_status=TaskStatus.RUNNING,
        new_status=TaskStatus.COMPLETED,
    )
    manager.send_task_complete.assert_not_awaited()
