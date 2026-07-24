"""
批量生成任务状态管理器 - 数据库同步模块

从 task_manager.py 拆分，将 Redis 任务字典同步到 WritingTask 表。
替代已删除的 NovelProject.generation_task_* 字段（迁移 022）。

@date: 2026-07-23 (迁移至 WritingTask)
@version: v2.0.0
"""
from typing import Optional, Dict, Any, Callable

from sqlalchemy import select, update

from app.core.logger import get_logger
from app.core.database import async_session_maker
from app.models import NovelProject
from app.models.writing_task import WritingTask, TaskStatus
from app.repositories.novel_project import NovelProjectRepository

logger = get_logger("task_manager")

# 服务重启导致任务中断的统一原因
SERVER_RESTARTED_REASON = "server_restarted"

# Repository 实例（注入方式设置，用于替代直连 async_session_maker）
_novel_project_repo: Optional[NovelProjectRepository] = None


def set_novel_project_repo(repo: NovelProjectRepository):
    """设置 NovelProjectRepository 实例（由启动注入）"""
    global _novel_project_repo
    _novel_project_repo = repo


async def sync_task_to_db(project_id: int, task: Dict[str, Any]):
    """同步任务状态到 WritingTask 表（替代已删除的 NovelProject.generation_task_*）。"""
    from app.services.task_query_service import sync_task_to_writing_task

    if _novel_project_repo:
        db = _novel_project_repo.session
        # repo 已有 active session，直接复用
        result = await sync_task_to_writing_task(db, project_id, task)
        if result is not None:
            await db.commit()
        return

    # Fallback: 创建独立 session
    async with async_session_maker() as db:
        await sync_task_to_writing_task(db, project_id, task)


async def get_task_from_db(project_id: int) -> Optional[Dict[str, Any]]:
    """从 WritingTask 表获取任务状态（替代已删除的 NovelProject.generation_task_*）。"""
    from app.services.task_query_service import get_task_for_project

    try:
        if _novel_project_repo:
            db = _novel_project_repo.session
            return await get_task_for_project(db, project_id)

        async with async_session_maker() as db:
            return await get_task_for_project(db, project_id)
    except Exception as e:
        logger.warning(f"从数据库获取任务状态失败: {e}")
    return None


async def clear_task_in_db(project_id: int, task: Optional[Dict[str, Any]] = None):
    """清除 WritingTask 中的任务状态（标记为 cancelled）。

    WritingTask 保留历史记录不删除，仅将状态迁移到终态。
    若调用方传入了 task 字典（含 writing_task_db_id），直接定位；
    否则查询最新非终态 WritingTask 来清除。
    """
    from app.services.task_query_service import (
        get_task_for_project,
        clear_task_in_writing_task,
    )

    try:
        if task is None:
            if _novel_project_repo:
                db = _novel_project_repo.session
                task = await get_task_for_project(db, project_id)
                if task:
                    await clear_task_in_writing_task(db, task)
                return

            async with async_session_maker() as db:
                task = await get_task_for_project(db, project_id)
                if task:
                    await clear_task_in_writing_task(db, task)
                return

        # 传入了 task 字典
        if _novel_project_repo:
            await clear_task_in_writing_task(_novel_project_repo.session, task)
            return

        async with async_session_maker() as db:
            await clear_task_in_writing_task(db, task)
    except Exception as e:
        logger.warning(f"清除数据库任务状态失败: {e}")


async def interrupt_orphaned_tasks(session_maker: Optional[Callable] = None) -> int:
    """将残留 RUNNING 状态的写作任务统一收敛为 INTERRUPTED。

    仅在应用启动/关闭这类生命周期节点调用：进程重启后内存中的执行体已消失，
    数据库里残留的 RUNNING 任务是幽灵状态，必须以持久化状态为唯一事实来源收敛。
    采用单条条件 UPDATE 完成迁移，写入原因 server_restarted，返回受影响任务数量；
    终态任务（completed/failed/cancelled/interrupted）不在 WHERE 命中范围内，天然幂等。

    Args:
        session_maker: 可选的会话工厂（用于测试注入内存数据库），缺省使用全局 async_session_maker

    Returns:
        本次被收敛的任务数量
    """
    from datetime import datetime
    from app.models.writing_task import WritingTask, TaskStatus

    maker = session_maker or async_session_maker
    try:
        async with maker() as db:
            result = await db.execute(
                update(WritingTask)
                .where(WritingTask.status == TaskStatus.RUNNING)
                .values(
                    status=TaskStatus.INTERRUPTED,
                    end_time=datetime.now(),
                    error_message=SERVER_RESTARTED_REASON,
                )
            )
            await db.commit()
            affected = result.rowcount or 0
            if affected > 0:
                logger.info(f"[任务收敛] 已将 {affected} 个残留 RUNNING 任务标记为 INTERRUPTED")
            return affected
    except Exception as e:
        logger.warning(f"收敛残留 RUNNING 任务失败（不影响启动/关闭）: {e}")
        return 0


__all__ = [
    "set_novel_project_repo",
    "sync_task_to_db",
    "get_task_from_db",
    "clear_task_in_db",
    "interrupt_orphaned_tasks",
    "SERVER_RESTARTED_REASON",
    "_novel_project_repo",
]
