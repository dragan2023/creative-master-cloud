"""
批量生成任务状态管理器 - 数据库同步模块

从 task_manager.py 拆分，包含所有数据库同步方法。

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Optional, Dict, Any, Callable

from sqlalchemy import select, update

from app.core.logger import get_logger
from app.core.database import async_session_maker
from app.models import NovelProject
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
    """同步任务状态到数据库"""
    try:
        if _novel_project_repo:
            project = await _novel_project_repo.get(project_id)
            if project:
                project.generation_task_type = task.get("task_type")
                project.generation_task_status = task.get("status")
                project.generation_task_total = task.get("total_count", 0)
                project.generation_task_completed = task.get("completed_count", 0)
                project.generation_task_failed = task.get("failed_count", 0)
                project.generation_task_skipped = task.get("skipped_count", 0)
                project.generation_task_current = task.get("current_item")
                project.generation_task_started_at = task.get("started_at")
                project.generation_task_updated_at = task.get("updated_at")
                await _novel_project_repo.session.commit()
            return
        # Fallback: 直连 session
        async with async_session_maker() as db:
            query = await db.execute(
                select(NovelProject).where(NovelProject.id == project_id)
            )
            project = query.scalar_one_or_none()
            if project:
                project.generation_task_type = task.get("task_type")
                project.generation_task_status = task.get("status")
                project.generation_task_total = task.get("total_count", 0)
                project.generation_task_completed = task.get("completed_count", 0)
                project.generation_task_failed = task.get("failed_count", 0)
                project.generation_task_skipped = task.get("skipped_count", 0)
                project.generation_task_current = task.get("current_item")
                project.generation_task_started_at = task.get("started_at")
                project.generation_task_updated_at = task.get("updated_at")
                await db.commit()
    except Exception as e:
        logger.error(f"同步任务状态到数据库失败: {e}", exc_info=True)
        raise


async def get_task_from_db(project_id: int) -> Optional[Dict[str, Any]]:
    """从数据库获取任务状态"""
    try:
        if _novel_project_repo:
            project = await _novel_project_repo.get(project_id)
            if project and project.generation_task_status:
                return {
                    "project_id": project_id,
                    "task_type": project.generation_task_type,
                    "status": project.generation_task_status,
                    "total_count": project.generation_task_total or 0,
                    "completed_count": project.generation_task_completed or 0,
                    "failed_count": project.generation_task_failed or 0,
                    "skipped_count": project.generation_task_skipped or 0,
                    "current_item": project.generation_task_current,
                    "started_at": project.generation_task_started_at,
                    "updated_at": project.generation_task_updated_at,
                    "metadata": {}
                }
            return None
        # Fallback: 直连 session
        async with async_session_maker() as db:
            query = await db.execute(
                select(NovelProject).where(NovelProject.id == project_id)
            )
            project = query.scalar_one_or_none()
            if project and project.generation_task_status:
                return {
                    "project_id": project_id,
                    "task_type": project.generation_task_type,
                    "status": project.generation_task_status,
                    "total_count": project.generation_task_total or 0,
                    "completed_count": project.generation_task_completed or 0,
                    "failed_count": project.generation_task_failed or 0,
                    "skipped_count": project.generation_task_skipped or 0,
                    "current_item": project.generation_task_current,
                    "started_at": project.generation_task_started_at,
                    "updated_at": project.generation_task_updated_at,
                    "metadata": {}
                }
    except Exception as e:
        logger.warning(f"从数据库获取任务状态失败: {e}")
    return None


async def clear_task_in_db(project_id: int):
    """清除数据库中的任务状态"""
    try:
        if _novel_project_repo:
            project = await _novel_project_repo.get(project_id)
            if project:
                project.generation_task_type = None
                project.generation_task_status = None
                project.generation_task_total = 0
                project.generation_task_completed = 0
                project.generation_task_failed = 0
                project.generation_task_skipped = 0
                project.generation_task_current = None
                project.generation_task_started_at = None
                project.generation_task_updated_at = None
                await _novel_project_repo.session.commit()
            return
        # Fallback: 直连 session
        async with async_session_maker() as db:
            query = await db.execute(
                select(NovelProject).where(NovelProject.id == project_id)
            )
            project = query.scalar_one_or_none()
            if project:
                project.generation_task_type = None
                project.generation_task_status = None
                project.generation_task_total = 0
                project.generation_task_completed = 0
                project.generation_task_failed = 0
                project.generation_task_skipped = 0
                project.generation_task_current = None
                project.generation_task_started_at = None
                project.generation_task_updated_at = None
                await db.commit()
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
