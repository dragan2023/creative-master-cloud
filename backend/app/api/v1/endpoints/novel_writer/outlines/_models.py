"""大纲管理 - 公共模型定义"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class UnitSummariesQualityControlRequest(BaseModel):
    """单元概述质控请求"""
    enable_auto_revision: bool = Field(
        default=True,
        description="是否启用自动修正严重问题"
    )


class UnitSummariesQualityControlResponse(BaseModel):
    """单元概述质控响应"""
    success: bool
    quality_report: Dict[str, Any]
    revision_summary: List[Dict[str, Any]]
    revised_count: int
    message: str


class UnitSummariesUploadRequest(BaseModel):
    """单元概述上传请求"""
    unit_summaries: Dict[str, Any]  # 单元概述字典
    global_outline: Optional[str] = None  # 可选的全局大纲


class UnitSummariesUploadResponse(BaseModel):
    """单元概述上传响应"""
    project_id: int
    unit_count: int
    message: str


class OutlineInterventionRequest(BaseModel):
    """详细大纲生成干预请求"""
    content_type: str = Field(
        default="novel", description="内容类型: novel/series_script/movie_script")
    user_choice: Optional[str] = Field(
        default=None, description="用户选择: accept/provide/reference/skip")
    user_guidance: Optional[str] = Field(default=None, description="用户提供的概要内容")
    force_regenerate: bool = Field(
        default=False, description="是否强制重新生成（即使已存在详细大纲）")
