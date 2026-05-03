"""
小说/剧本正文生成模块 Schema 定义
包含请求和响应模型

【重要说明】
本模块专注于根据用户上传的大纲进行正文创作，不提供大纲生成功能。
大纲生成功能由创意生成板块（/generate）提供。
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


# ==================== 枚举类型 ====================



class ContentType(str, Enum):
    """内容类型（三种独立类型，参数完全隔离）"""
    NOVEL = "novel"                      # 小说
    SERIES_SCRIPT = "series_script"      # 剧集剧本
    MOVIE_SCRIPT = "movie_script"        # 电影剧本


# 保留旧的ProjectType以兼容数据库模型


class ProjectType(str, Enum):
    """项目类型（数据库兼容用，新代码请使用ContentType）"""
    NOVEL = "novel"
    SCRIPT = "script"




class ProjectStatus(str, Enum):
    """项目状态"""
    INIT = "init"
    DIRECTORY = "directory"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"




class ChapterStatus(str, Enum):
    """章节状态"""
    PENDING = "pending"
    DRAFTING = "drafting"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== 小说专属配置 ====================
