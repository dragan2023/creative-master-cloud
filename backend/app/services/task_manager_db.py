"""
批量生成任务状态管理器 - 数据库同步模块

从 task_manager.py 拆分，包含所有数据库同步方法。

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Optional, Dict, Any

from sqlalchemy import select

from app.core.logger import get_logger
from app.core.database import async_session_maker
from app.models import NovelProject
from app.repositories.novel_project import NovelProjectRepository

logger = get_logger("task_manager")

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


__all__ = [
    "set_novel_project_repo",
    "sync_task_to_db",
    "get_task_from_db",
    "clear_task_in_db",
    "_novel_project_repo",
]
