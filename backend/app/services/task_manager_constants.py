# -*- coding: utf-8 -*-
"""
批量生成任务常量定义

从 task_manager.py 提取的任务状态和任务类型常量。
"""
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

__all__ = [
    "TASK_STATUS_PENDING",
    "TASK_STATUS_RUNNING",
    "TASK_STATUS_COMPLETED",
    "TASK_STATUS_CANCELLED",
    "TASK_STATUS_FAILED",
    "TASK_TYPE_EPISODE_OUTLINE",
    "TASK_TYPE_CHAPTER_OUTLINE",
    "TASK_TYPE_SCENE_OUTLINE",
    "TASK_TYPE_EPISODE_CONTENT",
    "TASK_TYPE_CHAPTER_CONTENT",
    "TASK_TYPE_SCENE_CONTENT",
]
