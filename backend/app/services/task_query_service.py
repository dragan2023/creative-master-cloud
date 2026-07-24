# -*- coding: utf-8 -*-
"""
批量生成任务 → WritingTask 持久化查询服务

职责：
    - 将 Redis 批量任务字典的读写映射到 WritingTask 表，替代已删除的
      NovelProject.generation_task_* 字段。
    - 提供与旧 get_task_from_db / sync_task_to_db / clear_task_in_db
      兼容的接口签名，调用方无需感知底层表结构变更。

设计约束：
    - 本模块是「杂食适配层」：输入 Redis 任务字典，输出仍为字典。
    - WritingTask 是唯一持久化事实来源；Redis 是暂态存储。
    - 不存在 WritingTask 记录时为「无任务」，返回 None，绝不伪造运行中状态。

@date: 2026-07-23
@version: v1.0.0
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.writing_task import WritingTask, TaskStatus
from app.models import NovelProject
from app.services.task_manager_constants import (
    TASK_STATUS_RUNNING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_PENDING,
    TASK_STATUS_INTERRUPTED,
    is_terminal_task_status,
)

logger = get_logger("task_query_service")

# ── Redis 状态字符串 ⇄ WritingTask TaskStatus 枚举映射 ──────────────────────
_STATUS_TO_WT: Dict[str, TaskStatus] = {
    TASK_STATUS_PENDING: TaskStatus.PENDING,
    TASK_STATUS_RUNNING: TaskStatus.RUNNING,
    TASK_STATUS_COMPLETED: TaskStatus.COMPLETED,
    TASK_STATUS_FAILED: TaskStatus.FAILED,
    TASK_STATUS_CANCELLED: TaskStatus.CANCELLED,
    TASK_STATUS_INTERRUPTED: TaskStatus.INTERRUPTED,
}

_WT_TO_STATUS: Dict[TaskStatus, str] = {v: k for k, v in _STATUS_TO_WT.items()}

# ── 公开接口 ────────────────────────────────────────────────────────────────


async def get_task_for_project(
    db: AsyncSession,
    project_id: int,
) -> Optional[Dict[str, Any]]:
    """查询项目最新的非终态 WritingTask，转换为 Redis 兼容字典。

    返回值语义：
        - None：无任务（从不存在，或全部已到达终态）
        - Dict：与旧 get_task_from_db 返回结构兼容的字典

    终态任务不返回——已完成的旧任务不应干扰当前批量进度查询。
    """
    result = await db.execute(
        select(WritingTask)
        .where(
            and_(
                WritingTask.project_id == project_id,
                WritingTask.status.in_(
                    [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.CANCELLING]
                ),
            )
        )
        .order_by(WritingTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None
    return _writing_task_to_dict(task)


async def get_latest_task_for_project(
    db: AsyncSession,
    project_id: int,
) -> Optional[Dict[str, Any]]:
    """查询项目最新的 WritingTask（含终态），用于重启恢复场景。

    与 get_task_for_project 的区别：当 Redis 不可用且最后一个
    WritingTask 正处在终态时，此函数仍返回该记录供上层判断。
    """
    result = await db.execute(
        select(WritingTask)
        .where(WritingTask.project_id == project_id)
        .order_by(WritingTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None
    return _writing_task_to_dict(task)


async def sync_task_to_writing_task(
    db: AsyncSession,
    project_id: int,
    task_dict: Dict[str, Any],
) -> Optional[int]:
    """将 Redis 任务字典同步到 WritingTask 表。

    行为：
        - 若 task_dict 中包含 writing_task_db_id 且记录存在 → 更新
        - 否则创建新的 WritingTask 记录
        - 创建时需要 project.user_id，从 NovelProject 读取

    Returns:
        writing_task_id (int)，失败返回 None
    """
    try:
        existing_id = task_dict.get("writing_task_db_id")
        if existing_id is not None:
            existing = await db.get(WritingTask, existing_id)
            if existing is not None:
                _apply_task_dict_to_writing_task(existing, task_dict)
                await db.commit()
                return existing.id

        # 获取 project.user_id
        proj_result = await db.execute(
            select(NovelProject.user_id).where(NovelProject.id == project_id)
        )
        user_id = proj_result.scalar_one_or_none()
        if user_id is None:
            logger.warning(f"项目不存在，无法同步任务: project_id={project_id}")
            return None

        new_task = WritingTask(
            project_id=project_id,
            user_id=user_id,
            status=TaskStatus.PENDING,
            total_units=0,
            completed_units=0,
        )
        _apply_task_dict_to_writing_task(new_task, task_dict)
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)

        # 回写 ID 到 Redis 任务字典，下次同步使用
        task_dict["writing_task_db_id"] = new_task.id
        logger.info(
            f"创建 WritingTask 记录: id={new_task.id}, project_id={project_id}, "
            f"status={new_task.status}"
        )
        return new_task.id
    except Exception:
        logger.error(f"同步任务到 WritingTask 失败: project_id={project_id}", exc_info=True)
        await db.rollback()
        return None


async def clear_task_in_writing_task(
    db: AsyncSession,
    task_dict: Optional[Dict[str, Any]] = None,
) -> None:
    """将关联的 WritingTask 标记为终态（cancelled）。

    不再强行置空字段——WritingTask 保留历史记录，
    仅将状态迁移到终态。
    """
    if not task_dict:
        return
    writing_task_db_id = task_dict.get("writing_task_db_id")
    if writing_task_db_id is None:
        return
    try:
        task = await db.get(WritingTask, writing_task_db_id)
        if task is not None and not is_terminal_task_status(task.status):
            task.status = TaskStatus.CANCELLED
            task.end_time = datetime.now()
            await db.commit()
            logger.info(
                f"WritingTask 已标记取消: id={task.id}, project_id={task.project_id}"
            )
    except Exception:
        logger.warning(
            f"清除 WritingTask 状态失败: project_id={task.project_id}",
            exc_info=True,
        )
        await db.rollback()


# ── 内部辅助 ────────────────────────────────────────────────────────────────


def _writing_task_to_dict(task: WritingTask) -> Dict[str, Any]:
    """将 WritingTask ORM 对象转换为 Redis 兼容的任务字典。"""
    config: Dict[str, Any] = task.config or {}
    return {
        "project_id": task.project_id,
        "task_type": config.get("task_type"),
        "status": _WT_TO_STATUS.get(task.status),
        "total_count": task.total_units or 0,
        "completed_count": task.completed_units or 0,
        "failed_count": config.get("failed_count", 0),
        "skipped_count": config.get("skipped_count", 0),
        "current_item": config.get("current_item"),
        "started_at": task.start_time.isoformat() if task.start_time else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "metadata": config.get("metadata", {}),
        "writing_task_db_id": task.id,
    }


def _apply_task_dict_to_writing_task(
    wt: WritingTask,
    task_dict: Dict[str, Any],
) -> None:
    """将 Redis 任务字典的数据写入 WritingTask 对象字段。"""
    redis_status: str = task_dict.get("status", "")
    if redis_status in _STATUS_TO_WT:
        wt.status = _STATUS_TO_WT[redis_status]

    wt.total_units = task_dict.get("total_count", wt.total_units or 0)
    wt.completed_units = task_dict.get("completed_count", wt.completed_units or 0)

    # 任务类型与扩展字段存入 config JSON（创建新字典确保 ORM 检测变更）
    config: Dict[str, Any] = dict(wt.config or {})
    if task_dict.get("task_type"):
        config["task_type"] = task_dict["task_type"]
    if "failed_count" in task_dict:
        config["failed_count"] = task_dict["failed_count"]
    if "skipped_count" in task_dict:
        config["skipped_count"] = task_dict["skipped_count"]
    if "current_item" in task_dict:
        config["current_item"] = task_dict["current_item"]
    if task_dict.get("metadata"):
        config["metadata"] = task_dict["metadata"]
    wt.config = config

    # 时间字段
    started_at = task_dict.get("started_at")
    if started_at and wt.start_time is None:
        try:
            wt.start_time = datetime.fromisoformat(str(started_at))
        except (ValueError, TypeError):
            pass

    # 若迁入终态，写入 end_time
    if is_terminal_task_status(redis_status) and wt.end_time is None:
        wt.end_time = datetime.now()
