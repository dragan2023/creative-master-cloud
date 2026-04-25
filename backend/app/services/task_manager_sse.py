# -*- coding: utf-8 -*-
"""
任务SSE订阅管理

从 task_manager.py 提取的 SSE 订阅管理功能。
管理每个项目对应的 SSE 订阅队列，支持添加/移除订阅者和推送事件。
"""
import json
import asyncio
from typing import Dict, Set, Any

from app.core.logger import get_logger

logger = get_logger("task_manager")

# SSE 订阅管理：每个项目ID对应一组订阅者队列
_sse_subscribers: Dict[int, Set[asyncio.Queue]] = {}


def subscribe_task_events(project_id: int) -> asyncio.Queue:
    """
    订阅项目的任务事件
    返回一个队列，调用者可以从队列中获取任务更新事件
    """
    if project_id not in _sse_subscribers:
        _sse_subscribers[project_id] = set()
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


__all__ = [
    "subscribe_task_events",
    "unsubscribe_task_events",
    "notify_task_update",
]
