"""
批量生成任务状态管理器 - 数据库同步模块

从 task_manager.py 拆分，包含所有数据库同步方法。
每个操作通过 Session Factory 创建独立的短生命周期 Session，
避免长期共享 AsyncSession 引发的并发冲突。

@date: 2026-04-24
@version: v2.0.0
"""
from collections.abc import Callable
from typing import Optional, Dict, Any
import warnings

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logger import get_logger
from app.core.database import async_session_maker
from app.repositories.novel_project import NovelProjectRepository

logger = get_logger("task_manager")

# Session 工厂（默认使用全局 async_session_maker，启动期或测试可注入替换）
_session_factory: Callable[[], AsyncSession] = async_session_maker


def set_session_factory(factory: Callable[[], AsyncSession]) -> None:
    """注入 Session 工厂（由启动期调用，测试时可注入伪工厂）"""
    global _session_factory
    _session_factory = factory


def set_novel_project_repo(repo: NovelProjectRepository) -> None:
    """Deprecated adapter that derives a short-lived Session factory.

    The repository instance itself is never retained or reused.  Only its
    AsyncSession bind is used to construct a factory that creates a distinct
    session for every database operation.
    """
    warnings.warn(
        "set_novel_project_repo() is deprecated; use set_session_factory()",
        DeprecationWarning,
        stacklevel=2,
    )
    session = getattr(repo, "session", None)
    bind = getattr(session, "bind", None)
    if bind is None:
        raise TypeError(
            "set_novel_project_repo() requires repo.session to be an "
            "AsyncSession with a configured bind"
        )

    factory = async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    set_session_factory(factory)


def _apply_task_fields(project, task: Dict[str, Any]) -> None:
    """将任务状态写入项目实体的任务追踪字段"""
    project.generation_task_type = task.get("task_type")
    project.generation_task_status = task.get("status")
    project.generation_task_total = task.get("total_count", 0)
    project.generation_task_completed = task.get("completed_count", 0)
    project.generation_task_failed = task.get("failed_count", 0)
    project.generation_task_skipped = task.get("skipped_count", 0)
    project.generation_task_current = task.get("current_item")
    project.generation_task_started_at = task.get("started_at")
    project.generation_task_updated_at = task.get("updated_at")


def _reset_task_fields(project) -> None:
    """清空项目实体上的任务追踪字段"""
    project.generation_task_type = None
    project.generation_task_status = None
    project.generation_task_total = 0
    project.generation_task_completed = 0
    project.generation_task_failed = 0
    project.generation_task_skipped = 0
    project.generation_task_current = None
    project.generation_task_started_at = None
    project.generation_task_updated_at = None


def _project_to_task_dict(project_id: int, project) -> Dict[str, Any]:
    """将项目实体上的任务字段转换为任务状态字典（结构保持不变）"""
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


async def sync_task_to_db(project_id: int, task: Dict[str, Any]):
    """同步任务状态到数据库

    写入失败会记录错误日志后重新抛出，让调用方感知同步失败。
    Session 由 async with 保证在正常与异常路径均退出。
    """
    try:
        async with _session_factory() as session:
            repo = NovelProjectRepository(session)
            project = await repo.get(project_id)
            if project:
                _apply_task_fields(project, task)
                await session.commit()
    except Exception as e:
        logger.error(
            f"同步任务状态到数据库失败: project_id={project_id}, error={e}",
            exc_info=True,
        )
        raise


async def get_task_from_db(project_id: int) -> Optional[Dict[str, Any]]:
    """从数据库获取任务状态

    读取失败返回 None（记录警告日志），Session 保证退出。
    """
    try:
        async with _session_factory() as session:
            repo = NovelProjectRepository(session)
            project = await repo.get(project_id)
            if project and project.generation_task_status:
                return _project_to_task_dict(project_id, project)
    except Exception as e:
        logger.warning(f"从数据库获取任务状态失败: project_id={project_id}, error={e}")
    return None


async def clear_task_in_db(project_id: int):
    """清除数据库中的任务状态

    清除失败会回滚、记录项目 ID 并原样重新抛出，Session 保证退出。
    """
    try:
        async with _session_factory() as session:
            try:
                repo = NovelProjectRepository(session)
                project = await repo.get(project_id)
                if project:
                    _reset_task_fields(project)
                    await session.commit()
            except Exception:
                try:
                    await session.rollback()
                except Exception as rollback_error:
                    logger.error(
                        f"回滚数据库任务清理失败: project_id={project_id}, "
                        f"error={rollback_error}",
                        exc_info=True,
                    )
                raise
    except Exception as e:
        logger.warning(
            f"清除数据库任务状态失败: project_id={project_id}, error={e}",
            exc_info=True,
        )
        raise


__all__ = [
    "set_session_factory",
    "set_novel_project_repo",
    "sync_task_to_db",
    "get_task_from_db",
    "clear_task_in_db",
]
