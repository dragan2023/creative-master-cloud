"""
批量生成任务状态管理器
用于追踪和持久化生成任务状态，支持跨会话查询和取消
支持 Redis 不可用时使用内存令牌作为后备
同时同步任务状态到数据库，确保服务器重启后状态不丢失
支持 SSE 实时推送任务状态更新
"""
import json
import asyncio
from typing import Optional, Dict, Any, Set
from datetime import datetime
from collections import defaultdict

from sqlalchemy import select

from app.core.redis_client import redis_manager
from app.core.logger import get_logger
from app.core.database import async_session_maker
from app.models import NovelProject

logger = get_logger("task_manager")

# SSE 订阅管理：每个项目ID对应一组订阅者队列
_sse_subscribers: Dict[int, Set[asyncio.Queue]] = defaultdict(set)

# 任务状态常量
TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_CANCELLED = "cancelled"
TASK_STATUS_FAILED = "failed"

# 任务类型常量
TASK_TYPE_EPISODE_OUTLINE = "episode_outline"      # 分集大纲
TASK_TYPE_CHAPTER_OUTLINE = "chapter_outline"      # 章节大纲
TASK_TYPE_SCENE_OUTLINE = "scene_outline"          # 场景大纲
TASK_TYPE_EPISODE_CONTENT = "episode_content"      # 分集正文
TASK_TYPE_CHAPTER_CONTENT = "chapter_content"      # 章节正文
TASK_TYPE_SCENE_CONTENT = "scene_content"          # 场景正文

# 内存取消令牌字典（当 Redis 不可用时使用）
_memory_cancel_tokens: Dict[int, asyncio.Event] = {}


def set_memory_cancel_token(project_id: int) -> asyncio.Event:
    """为项目创建内存取消令牌"""
    event = asyncio.Event()
    _memory_cancel_tokens[project_id] = event
    return event


def get_memory_cancel_token(project_id: int) -> Optional[asyncio.Event]:
    """获取项目的内存取消令牌"""
    return _memory_cancel_tokens.get(project_id)


def clear_memory_cancel_token(project_id: int):
    """清除项目的内存取消令牌"""
    if project_id in _memory_cancel_tokens:
        del _memory_cancel_tokens[project_id]


def trigger_memory_cancel(project_id: int):
    """触发内存取消令牌"""
    token = _memory_cancel_tokens.get(project_id)
    if token:
        token.set()
        logger.info(f"已触发内存取消令牌: project_id={project_id}")


def is_memory_cancelled(project_id: int) -> bool:
    """检查内存取消令牌是否被触发"""
    token = _memory_cancel_tokens.get(project_id)
    return token is not None and token.is_set()


# ==================== SSE 订阅管理 ====================

def subscribe_task_events(project_id: int) -> asyncio.Queue:
    """
    订阅项目的任务事件
    返回一个队列，调用者可以从队列中获取任务更新事件
    """
    queue = asyncio.Queue()
    _sse_subscribers[project_id].add(queue)
    logger.debug(
        f"SSE 订阅: project_id={project_id}, 当前订阅者数={len(_sse_subscribers[project_id])}")
    return queue


def unsubscribe_task_events(project_id: int, queue: asyncio.Queue):
    """
    取消订阅项目的任务事件
    """
    if project_id in _sse_subscribers:
        _sse_subscribers[project_id].discard(queue)
        if not _sse_subscribers[project_id]:
            del _sse_subscribers[project_id]
    logger.debug(f"SSE 取消订阅: project_id={project_id}")


async def notify_task_update(project_id: int, task: Dict[str, Any]):
    """
    通知所有订阅者任务状态更新
    当任务状态变化时调用此函数，将事件推送给所有 SSE 客户端
    """
    if project_id not in _sse_subscribers:
        return

    event_data = json.dumps(task, ensure_ascii=False)
    dead_queues = set()

    for queue in _sse_subscribers[project_id]:
        try:
            # 非阻塞放入，如果队列满则跳过
            queue.put_nowait(event_data)
        except asyncio.QueueFull:
            logger.warning(f"SSE 队列已满，跳过: project_id={project_id}")
        except Exception as e:
            # 队列可能已关闭，标记为死连接
            dead_queues.add(queue)
            logger.debug(f"SSE 队列异常: {e}")

    # 清理失效的订阅者
    for queue in dead_queues:
        _sse_subscribers[project_id].discard(queue)


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
            logger.warning(f"同步任务状态到数据库失败: {e}")

    @staticmethod
    async def _get_task_from_db(project_id: int) -> Optional[Dict[str, Any]]:
        """从数据库获取任务状态"""
        try:
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
        await TaskManager._sync_task_to_db(project_id, task)

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
        task = await TaskManager._get_task_from_db(project_id)
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
        await TaskManager._sync_task_to_db(project_id, task)

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
        task = await TaskManager.get_task(project_id)
        if not task:
            return None

        now = datetime.now()
        current_step = {
            "key": step_key,
            "message": step_message,
            "status": step_status,
            "icon": step_icon,
            "timestamp": now.isoformat()
        }

        # 更新当前步骤
        task["current_step"] = current_step

        # 如果步骤完成，添加到历史记录
        if step_status == "done":
            # 计算步骤耗时
            step_duration_ms = 0
            # 查找同key的running步骤开始时间
            steps_history = task.get("steps_history", [])
            for prev_step in reversed(steps_history):
                if prev_step.get("key") == step_key and prev_step.get("status") == "running":
                    try:
                        start_time = datetime.fromisoformat(
                            prev_step["timestamp"])
                        step_duration_ms = int(
                            (now - start_time).total_seconds() * 1000)
                    except:
                        pass
                    break

            current_step["duration_ms"] = step_duration_ms
            steps_history.append(current_step)
            task["steps_history"] = steps_history[-20:]  # 只保留最近20条
        elif step_status == "running":
            # 添加running状态到历史
            steps_history = task.get("steps_history", [])
            steps_history.append(current_step)
            task["steps_history"] = steps_history[-20:]
        elif step_status == "error":
            # 错误步骤也添加到历史
            steps_history = task.get("steps_history", [])
            steps_history.append(current_step)
            task["steps_history"] = steps_history[-20:]

        # 更新当前处理项名称
        if item_name:
            task["current_item_name"] = item_name

        task["updated_at"] = now.isoformat()

        key = TaskManager._get_task_key(project_id)
        await redis_manager.set(key, json.dumps(task), expire=TaskManager.TASK_EXPIRE_SECONDS)

        # 通知所有 SSE 订阅者步骤更新
        await notify_task_update(project_id, task)

        return task

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
            await TaskManager._sync_task_to_db(project_id, task)
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
        # 获取当前任务
        task = await TaskManager.get_task(project_id)
        if not task:
            logger.warning(f"推送干预请求失败: 未找到任务 project_id={project_id}")
            return

        # 构建干预请求事件
        event_data = {
            "type": "intervention_request",
            "project_id": project_id,
            "intervention": intervention_info,
            "task": task,
            "timestamp": datetime.now().isoformat()
        }

        # 通过SSE推送干预请求
        await notify_task_update(project_id, {
            **task,
            "intervention_request": intervention_info
        })

        logger.info(
            f"干预请求已推送: project_id={project_id}, chapter={intervention_info.get('chapter_number')}")

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
        await TaskManager._clear_task_in_db(project_id)

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
