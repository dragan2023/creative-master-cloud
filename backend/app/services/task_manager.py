"""批量生成任务状态管理器（GenerationTaskManager）

用于追踪和持久化生成任务状态，支持跨会话查询和取消。
支持 Redis 不可用时使用内存令牌作为后备。
同时同步任务状态到数据库，确保服务器重启后状态不丢失。
支持 SSE 实时推送任务状态更新。

区别说明:
    - 本模块: 批量生成任务的状态管理（进度追踪、取消、持久化）
    - writing_engine/task_manager.py: 写作任务的CRUD服务（数据库操作）

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import json
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.redis_client import redis_manager
from app.core.logger import get_logger
from app.services.task_manager_sse import (
    subscribe_task_events,
    unsubscribe_task_events,
    notify_task_update,
)
from app.services.task_manager_db import (
    set_novel_project_repo,
    sync_task_to_db,
    get_task_from_db,
    clear_task_in_db,
)

logger = get_logger("task_manager")

# 任务状态与类型常量（从独立模块导入）
from app.services.task_manager_constants import (
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_FAILED,
    TASK_TYPE_EPISODE_OUTLINE,
    TASK_TYPE_CHAPTER_OUTLINE,
    TASK_TYPE_SCENE_OUTLINE,
    TASK_TYPE_EPISODE_CONTENT,
    TASK_TYPE_CHAPTER_CONTENT,
    TASK_TYPE_SCENE_CONTENT,
)

# 内存取消令牌（从独立模块导入）
from app.services.task_manager_cancel import (
    set_memory_cancel_token,
    get_memory_cancel_token,
    clear_memory_cancel_token,
    trigger_memory_cancel,
    is_memory_cancelled,
)
from app.services.task_manager_steps import (
    update_task_step as _update_task_step_impl,
    notify_intervention_request as _notify_intervention_request_impl,
)


class TaskManager:
    """批量生成任务管理器"""

    # 任务过期时间（默认24小时）
    TASK_EXPIRE_SECONDS = 86400

    @staticmethod
    def _get_task_key(project_id: int) -> str:
        """获取任务的Redis键"""
        return f"novel_writer:task:{project_id}"

    @staticmethod
    async def _sync_task_to_db(project_id: int, task: Dict[str, Any]):
        """同步任务状态到数据库"""
        try:
            if _novel_project_repo:
                project = await _novel_project_repo.get(project_id)
                if project:
                    project.generation_task_type = task.get("task_type")
                    project.generation_task_status = task.get("status")
                    project.generation_task_total = task.get("total_count", 0)
                    project.generation_task_completed = task.get(
                        "completed_count", 0)
                    project.generation_task_failed = task.get(
                        "failed_count", 0)
                    project.generation_task_skipped = task.get(
                        "skipped_count", 0)
                    project.generation_task_current = task.get("current_item")
                    project.generation_task_started_at = task.get("started_at")
                    project.generation_task_updated_at = task.get("updated_at")
                    await _novel_project_repo.session.commit()
                return
            # Fallback: 直连 session
            from app.core.database import async_session_maker
            async with async_session_maker() as db:
                query = await db.execute(
                    select(NovelProject).where(NovelProject.id == project_id)
                )
                project = query.scalar_one_or_none()
                if project:
                    project.generation_task_type = task.get("task_type")
                    project.generation_task_status = task.get("status")
                    project.generation_task_total = task.get("total_count", 0)
                    project.generation_task_completed = task.get(
                        "completed_count", 0)
                    project.generation_task_failed = task.get(
                        "failed_count", 0)
                    project.generation_task_skipped = task.get(
                        "skipped_count", 0)
                    project.generation_task_current = task.get("current_item")
                    project.generation_task_started_at = task.get("started_at")
                    project.generation_task_updated_at = task.get("updated_at")
                    await db.commit()
        except Exception as e:
            logger.error(f"同步任务状态到数据库失败: {e}", exc_info=True)
            # 【修复 #6】抛出异常让调用方感知同步失败
            raise

    @staticmethod
    async def _get_task_from_db(project_id: int) -> Optional[Dict[str, Any]]:
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
            from app.core.database import async_session_maker
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

    @staticmethod
    async def _clear_task_in_db(project_id: int):
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
            from app.core.database import async_session_maker
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

    @staticmethod
    async def create_task(
        project_id: int,
        task_type: str,
        total_count: int = 0,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        创建新任务

        Args:
            project_id: 项目ID
            task_type: 任务类型
            total_count: 总数量
            metadata: 额外元数据

        Returns:
            任务信息字典
        """
        now = datetime.now().isoformat()
        task = {
            "project_id": project_id,
            "task_type": task_type,
            "status": TASK_STATUS_RUNNING,
            "total_count": total_count,
            "completed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "current_item": None,
            "current_step": None,  # 当前步骤信息
            "steps_history": [],   # 历史步骤记录
            "started_at": now,
            "updated_at": now,
            "metadata": metadata or {}
        }

        key = TaskManager._get_task_key(project_id)
        await redis_manager.set(key, json.dumps(task), expire=TaskManager.TASK_EXPIRE_SECONDS)

        # 同步到数据库
        await sync_task_to_db(project_id, task)

        # 通知所有 SSE 订阅者新任务已创建
        await notify_task_update(project_id, task)

        logger.info(f"创建任务: project_id={project_id}, type={task_type}")
        return task

    @staticmethod
    async def get_task(project_id: int) -> Optional[Dict[str, Any]]:
        """
        获取当前任务状态

        优先从 Redis 获取，如果 Redis 中没有（可能是服务器重启），
        则尝试从数据库恢复任务状态。

        Args:
            project_id: 项目ID

        Returns:
            任务信息字典，无任务时返回None
        """
        key = TaskManager._get_task_key(project_id)
        task_json = await redis_manager.get(key)

        if task_json:
            return json.loads(task_json)

        # Redis 中没有，尝试从数据库恢复
        task = await get_task_from_db(project_id)
        if task:
            # 服务器重启后，数据库中 running 的任务实际上已中断
            # main.py 启动时会将其改为 failed，但此处做二次兜底
            # 注意：此处不再将 running 任务恢复到内存，只读取返回
            return task

        return None

    @staticmethod
    async def update_task(
        project_id: int,
        completed_count: int = None,
        failed_count: int = None,
        skipped_count: int = None,
        current_item: int = None,
        status: str = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        更新任务进度

        Args:
            project_id: 项目ID
            completed_count: 已完成数量
            failed_count: 失败数量
            skipped_count: 跳过数量
            current_item: 当前处理项
            status: 新状态
            metadata: 要合并的元数据

        Returns:
            更新后的任务信息
        """
        task = await TaskManager.get_task(project_id)
        if not task:
            return None

        if completed_count is not None:
            task["completed_count"] = completed_count
        if failed_count is not None:
            task["failed_count"] = failed_count
        if skipped_count is not None:
            task["skipped_count"] = skipped_count
        if current_item is not None:
            task["current_item"] = current_item
        if status is not None:
            task["status"] = status
        if metadata:
            task["metadata"].update(metadata)

        task["updated_at"] = datetime.now().isoformat()

        key = TaskManager._get_task_key(project_id)
        await redis_manager.set(key, json.dumps(task), expire=TaskManager.TASK_EXPIRE_SECONDS)

        # 同步到数据库
        await sync_task_to_db(project_id, task)

        # 通知所有 SSE 订阅者任务状态更新
        await notify_task_update(project_id, task)

        return task

    @staticmethod
    async def update_task_step(
        project_id: int,
        step_key: str,
        step_message: str,
        step_status: str = "running",
        step_icon: str = None,
        item_name: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        更新任务当前步骤信息

        Args:
            project_id: 项目ID
            step_key: 步骤键名（如 'context', 'llm', 'parse' 等）
            step_message: 步骤描述信息
            step_status: 步骤状态（'running', 'done', 'error'）
            step_icon: 步骤图标（前端显示用）
            item_name: 当前处理的项名称（如 "第1章"）

        Returns:
            更新后的任务信息
        """
        return await _update_task_step_impl(project_id, step_key, step_message, step_status, step_icon, item_name)

    @staticmethod
    async def complete_task(project_id: int, success: bool = True) -> Optional[Dict[str, Any]]:
        """
        标记任务完成

        Args:
            project_id: 项目ID
            success: 是否成功

        Returns:
            完成的任务信息
        """
        status = TASK_STATUS_COMPLETED if success else TASK_STATUS_FAILED
        task = await TaskManager.update_task(project_id, status=status)

        if task:
            logger.info(f"任务完成: project_id={project_id}, status={status}")
            # 同步到数据库
            await sync_task_to_db(project_id, task)
        return task

    @staticmethod
    async def cancel_task(project_id: int) -> Optional[Dict[str, Any]]:
        """
        取消任务

        Args:
            project_id: 项目ID

        Returns:
            被取消的任务信息
        """
        task = await TaskManager.update_task(project_id, status=TASK_STATUS_CANCELLED)

        if task:
            logger.info(f"任务已取消: project_id={project_id}")
        return task

    @staticmethod
    async def notify_intervention_request(project_id: int, intervention_info: Dict[str, Any]) -> None:
        """
        推送用户干预请求到SSE

        Args:
            project_id: 项目ID
            intervention_info: 干预请求信息
        """
        await _notify_intervention_request_impl(project_id, intervention_info)

    @staticmethod
    async def delete_task(project_id: int) -> bool:
        """
        删除任务记录

        Args:
            project_id: 项目ID

        Returns:
            是否删除成功
        """
        key = TaskManager._get_task_key(project_id)
        result = await redis_manager.delete(key)

        # 同时清除数据库中的任务状态
        await clear_task_in_db(project_id)

        return result > 0

    @staticmethod
    async def is_task_running(project_id: int) -> bool:
        """
        检查是否有正在运行的任务

        Args:
            project_id: 项目ID

        Returns:
            是否有运行中的任务
        """
        task = await TaskManager.get_task(project_id)
        return task is not None and task.get("status") == TASK_STATUS_RUNNING

    @staticmethod
    async def is_task_cancelled(project_id: int) -> bool:
        """
        检查任务是否被取消

        同时检查 Redis 任务状态和内存取消令牌。
        当 Redis 不可用时，内存令牌提供即时取消功能。

        Args:
            project_id: 项目ID

        Returns:
            任务是否被取消
        """
        # 首先检查内存取消令牌（即时生效）
        if is_memory_cancelled(project_id):
            return True

        # 然后检查 Redis 任务状态
        task = await TaskManager.get_task(project_id)
        return task is not None and task.get("status") == TASK_STATUS_CANCELLED


# 全局任务管理器实例
task_manager = TaskManager()
