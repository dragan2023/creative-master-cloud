"""知识库API - 共享状态

包含进度存储、线程池等共享模块状态
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from app.core.logger import get_logger
from app.core.redis_client import redis_manager
from app.models.base import get_local_now

logger = get_logger(__name__)

# Redis 进度存储配置
KB_PROGRESS_PREFIX = "kb_progress:"
KB_PROGRESS_EXPIRE = 3600  # 1小时过期

# 知识库处理进度状态存储
kb_processing_progress: Dict[int, Dict[str, Any]] = {}

# 存储正在运行的处理任务（用于终止）
kb_processing_tasks: Dict[int, Dict[str, Any]] = {}

# 知识库处理线程池，限制最大并发数
KB_MAX_CONCURRENT = 5
kb_thread_pool = ThreadPoolExecutor(
    max_workers=KB_MAX_CONCURRENT, thread_name_prefix="kb_process")


def _sync_update_kb_progress(kb_id: int, progress_data: Dict[str, Any]):
    """同步更新知识库进度到 Redis（用于后台线程）"""
    key = f"{KB_PROGRESS_PREFIX}{kb_id}"
    data = json.dumps(progress_data, ensure_ascii=False)
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    redis_manager.set(key, data, expire=KB_PROGRESS_EXPIRE),
                    loop
                )
                future.result(timeout=5)
            else:
                loop.run_until_complete(redis_manager.set(
                    key, data, expire=KB_PROGRESS_EXPIRE))
        except RuntimeError:
            asyncio.run(redis_manager.set(
                key, data, expire=KB_PROGRESS_EXPIRE))
    except Exception as e:
        logger.debug(f"Redis 进度更新失败，降级到内存: {e}")


async def _async_get_kb_progress(kb_id: int) -> Dict[str, Any]:
    """异步获取知识库进度"""
    key = f"{KB_PROGRESS_PREFIX}{kb_id}"
    try:
        data = await redis_manager.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.debug(f"Redis 进度获取失败，降级到内存: {e}")
    return kb_processing_progress.get(kb_id, {
        "kb_id": kb_id,
        "current_step": "",
        "progress": 0,
        "total_steps": 6,
        "current_step_index": 0,
        "error": None,
        "status": "unknown",
        "is_processing": False,
        "updated_at": None
    })


async def _async_delete_kb_progress(kb_id: int):
    """异步删除知识库进度"""
    key = f"{KB_PROGRESS_PREFIX}{kb_id}"
    try:
        await redis_manager.delete(key)
    except Exception as e:
        logger.debug(f"Redis 进度删除失败: {e}")
    kb_processing_progress.pop(kb_id, None)


async def _async_get_all_kb_progress() -> List[Dict[str, Any]]:
    """异步获取所有正在处理的知识库进度"""
    result = []
    for kb_id in list(kb_processing_progress.keys()):
        progress = await _async_get_kb_progress(kb_id)
        if progress.get("is_processing", False):
            result.append(progress)
    return result


def update_kb_progress(kb_id: int, step: str, progress: int, step_index: int, error: str = None, total_steps: int = 6):
    """更新知识库处理进度（同时写入内存和 Redis）"""
    if error and not error.startswith("KB-"):
        prefix = "KB-PARSE-001" if step_index == 1 else "KB-PROCESS-001"
        error = f"{prefix}: {error}"
    status = "failed" if error else ("completed" if progress >= 100 else "processing")
    progress_data = {
        "kb_id": kb_id,
        "current_step": step,
        "progress": progress,
        "total_steps": total_steps,
        "current_step_index": step_index,
        "error": error,
        "status": status,
        "is_processing": error is None and progress < 100,
        "updated_at": get_local_now().isoformat()
    }
    kb_processing_progress[kb_id] = progress_data
    _sync_update_kb_progress(kb_id, progress_data)


def get_kb_progress(kb_id: int) -> Dict[str, Any]:
    """获取知识库处理进度"""
    return kb_processing_progress.get(kb_id, {
        "kb_id": kb_id,
        "current_step": "",
        "progress": 0,
        "total_steps": 6,
        "current_step_index": 0,
        "error": None,
        "status": "unknown",
        "is_processing": False,
        "updated_at": None
    })


def get_all_processing_progress() -> List[Dict[str, Any]]:
    """获取所有正在处理的知识库进度"""
    processing_list = []
    for kb_id, progress in kb_processing_progress.items():
        if progress.get("is_processing", False):
            processing_list.append(progress)
    return processing_list


def register_kb_task(kb_id: int, future=None, stop_event=None):
    """注册知识库处理任务"""
    kb_processing_tasks[kb_id] = {
        "future": future,
        "stop_event": stop_event,
        "started_at": get_local_now().isoformat()
    }


def unregister_kb_task(kb_id: int):
    """注销知识库处理任务"""
    if kb_id in kb_processing_tasks:
        del kb_processing_tasks[kb_id]


def stop_kb_processing(kb_id: int) -> bool:
    """终止知识库处理进程"""
    if kb_id in kb_processing_tasks:
        task_info = kb_processing_tasks[kb_id]
        stop_event = task_info.get("stop_event")
        if stop_event:
            stop_event.set()
            logger.info(f"已设置停止信号: kb_id={kb_id}")
        update_kb_progress(kb_id, "处理已终止", 0, 0, error="用户手动终止")
        return True

    progress = get_kb_progress(kb_id)
    if progress.get("is_processing", False):
        update_kb_progress(kb_id, "处理已终止", 0, 0, error="用户手动终止")
        return True

    return False
