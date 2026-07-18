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

# 导入前向引用所需的类型
from ._enums import ProjectType, ProjectStatus
from ._config import NovelConfig, SeriesScriptConfig, MovieScriptConfig


# ==================== 枚举类型 ====================

class ContentType(str, Enum):
    """内容类型"""
    NOVEL = "novel"
    SERIES_SCRIPT = "series_script"
    MOVIE_SCRIPT = "movie_script"


class NovelProjectCreate(BaseModel):
    """创建项目请求

    【重要】本模块专注于正文创作，请先上传大纲或从创意生成板块获取大纲
    """
    title: str = Field(..., min_length=1, max_length=200, description="项目标题")

    # 内容类型（三种独立类型）
    content_type: ContentType = Field(
        ...,
        description="内容类型（novel=小说, series_script=剧集剧本, movie_script=电影剧本）"
    )

    # 题材标签
    genre: Optional[str] = Field(
        None, max_length=50, description="题材标签（如言情、悬疑、科幻）")

    # 根据内容类型选择对应配置（三选一）
    novel_config: Optional[NovelConfig] = Field(
        None, description="小说配置（content_type=novel时使用）")
    series_script_config: Optional[SeriesScriptConfig] = Field(
        None, description="剧集剧本配置（content_type=series_script时使用）")
    movie_script_config: Optional[MovieScriptConfig] = Field(
        None, description="电影剧本配置（content_type=movie_script时使用）")

    # 知识库配置
    knowledge_base_config: Optional[Dict[str, Any]] = Field(
        None, description="知识库配置"
    )

    # 知识图谱继承（已废弃：当前四阶段流程不再构建知识图谱，保留字段仅向后兼容）
    inherit_kb_from_project_id: Optional[int] = Field(
        None, ge=1, description="[已废弃] 继承知识图谱的源项目ID。四阶段流程不再构建知识图谱，此字段不再生效。"
    )

    # 兼容旧版字段（将被废弃）
    project_type: Optional[ProjectType] = Field(None, description="项目类型（兼容旧版）")
    target_platform: Optional[str] = Field(
        None, max_length=50, description="目标平台（兼容旧版）")
    generation_config: Optional[Dict[str, Any]] = Field(
        None, description="生成配置（兼容旧版）")
    script_config: Optional[Dict[str, Any]] = Field(
        None, description="剧本专用配置（兼容旧版）")




class ScriptProjectCreate(BaseModel):
    """创建剧本项目请求"""
    title: str = Field(..., min_length=1, max_length=200, description="项目标题")
    series_type: str = Field(
        default="电视剧", description="剧集类型(电视剧/网络剧/短剧/电影/微电影)")
    episode_count: Optional[int] = Field(None, ge=1, le=100, description="总集数")

    # ========== 剧本专用配置参数 ==========
    # 每集时长区间（核心参数，控制内容体量）
    episode_duration_range: Optional[List[int]] = Field(
        default=[30, 45],
        max_length=2,
        description="每集时长区间(分钟)，如[30,45]表示30-45分钟"
    )

    # 场景数范围（可选，AI自动估算）
    scenes_per_episode_range: Optional[List[int]] = Field(
        default=None,
        max_length=2,
        description="每集场景数范围(可选)，如[10,20]表示10-20场，留空则AI根据时长自动设计"
    )

    # 剧本格式标准
    format_standard: str = Field(
        default="标准格式",
        description="剧本格式标准(标准格式/简格式/网络平台格式/短剧格式)"
    )

    # 对白与叙述比例
    dialogue_narration_ratio: str = Field(
        default="均衡",
        description="对白与叙述比例(对话为主/均衡/叙述为主/动作导向)"
    )

    # 目标投放平台（影响格式细节）
    target_broadcast: Optional[str] = Field(
        None,
        max_length=50,
        description="目标投放平台(央视/卫视/爱奇艺/腾讯视频/抖音/快手等)"
    )

    genre: Optional[str] = Field(None, max_length=50, description="类型标签")
    target_platform: Optional[str] = Field(
        None, max_length=50, description="目标平台")
    generation_config: Optional[Dict[str, Any]
                                ] = Field(None, description="生成配置")
    knowledge_base_config: Optional[Dict[str, Any]] = Field(
        None, description="知识库配置")




class NovelProjectUpdate(BaseModel):
    """更新项目请求"""
    title: Optional[str] = Field(
        None, min_length=1, max_length=200, description="项目标题")
    genre: Optional[str] = Field(None, max_length=50, description="题材标签")
    outline_content: Optional[str] = Field(None, description="大纲内容")
    unit_summaries: Optional[Dict[str, Any]] = Field(None, description="单元概述数据")

    # 新版配置字段
    novel_config: Optional[NovelConfig] = Field(None, description="小说配置")
    series_script_config: Optional[SeriesScriptConfig] = Field(
        None, description="剧集剧本配置")
    movie_script_config: Optional[MovieScriptConfig] = Field(
        None, description="电影剧本配置")
    knowledge_base_config: Optional[Dict[str, Any]] = Field(
        None, description="知识库配置")

    # 兼容旧版字段
    target_platform: Optional[str] = Field(
        None, max_length=50, description="目标平台（兼容旧版）")
    generation_config: Optional[Dict[str, Any]
                                ] = Field(None, description="生成配置（兼容旧版）")
    script_config: Optional[Dict[str, Any]] = Field(
        None, description="剧本专用配置（兼容旧版）")




class NovelProjectResponse(BaseModel):
    """项目响应"""
    id: int
    title: str
    project_type: ProjectType  # 兼容数据库模型
    content_type: Optional[ContentType] = None  # 新版内容类型
    genre: Optional[str] = None
    target_platform: Optional[str] = None
    status: ProjectStatus
    total_chapters: int = 0
    completed_chapters: int = 0
    current_chapter: int = 0
    progress_percentage: float = 0.0

    # 新版配置字段
    novel_config: Optional[NovelConfig] = None
    series_script_config: Optional[SeriesScriptConfig] = None
    movie_script_config: Optional[MovieScriptConfig] = None

    # 兼容旧版字段
    generation_config: Optional[Dict[str, Any]] = None
    knowledge_base_config: Optional[Dict[str, Any]] = None
    script_config: Optional[Dict[str, Any]] = None  # 剧本专用配置

    project_code: Optional[str] = None
    total_tokens: int = 0
    total_duration_ms: int = 0
    outline_content: Optional[str] = None  # 大纲内容（截断预览用）
    outline_word_count: int = 0  # 大纲真实字数（去除空白字符）

    # 单元概述相关字段
    unit_summaries: Optional[Dict[str, Any]] = None  # 单元概述数据
    unit_summaries_status: Optional[str] = None  # 单元概述状态

    # AI文风消除配置
    ai_elimination_enabled: Optional[bool] = True  # 是否启用AI文风消除
    ai_elimination_threshold: Optional[int] = 50  # AI文风消除阈值(0-100)

    created_at: datetime
    updated_at: datetime

    # 获取内容类型标签
    @property
    def content_type_label(self) -> str:
        """获取内容类型的中文标签"""
        labels = {
            ContentType.NOVEL: "小说",
            ContentType.SERIES_SCRIPT: "剧集剧本",
            ContentType.MOVIE_SCRIPT: "电影剧本"
        }
        return labels.get(self.content_type, "未知类型")

    # 获取生成单位标签
    @property
    def unit_label(self) -> str:
        """获取生成单位标签（章节/集/场）"""
        unit_labels = {
            ContentType.NOVEL: "章",
            ContentType.SERIES_SCRIPT: "集",
            ContentType.MOVIE_SCRIPT: "场"
        }
        return unit_labels.get(self.content_type, "章")

    # 剧本专用配置的快捷访问属性（兼容旧版，方便前端使用）
    @property
    def script_format_standard(self) -> str:
        """获取剧本格式标准"""
        if self.content_type == ContentType.NOVEL:
            return ""
        if self.series_script_config:
            return self.series_script_config.format_standard
        if self.movie_script_config:
            return self.movie_script_config.format_standard
        return self.script_config.get("format_standard", "标准格式") if self.script_config else "标准格式"

    @property
    def script_dialogue_ratio(self) -> str:
        """获取对白叙述比例"""
        if self.content_type == ContentType.NOVEL:
            return ""
        if self.series_script_config:
            return self.series_script_config.dialogue_narration_ratio
        if self.movie_script_config:
            return self.movie_script_config.dialogue_narration_ratio
        return self.script_config.get("dialogue_narration_ratio", "均衡") if self.script_config else "均衡"

    @property
    def script_duration_range(self) -> List[int]:
        """获取每集时长区间"""
        if self.content_type == ContentType.NOVEL:
            return []
        if self.series_script_config:
            return self.series_script_config.episode_duration_range
        return self.script_config.get("episode_duration_range", [30, 45]) if self.script_config else [30, 45]

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # 枚举类型序列化为字符串值
        # Pydantic V2 默认将 datetime 序列化为 ISO 8601，无需已弃用的 json_encoders
    }




class NovelProjectListResponse(BaseModel):
    """项目列表响应"""
    items: List[NovelProjectResponse]
    total: int


# ==================== 大纲上传 ====================



class OutlineUploadResponse(BaseModel):
    """大纲上传响应"""
    project_id: int
    outline_content: str
    extracted_chapters: int
    message: str = "大纲上传成功"


# ==================== 章节目录 ====================
