"""
任务管理器 - 步骤更新与干预请求模块

从 task_manager.py 拆分出的步骤更新和干预请求功能。

@date: 2026-04-25
"""
from datetime import datetime
from typing import Dict, Any, Optional

from app.core.logger import get_logger
from app.services.task_manager_sse import notify_task_update

logger = get_logger("task_manager.steps")


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
    # 延迟导入避免循环依赖
    from app.services.task_manager import TaskManager

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
                except (ValueError, TypeError) as e:
                    logger.warning(f"解析步骤时间失败: {e}")
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

    from app.services.task_manager import TaskManager as TM
    key = TM._get_task_key(project_id)
    import json
    from app.core.redis_client import redis_manager
    await redis_manager.set(key, json.dumps(task), expire=TM.TASK_EXPIRE_SECONDS)

    # 通知所有 SSE 订阅者步骤更新
    await notify_task_update(project_id, task)

    return task


async def notify_intervention_request(project_id: int, intervention_info: Dict[str, Any]) -> None:
    """
    推送用户干预请求到SSE

    Args:
        project_id: 项目ID
        intervention_info: 干预请求信息
    """
    # 延迟导入避免循环依赖
    from app.services.task_manager import TaskManager

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
