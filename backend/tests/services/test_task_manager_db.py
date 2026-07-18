"""
task_manager_db Session 生命周期测试

验证任务状态数据库操作使用短生命周期 Session：
- 每次操作通过 Session Factory 创建独立 Session
- 正常与异常路径均退出 Session
- 不访问真实数据库

@date: 2026-07-18
@version: v1.0.0
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import task_manager_db


class FakeAsyncSession:
    """记录进入/退出/提交次数的伪 Session"""

    def __init__(self):
        self.enter_count = 0
        self.exit_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.commit_error = None

    async def __aenter__(self):
        self.enter_count += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exit_count += 1
        return False

    async def commit(self):
        self.commit_count += 1
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self):
        self.rollback_count += 1


class FakeSessionFactory:
    """每次调用返回一个新的 FakeAsyncSession 并记录创建历史"""

    def __init__(self):
        self.created_sessions = []
        self.commit_error = None

    def __call__(self):
        session = FakeAsyncSession()
        session.commit_error = self.commit_error
        self.created_sessions.append(session)
        return session


class FakeNovelProjectRepo:
    """伪 Repository：返回预置项目或抛出预置异常，不访问数据库"""

    project_to_return = None
    error_to_raise = None

    def __init__(self, session):
        self.session = session

    async def get(self, project_id):
        if FakeNovelProjectRepo.error_to_raise is not None:
            raise FakeNovelProjectRepo.error_to_raise
        return FakeNovelProjectRepo.project_to_return


def _build_running_task() -> dict:
    return {
        "task_type": "chapter_content",
        "status": "running",
        "total_count": 10,
        "completed_count": 1,
        "failed_count": 0,
        "skipped_count": 0,
        "current_item": 2,
        "started_at": "2026-07-18T00:00:00",
        "updated_at": "2026-07-18T00:01:00",
    }


def _build_project_with_task_fields() -> SimpleNamespace:
    return SimpleNamespace(
        generation_task_type="chapter_content",
        generation_task_status="running",
        generation_task_total=10,
        generation_task_completed=1,
        generation_task_failed=0,
        generation_task_skipped=0,
        generation_task_current=2,
        generation_task_started_at="2026-07-18T00:00:00",
        generation_task_updated_at="2026-07-18T00:01:00",
    )


@pytest.fixture
def fake_factory():
    """注入伪 Session Factory，测试结束后恢复默认工厂并重置伪 Repo 状态"""
    original_factory = task_manager_db._session_factory
    factory = FakeSessionFactory()
    task_manager_db.set_session_factory(factory)
    FakeNovelProjectRepo.project_to_return = None
    FakeNovelProjectRepo.error_to_raise = None
    with patch.object(task_manager_db, "NovelProjectRepository", FakeNovelProjectRepo):
        yield factory
    task_manager_db.set_session_factory(original_factory)


@pytest.mark.asyncio
async def test_two_writes_create_two_distinct_sessions(fake_factory):
    """连续两次任务状态写入应创建两个不同 Session，且两次事务均正常退出"""
    FakeNovelProjectRepo.project_to_return = _build_project_with_task_fields()

    await task_manager_db.sync_task_to_db(1, _build_running_task())
    await task_manager_db.sync_task_to_db(1, _build_running_task())

    assert len(fake_factory.created_sessions) == 2
    first_session, second_session = fake_factory.created_sessions
    assert first_session is not second_session
    for session in fake_factory.created_sessions:
        assert session.enter_count == 1
        assert session.exit_count == 1
        assert session.commit_count == 1


@pytest.mark.asyncio
async def test_write_failure_reraises_and_exits_session(fake_factory):
    """写入异常应重新抛出，且 Session 必须退出"""
    FakeNovelProjectRepo.error_to_raise = RuntimeError("db down")

    with pytest.raises(RuntimeError, match="db down"):
        await task_manager_db.sync_task_to_db(1, _build_running_task())

    assert len(fake_factory.created_sessions) == 1
    failed_session = fake_factory.created_sessions[0]
    assert failed_session.enter_count == 1
    assert failed_session.exit_count == 1
    assert failed_session.commit_count == 0


@pytest.mark.asyncio
async def test_read_failure_returns_none_and_exits_session(fake_factory):
    """读取异常应返回 None，且 Session 必须退出"""
    FakeNovelProjectRepo.error_to_raise = RuntimeError("db down")

    result = await task_manager_db.get_task_from_db(1)

    assert result is None
    assert len(fake_factory.created_sessions) == 1
    assert fake_factory.created_sessions[0].exit_count == 1


@pytest.mark.asyncio
async def test_read_success_returns_task_dict_and_exits_session(fake_factory):
    """读取成功应返回任务字典（结构不变），且 Session 退出"""
    FakeNovelProjectRepo.project_to_return = _build_project_with_task_fields()

    result = await task_manager_db.get_task_from_db(7)

    assert result is not None
    assert result["project_id"] == 7
    assert result["task_type"] == "chapter_content"
    assert result["status"] == "running"
    assert result["total_count"] == 10
    assert result["completed_count"] == 1
    assert result["metadata"] == {}
    assert fake_factory.created_sessions[0].exit_count == 1


@pytest.mark.asyncio
async def test_clear_task_commits_and_exits_session(fake_factory):
    """清除任务状态应提交事务并退出 Session"""
    FakeNovelProjectRepo.project_to_return = _build_project_with_task_fields()

    await task_manager_db.clear_task_in_db(3)

    session = fake_factory.created_sessions[0]
    assert session.enter_count == 1
    assert session.exit_count == 1
    assert session.commit_count == 1
    cleared_project = FakeNovelProjectRepo.project_to_return
    assert cleared_project.generation_task_status is None
    assert cleared_project.generation_task_total == 0


@pytest.mark.asyncio
async def test_clear_repo_get_failure_rolls_back_exits_and_reraises(
    fake_factory,
):
    FakeNovelProjectRepo.error_to_raise = RuntimeError("repo get failed")

    with pytest.raises(RuntimeError, match="repo get failed"):
        await task_manager_db.clear_task_in_db(41)

    session = fake_factory.created_sessions[0]
    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.exit_count == 1


@pytest.mark.asyncio
async def test_clear_commit_failure_rolls_back_exits_logs_id_and_reraises(
    fake_factory,
):
    FakeNovelProjectRepo.project_to_return = _build_project_with_task_fields()
    fake_factory.commit_error = RuntimeError("commit failed")

    with patch.object(task_manager_db.logger, "warning") as warning:
        with pytest.raises(RuntimeError, match="commit failed"):
            await task_manager_db.clear_task_in_db(42)

    session = fake_factory.created_sessions[0]
    assert session.commit_count == 1
    assert session.rollback_count == 1
    assert session.exit_count == 1
    assert "project_id=42" in warning.call_args.args[0]
