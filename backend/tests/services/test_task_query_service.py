# -*- coding: utf-8 -*-
"""
task_query_service 单元测试 — WritingTask ↔ Redis 任务字典映射

覆盖：
    - 空库查询返回 None
    - 终态任务的 get_task_for_project 返回 None（不返回已完成/已取消任务）
    - 非终态任务的 get_task_for_project 返回正确映射
    - sync_task_to_writing_task 新建 WritingTask 并回写 ID
    - sync_task_to_writing_task 更新已存在记录
    - clear_task_in_writing_task 将任务标记为 cancelled
    - 不存在项目时 sync 返回 None（不崩溃）
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models.writing_task import TaskStatus, WritingTask
from app.models.novel_project import NovelProject, ProjectType
from app.models.user import User
from app.services.task_query_service import (
    get_task_for_project,
    get_latest_task_for_project,
    sync_task_to_writing_task,
    clear_task_in_writing_task,
    _writing_task_to_dict,
    _apply_task_dict_to_writing_task,
)
from app.services.task_manager_constants import (
    TASK_STATUS_RUNNING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_CANCELLED,
)


async def _build_session_maker():
    """构建内存 SQLite 会话工厂，创建 writing_tasks + novel_projects + users 表。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                NovelProject.__table__,
                WritingTask.__table__,
            ],
        )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_user_and_project(session_maker) -> tuple[int, int]:
    """插入测试用户和项目，返回 (user_id, project_id)。"""
    async with session_maker() as db:
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="x",
            is_active=True,
        )
        db.add(user)
        await db.flush()

        project = NovelProject(
            title="测试项目",
            user_id=user.id,
            project_type=ProjectType.NOVEL,
            content_type="novel",
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return user.id, project.id


# ── 测试: get_task_for_project ──────────────────────────────────────────────


class TestGetTaskForProject:
    """查询接口行为"""

    def test_returns_none_when_no_tasks_exist(self):
        async def scenario():
            sm = await _build_session_maker()
            _, pid = await _seed_user_and_project(sm)
            async with sm() as db:
                result = await get_task_for_project(db, pid)
                assert result is None
        asyncio.run(scenario())

    def test_returns_none_for_completed_task(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)
            async with sm() as db:
                wt = WritingTask(
                    project_id=pid,
                    user_id=uid,
                    status=TaskStatus.COMPLETED,
                    total_units=3,
                    completed_units=3,
                )
                db.add(wt)
                await db.commit()
            async with sm() as db:
                result = await get_task_for_project(db, pid)
                assert result is None  # 终态任务不返回
        asyncio.run(scenario())

    def test_returns_none_for_cancelled_task(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)
            async with sm() as db:
                wt = WritingTask(
                    project_id=pid,
                    user_id=uid,
                    status=TaskStatus.CANCELLED,
                )
                db.add(wt)
                await db.commit()
            async with sm() as db:
                result = await get_task_for_project(db, pid)
                assert result is None
        asyncio.run(scenario())

    def test_returns_task_dict_for_running_task(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)
            async with sm() as db:
                wt = WritingTask(
                    project_id=pid,
                    user_id=uid,
                    status=TaskStatus.RUNNING,
                    total_units=10,
                    completed_units=5,
                    config={
                        "task_type": "chapter_outline",
                        "failed_count": 1,
                        "skipped_count": 0,
                        "current_item": "第3章",
                    },
                )
                db.add(wt)
                await db.commit()
            async with sm() as db:
                result = await get_task_for_project(db, pid)
                assert result is not None
                assert result["project_id"] == pid
                assert result["task_type"] == "chapter_outline"
                assert result["status"] == TASK_STATUS_RUNNING
                assert result["total_count"] == 10
                assert result["completed_count"] == 5
                assert result["failed_count"] == 1
                assert result["skipped_count"] == 0
                assert result["current_item"] == "第3章"
                assert result["writing_task_db_id"] == wt.id
        asyncio.run(scenario())

    def test_get_latest_returns_completed_task_unlike_get_task(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)
            async with sm() as db:
                wt = WritingTask(
                    project_id=pid,
                    user_id=uid,
                    status=TaskStatus.COMPLETED,
                    total_units=5,
                    completed_units=5,
                    config={"task_type": "episode_content"},
                )
                db.add(wt)
                await db.commit()
            async with sm() as db:
                # get_task_for_project 应过滤终态
                active = await get_task_for_project(db, pid)
                assert active is None
                # get_latest_task_for_project 应返回终态
                latest = await get_latest_task_for_project(db, pid)
                assert latest is not None
                assert latest["status"] == TASK_STATUS_COMPLETED
                assert latest["task_type"] == "episode_content"
        asyncio.run(scenario())


# ── 测试: sync_task_to_writing_task ─────────────────────────────────────────


class TestSyncTaskToWritingTask:
    """写入同步行为"""

    def test_creates_writing_task_and_writes_back_id(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)

            task_dict = {
                "project_id": pid,
                "task_type": "scene_outline",
                "status": TASK_STATUS_RUNNING,
                "total_count": 20,
                "completed_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "current_item": None,
                "started_at": "2026-07-23T10:00:00",
                "metadata": {"batch": "v1"},
            }

            async with sm() as db:
                wt_id = await sync_task_to_writing_task(db, pid, task_dict)
                assert wt_id is not None
                # 验证回写
                assert task_dict.get("writing_task_db_id") == wt_id

            async with sm() as db:
                wt = await db.get(WritingTask, wt_id)
                assert wt is not None
                assert wt.project_id == pid
                assert wt.status == TaskStatus.RUNNING
                assert wt.total_units == 20
                assert wt.config.get("task_type") == "scene_outline"
                assert wt.config.get("metadata") == {"batch": "v1"}
        asyncio.run(scenario())

    def test_updates_existing_writing_task_via_id(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)

            # 首次创建
            task_dict = {
                "project_id": pid,
                "task_type": "chapter_content",
                "status": TASK_STATUS_RUNNING,
                "total_count": 8,
                "completed_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
            }
            async with sm() as db:
                await sync_task_to_writing_task(db, pid, task_dict)

            # 更新进度
            task_dict["completed_count"] = 4
            task_dict["failed_count"] = 1
            task_dict["status"] = TASK_STATUS_COMPLETED
            async with sm() as db:
                await sync_task_to_writing_task(db, pid, task_dict)

            async with sm() as db:
                wt_id = task_dict["writing_task_db_id"]
                wt = await db.get(WritingTask, wt_id)
                assert wt.completed_units == 4
                assert wt.config.get("failed_count") == 1
                assert wt.status == TaskStatus.COMPLETED
                assert wt.end_time is not None  # 终态应有结束时间
        asyncio.run(scenario())

    def test_returns_none_when_project_not_found(self):
        async def scenario():
            sm = await _build_session_maker()
            task_dict = {
                "project_id": 99999,
                "task_type": "episode_outline",
                "status": TASK_STATUS_RUNNING,
                "total_count": 1,
                "completed_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
            }
            async with sm() as db:
                result = await sync_task_to_writing_task(db, 99999, task_dict)
                assert result is None  # 项目不存在，不应崩溃
        asyncio.run(scenario())

    def test_multiple_syncs_for_same_project_create_one_record(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)

            task_dict = {
                "project_id": pid,
                "task_type": "episode_outline",
                "status": TASK_STATUS_RUNNING,
                "total_count": 5,
                "completed_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
            }
            async with sm() as db:
                id1 = await sync_task_to_writing_task(db, pid, task_dict)
                id2 = await sync_task_to_writing_task(db, pid, task_dict)
                assert id1 == id2  # 同一任务记录复用

            # 只有一个非终态 WritingTask
            from sqlalchemy import select, func
            async with sm() as db:
                count = await db.scalar(
                    select(func.count()).select_from(WritingTask).where(
                        WritingTask.project_id == pid
                    )
                )
                assert count == 1
        asyncio.run(scenario())


# ── 测试: clear_task_in_writing_task ─────────────────────────────────────


class TestClearTaskInWritingTask:
    """清除行为"""

    def test_marks_writing_task_as_cancelled(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)

            task_dict = {
                "project_id": pid,
                "task_type": "chapter_outline",
                "status": TASK_STATUS_RUNNING,
                "total_count": 3,
                "completed_count": 2,
                "failed_count": 0,
                "skipped_count": 0,
            }
            async with sm() as db:
                await sync_task_to_writing_task(db, pid, task_dict)
                wt_id = task_dict["writing_task_db_id"]

            async with sm() as db:
                await clear_task_in_writing_task(db, task_dict)

            async with sm() as db:
                wt = await db.get(WritingTask, wt_id)
                assert wt.status == TaskStatus.CANCELLED
                assert wt.end_time is not None
        asyncio.run(scenario())

    def test_noop_when_no_db_id(self):
        async def scenario():
            sm = await _build_session_maker()
            task_dict = {"project_id": 1, "status": "running"}
            async with sm() as db:
                # 不应崩溃
                await clear_task_in_writing_task(db, task_dict)
        asyncio.run(scenario())

    def test_noop_when_already_terminal(self):
        async def scenario():
            sm = await _build_session_maker()
            uid, pid = await _seed_user_and_project(sm)
            async with sm() as db:
                wt = WritingTask(
                    project_id=pid,
                    user_id=uid,
                    status=TaskStatus.COMPLETED,
                    total_units=1,
                    completed_units=1,
                )
                db.add(wt)
                await db.commit()
                await db.refresh(wt)

                task_dict = {"writing_task_db_id": wt.id, "status": "completed"}
                await clear_task_in_writing_task(db, task_dict)

            async with sm() as db:
                wt2 = await db.get(WritingTask, wt.id)
                assert wt2.status == TaskStatus.COMPLETED  # 终态不变
        asyncio.run(scenario())


# ── 测试: 内部辅助函数 ────────────────────────────────────────────────────


class TestHelperFunctions:
    """字典/ORM 转换正确性"""

    def test_apply_task_dict_updates_fields_correctly(self):
        """_apply_task_dict_to_writing_task 将 Redis 字典写入 WritingTask 各字段"""
        wt = WritingTask(status=TaskStatus.PENDING, config={})
        task_dict = {
            "status": TASK_STATUS_RUNNING,
            "total_count": 12,
            "completed_count": 7,
            "task_type": "scene_content",
            "failed_count": 1,
            "skipped_count": 2,
            "current_item": "场景5",
            "started_at": "2026-07-23T08:00:00",
        }
        _apply_task_dict_to_writing_task(wt, task_dict)
        assert wt.status == TaskStatus.RUNNING
        assert wt.total_units == 12
        assert wt.completed_units == 7
        assert wt.config.get("task_type") == "scene_content"
        assert wt.config.get("failed_count") == 1
        assert wt.config.get("skipped_count") == 2
        assert wt.config.get("current_item") == "场景5"

    def test_apply_task_dict_writes_end_time_on_terminal(self):
        wt = WritingTask(status=TaskStatus.RUNNING, config={})
        _apply_task_dict_to_writing_task(wt, {"status": TASK_STATUS_COMPLETED})
        assert wt.status == TaskStatus.COMPLETED
        assert wt.end_time is not None

    def test_apply_task_dict_does_not_overwrite_existing_start_time(self):
        from datetime import datetime
        fixed = datetime(2026, 7, 1, 12, 0, 0)
        wt = WritingTask(status=TaskStatus.PENDING, start_time=fixed, config={})
        _apply_task_dict_to_writing_task(
            wt, {"status": TASK_STATUS_RUNNING, "started_at": "2026-08-01T00:00:00"}
        )
        # start_time 已设置，不应覆盖
        assert wt.start_time == fixed

    def test_writing_task_to_dict_preserves_writing_task_db_id(self):
        from datetime import datetime
        wt = WritingTask(
            id=42,
            project_id=1,
            status=TaskStatus.RUNNING,
            total_units=5,
            completed_units=3,
            config={"task_type": "episode_content"},
            start_time=datetime(2026, 7, 23, 10, 0, 0),
        )
        result = _writing_task_to_dict(wt)
        assert result["writing_task_db_id"] == 42
        assert result["status"] == TASK_STATUS_RUNNING
        assert result["total_count"] == 5
        assert result["completed_count"] == 3
        assert result["failed_count"] == 0  # 未在 config 中设置，默认 0
