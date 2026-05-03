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



class EpisodeOutlineScene(BaseModel):
    """分集大纲中的场景信息"""
    scene_number: int = Field(..., description="场景序号")
    location: str = Field(default="", description="场景地点")
    interior_exterior: str = Field(default="内", description="内景/外景")
    time_of_day: str = Field(default="日", description="日/夜/晨/昏")
    core_content: str = Field(default="", description="核心内容/冲突")
    main_characters: str = Field(default="", description="主要人物")
    estimated_duration: int = Field(default=3, description="预计时长(分钟)")




class EpisodeOutlineBase(BaseModel):
    """分集详细大纲基础模型"""
    episode_number: int = Field(..., description="集数")
    episode_title: Optional[str] = Field(None, description="集标题")
    episode_summary: Optional[str] = Field(None, description="本集梗概(200-300字)")
    detailed_outline: str = Field(..., description="详细大纲(500-1200字)")
    estimated_duration: Optional[int] = Field(None, description="预计时长(分钟)")
    scenes: Optional[List[EpisodeOutlineScene]
                     ] = Field(None, description="场景列表")
    core_conflict: Optional[str] = Field(None, description="核心冲突")
    emotional_curve: Optional[str] = Field(None, description="情感曲线")
    key_dialogues: Optional[List[str]] = Field(None, description="关键对话")
    visual_highlights: Optional[str] = Field(None, description="视觉亮点")




class EpisodeOutlineCreate(EpisodeOutlineBase):
    """创建分集详细大纲"""
    pass




class EpisodeOutlineUpdate(BaseModel):
    """更新分集详细大纲"""
    episode_title: Optional[str] = Field(None, description="集标题")
    episode_summary: Optional[str] = Field(None, description="本集梗概")
    detailed_outline: Optional[str] = Field(None, description="详细大纲")
    estimated_duration: Optional[int] = Field(None, description="预计时长(分钟)")
    scenes: Optional[List[EpisodeOutlineScene]
                     ] = Field(None, description="场景列表")
    core_conflict: Optional[str] = Field(None, description="核心冲突")
    emotional_curve: Optional[str] = Field(None, description="情感曲线")
    key_dialogues: Optional[List[str]] = Field(None, description="关键对话")
    visual_highlights: Optional[str] = Field(None, description="视觉亮点")




class EpisodeOutlineResponse(EpisodeOutlineBase):
    """分集详细大纲响应"""
    status: str = Field(default="pending",
                        description="状态: pending/generated/edited")
    content_status: Optional[str] = Field(None,
                                          description="正文生成状态: None/generated")
    content_word_count: Optional[int] = Field(None,
                                              description="已生成正文字数")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")

    model_config = {
        "from_attributes": True
    }




class EpisodeOutlineListResponse(BaseModel):
    """分集详细大纲列表响应"""
    project_id: int
    total_episodes: int = Field(default=0, description="总集数")
    generated_count: int = Field(default=0, description="已生成集数")
    episodes: List[EpisodeOutlineResponse] = Field(
        default_factory=list, description="分集大纲列表")




class EpisodeOutlineGenerateRequest(BaseModel):
    """分集详细大纲生成请求"""
    episode_numbers: Optional[List[int]] = Field(
        None, description="指定要生成的集数列表，None表示生成全部")
    stop_on_error: bool = Field(default=True, description="出错时是否停止")


# ==================== 章节详细大纲（小说专用） ====================



class ChapterOutlineBase(BaseModel):
    """章节详细大纲基础模型"""
    chapter_number: int = Field(..., description="章节号")
    chapter_title: Optional[str] = Field(None, description="章节标题")
    chapter_summary: Optional[str] = Field(None, description="本章梗概(200-300字)")
    detailed_outline: str = Field(..., description="详细大纲(500-1000字)")
    key_events: Optional[List[str]] = Field(None, description="关键事件")
    character_arcs: Optional[str] = Field(None, description="角色发展弧线")
    suspense_points: Optional[List[str]] = Field(None, description="悬念设置")
    emotional_tone: Optional[str] = Field(None, description="情感基调")




class ChapterOutlineCreate(ChapterOutlineBase):
    """创建章节详细大纲"""
    pass




class ChapterOutlineUpdate(BaseModel):
    """更新章节详细大纲"""
    chapter_title: Optional[str] = Field(None, description="章节标题")
    chapter_summary: Optional[str] = Field(None, description="本章梗概")
    detailed_outline: Optional[str] = Field(None, description="详细大纲")
    key_events: Optional[List[str]] = Field(None, description="关键事件")
    character_arcs: Optional[str] = Field(None, description="角色发展弧线")
    suspense_points: Optional[List[str]] = Field(None, description="悬念设置")
    emotional_tone: Optional[str] = Field(None, description="情感基调")




class ChapterOutlineResponse(ChapterOutlineBase):
    """章节详细大纲响应"""
    status: str = Field(default="pending",
                        description="状态: pending/generated/edited")
    content_status: Optional[str] = Field(
        None, description="正文生成状态: None/generated")
    content_word_count: Optional[int] = Field(None, description="已生成正文字数")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    # 修正信息
    original_content: Optional[str] = Field(None, description="原始大纲内容（修正前）")
    revision_info: Optional[Dict[str, Any]] = Field(None, description="修正信息")

    model_config = {
        "from_attributes": True
    }




class ChapterOutlineListResponse(BaseModel):
    """章节详细大纲列表响应"""
    project_id: int
    total_chapters: int = Field(default=0, description="总章节数")
    generated_count: int = Field(default=0, description="已生成章节数")
    chapters: List[ChapterOutlineResponse] = Field(
        default_factory=list, description="章节大纲列表")




class ChapterOutlineGenerateRequest(BaseModel):
    """章节详细大纲生成请求"""
    chapter_numbers: Optional[List[int]] = Field(
        None, description="指定要生成的章节列表，None表示生成全部")
    start_unit: Optional[int] = Field(
        None, description="起始单元编号，与unit_count配合使用")
    unit_count: Optional[int] = Field(
        None, description="生成数量，与start_unit配合使用")
    stop_on_error: bool = Field(default=True, description="出错时是否停止")
    skip_existing: bool = Field(
        default=True, description="是否跳过已生成的章节（断点续传）")


# ==================== 场景详细大纲（电影剧本专用） ====================



class SceneOutlineBase(BaseModel):
    """场景详细大纲基础模型"""
    scene_number: int = Field(..., description="场景号")
    scene_title: Optional[str] = Field(None, description="场景标题")
    location: Optional[str] = Field(None, description="场景地点（如：内景 办公室-日）")
    scene_summary: Optional[str] = Field(None, description="本场梗概(100-200字)")
    detailed_outline: str = Field(..., description="详细大纲(300-500字)")
    characters: Optional[List[str]] = Field(None, description="出场人物")
    estimated_duration: Optional[int] = Field(None, description="预计时长(分钟)")
    key_action: Optional[str] = Field(None, description="关键动作/事件")
    dialogue_focus: Optional[str] = Field(None, description="对话重点")




class SceneOutlineCreate(SceneOutlineBase):
    """创建场景详细大纲"""
    pass




class SceneOutlineUpdate(BaseModel):
    """更新场景详细大纲"""
    scene_title: Optional[str] = Field(None, description="场景标题")
    location: Optional[str] = Field(None, description="场景地点")
    scene_summary: Optional[str] = Field(None, description="本场梗概")
    detailed_outline: Optional[str] = Field(None, description="详细大纲")
    characters: Optional[List[str]] = Field(None, description="出场人物")
    estimated_duration: Optional[int] = Field(None, description="预计时长(分钟)")
    key_action: Optional[str] = Field(None, description="关键动作/事件")
    dialogue_focus: Optional[str] = Field(None, description="对话重点")




class SceneOutlineResponse(SceneOutlineBase):
    """场景详细大纲响应"""
    status: str = Field(default="pending",
                        description="状态: pending/generated/edited")
    content_status: Optional[str] = Field(
        None, description="正文生成状态: None/generated")
    content_word_count: Optional[int] = Field(None, description="已生成正文字数")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")

    model_config = {
        "from_attributes": True
    }




class SceneOutlineListResponse(BaseModel):
    """场景详细大纲列表响应"""
    project_id: int
    total_scenes: int = Field(default=0, description="总场景数")
    generated_count: int = Field(default=0, description="已生成场景数")
    scenes: List[SceneOutlineResponse] = Field(
        default_factory=list, description="场景大纲列表")




class SceneOutlineGenerateRequest(BaseModel):
    """场景详细大纲生成请求"""
    scene_numbers: Optional[List[int]] = Field(
        None, description="指定要生成的场景列表，None表示生成全部")
    stop_on_error: bool = Field(default=True, description="出错时是否停止")


# ==================== 风格文档相关 Schema ====================
