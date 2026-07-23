# -*- coding: utf-8 -*-
"""
任务收敛（幽灵状态清理）测试

覆盖：
    - 重启一次后，残留 RUNNING 任务被收敛为 INTERRUPTED，写入原因 server_restarted 与 end_time；
    - 已终止（completed）任务不受影响；
    - 第二次收敛不改写终态任务，且不重复改写已 INTERRUPTED 的 end_time。
"""
import asyncio
import os
import sys

# 确保 backend 目录在 Python 路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 导入全部模型以完成映射注册，随后仅创建 writing_tasks 表
import app.models  # noqa: F401
from app.core.database import Base
from app.models.writing_task import TaskStatus, WritingTask
from app.services.task_manager_db import SERVER_RESTARTED_REASON, interrupt_orphaned_tasks


async def _build_session_maker():
    """构建内存 SQLite 会话工厂，仅建 writing_tasks 表。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[WritingTask.__table__])
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _insert_task(session_maker, status: TaskStatus, end_time=None) -> int:
    async with session_maker() as db:
        task = WritingTask(
            project_id=1,
            user_id=1,
            status=status,
            end_time=end_time,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task.id


async def _get_task(session_maker, task_id: int) -> WritingTask:
    from sqlalchemy import select
    async with session_maker() as db:
        result = await db.execute(select(WritingTask).where(WritingTask.id == task_id))
        return result.scalar_one()


def test_restart_once_interrupts_running_tasks():
    async def scenario():
        session_maker = await _build_session_maker()
        running_id = await _insert_task(session_maker, TaskStatus.RUNNING)
        completed_id = await _insert_task(session_maker, TaskStatus.COMPLETED)

        affected = await interrupt_orphaned_tasks(session_maker)
        assert affected == 1

        running = await _get_task(session_maker, running_id)
        assert running.status == TaskStatus.INTERRUPTED
        assert running.error_message == SERVER_RESTARTED_REASON
        assert running.end_time is not None

        completed = await _get_task(session_maker, completed_id)
        assert completed.status == TaskStatus.COMPLETED

    asyncio.run(scenario())


def test_second_restart_does_not_rewrite_terminal_tasks():
    async def scenario():
        session_maker = await _build_session_maker()
        running_id = await _insert_task(session_maker, TaskStatus.RUNNING)

        first_affected = await interrupt_orphaned_tasks(session_maker)
        assert first_affected == 1

        interrupted = await _get_task(session_maker, running_id)
        first_end_time = interrupted.end_time
        assert interrupted.status == TaskStatus.INTERRUPTED

        # 第二次收敛：终态不在 WHERE 命中范围内，受影响数量为 0，end_time 不变
        second_affected = await interrupt_orphaned_tasks(session_maker)
        assert second_affected == 0

        again = await _get_task(session_maker, running_id)
        assert again.status == TaskStatus.INTERRUPTED
        assert again.end_time == first_end_time

    asyncio.run(scenario())
