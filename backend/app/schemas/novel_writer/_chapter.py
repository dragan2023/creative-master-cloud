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



class DirectoryGenerateRequest(BaseModel):
    """章节目录生成请求"""
    total_chapters: int = Field(..., ge=1, le=500, description="总章节数")
    chapter_naming_style: str = Field(default="数字编号", description="章节命名风格")
    custom_instructions: Optional[str] = Field(None, description="自定义指令")
    generate_names: bool = Field(default=True, description="是否调用LLM预生成章节名称")




class ChapterMetadata(BaseModel):
    """章节元数据"""
    chapter_number: int
    chapter_title: str
    chapter_role: Optional[str] = None
    chapter_purpose: Optional[str] = None
    suspense_level: Optional[str] = None
    foreshadowing: Optional[str] = None
    plot_twist_level: Optional[str] = None
    chapter_summary: Optional[str] = None
    # 剧本专用
    episode_number: Optional[int] = None  # 集数
    scene_number: Optional[int] = None    # 场次
    scene_metadata: Optional[Dict[str, Any]] = None


# ==================== 剧本场景相关 ====================



class SceneMetadata(BaseModel):
    """场景元数据"""
    location: str = Field(..., description="地点")
    interior_exterior: str = Field(default="内", description="内景/外景")
    time_of_day: str = Field(default="日", description="日/夜/晨/昏")
    weather: Optional[str] = Field(None, description="天气")
    characters_present: List[str] = Field(
        default_factory=list, description="在场角色")
    duration_minutes: int = Field(default=3, description="预计时长(分钟)")
    transition: Optional[str] = Field(None, description="转场方式")




class SceneGenerateRequest(BaseModel):
    """场景生成请求"""
    episode_number: int = Field(..., ge=1, description="集数")
    scene_number: int = Field(..., ge=1, description="场次")
    scene_metadata: SceneMetadata = Field(..., description="场景元数据")
    scene_purpose: Optional[str] = Field(None, description="本场任务")




class SceneGenerateResponse(BaseModel):
    """场景生成响应"""
    project_id: int
    episode_number: int
    scene_number: int
    scene_title: Optional[str] = None
    status: "ChapterStatus"
    content: Optional[str] = None
    word_count: int = 0
    duration_ms: int = 0
    error_message: Optional[str] = None




class ScriptDirectoryRequest(BaseModel):
    """剧本目录生成请求"""
    total_episodes: int = Field(..., ge=1, le=100, description="总集数")
    # 场景数改为可选范围，AI自动估算
    scenes_per_episode_range: Optional[List[int]] = Field(
        default=None,
        max_length=2,
        description="每集场景数范围(可选)，如[10,20]，留空则AI根据时长自动设计"
    )
    include_scene_breakdown: bool = Field(default=True, description="是否生成场景细分")

    # 新增：时长控制
    episode_duration_range: Optional[List[int]] = Field(
        default=[30, 45],
        max_length=2,
        description="每集时长区间(分钟)"
    )

    # 新增：格式标准
    format_standard: str = Field(
        default="标准格式",
        description="剧本格式标准"
    )

    # 新增：对白比例
    dialogue_narration_ratio: str = Field(
        default="均衡",
        description="对白与叙述比例"
    )




class EpisodeDirectory(BaseModel):
    """分集目录"""
    episode_number: int
    episode_title: str
    episode_summary: str
    scenes: List[SceneMetadata]




class ScriptDirectoryResponse(BaseModel):
    """剧本目录响应"""
    project_id: int
    total_episodes: int
    episodes: List[EpisodeDirectory]


# ==================== 角色管理 ====================



class CharacterInfo(BaseModel):
    """角色信息"""
    character_name: str
    character_type: str = Field(default="配角", description="主角/配角/客串")
    first_appearance: Optional[int] = Field(None, description="首次出场场次")
    character_description: Optional[str] = Field(None, description="角色描述")
    dialogue_count: int = Field(default=0, description="台词数量")




class CharacterListResponse(BaseModel):
    """角色列表响应"""
    project_id: int
    characters: List[CharacterInfo]
    total_dialogues: int = 0




class DirectoryUpdateRequest(BaseModel):
    """章节目录更新请求"""
    chapters: List[ChapterMetadata] = Field(..., description="章节列表")




class DirectoryResponse(BaseModel):
    """章节目录响应"""
    project_id: int
    total_chapters: int
    chapters: List[ChapterMetadata]


# ==================== 章节生成 ====================



class ChapterGenerateRequest(BaseModel):
    """章节生成请求"""
    chapter_numbers: Optional[List[int]] = Field(
        None, description="指定章节号列表，None表示当前章节")
    auto_continue: bool = Field(default=True, description="是否自动继续下一章")




class ChapterGenerateResponse(BaseModel):
    """章节生成响应"""
    project_id: int
    chapter_number: int
    chapter_title: Optional[str] = None
    status: "ChapterStatus"
    content: Optional[str] = None
    word_count: int = 0
    token_count: int = 0
    duration_ms: int = 0
    error_message: Optional[str] = None




class ChapterContentResponse(BaseModel):
    """章节内容响应"""
    id: int
    project_id: int
    chapter_number: int
    chapter_title: Optional[str] = None
    chapter_metadata: Optional[Dict[str, Any]] = None
    status: "ChapterStatus"
    draft_content: Optional[str] = None  # 原始草稿（修正前）
    final_content: Optional[str] = None
    word_count: int = 0
    token_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # 枚举类型序列化为字符串值
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }




class ChapterContentUpdate(BaseModel):
    """章节内容更新请求"""
    content: str = Field(..., description="章节内容")




class ChapterListResponse(BaseModel):
    """章节列表响应"""
    project_id: int
    total_chapters: int
    completed_chapters: int
    chapters: List[Dict[str, Any]]


# ==================== 导出 ====================



class ExportRequest(BaseModel):
    """导出请求"""
    format: str = Field(default="txt", description="导出格式(txt/md/docx/epub)")
    include_metadata: bool = Field(default=False, description="是否包含元数据")
    chapter_range: Optional[str] = Field(None, description="章节范围(如: 1-10)")




class ExportResponse(BaseModel):
    """导出响应"""
    file_path: str
    file_name: str
    file_size: int
    format: str


# ==================== 进度 ====================



class GenerationProgress(BaseModel):
    """生成进度"""
    project_id: int
    status: "ProjectStatus"
    total_chapters: int
    completed_chapters: int
    current_chapter: int
    progress_percentage: float
    current_chapter_status: Optional["ChapterStatus"] = None
    estimated_remaining_time: Optional[int] = None  # 秒
    error_message: Optional[str] = None


# ==================== 批量生成 ====================



class BatchGenerateRequest(BaseModel):
    """批量生成请求"""
    start_chapter: int = Field(..., ge=1, description="起始章节")
    end_chapter: int = Field(..., ge=1, description="结束章节")
    stop_on_error: bool = Field(default=True, description="出错时是否停止")




class BatchGenerateResponse(BaseModel):
    """批量生成响应"""
    project_id: int
    start_chapter: int
    end_chapter: int
    completed_count: int
    failed_count: int
    total_tokens: int
    total_duration_ms: int
    errors: List[Dict[str, Any]] = []


# ==================== 分集详细大纲 ====================
