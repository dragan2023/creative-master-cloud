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

class NovelConfig(BaseModel):
    """小说正文生成专属配置

    生成单位：章节（按大纲中的章节划分）
    """
    # 投放平台
    target_platform: Optional[str] = Field(
        None,
        description="投放平台（起点中文网、豆瓣阅读、晋江、番茄小说等）"
    )

    # 总字数规划
    total_words: Optional[int] = Field(
        None,
        description="总字数规划"
    )

    # 每章节字数
    words_per_chapter: int = Field(
        default=3000,
        description="每章节字数（默认3000字）"
    )

    # 风格模仿参数
    style_reference: Optional[str] = Field(
        None,
        description="风格模仿文本（可粘贴喜欢的作品片段，AI将模仿其风格）"
    )

    # 温度系数
    temperature: float = Field(
        default=0.8,
        ge=0,
        le=1,
        description="温度系数（0-1，越高越有创意）"
    )

    # 叙事视角
    narrative_perspective: str = Field(
        default="第三人称",
        description="叙事视角（第一人称/第三人称）"
    )

    # 基调风格
    tone: str = Field(
        default="正剧",
        description="基调风格（正剧/轻松/幽默/严肃等）"
    )

    model_config = {
        "from_attributes": True
    }


# ==================== 剧集剧本专属配置 ====================

class SeriesScriptConfig(BaseModel):
    """剧集剧本正文生成专属配置

    生成单位：分集（按大纲中的集数划分）
    """
    # 剧集类型
    series_type: str = Field(
        default="电视剧",
        description="剧集类型（电视剧/网络剧/短剧/微短剧/网剧/竖屏剧）"
    )

    # 每集时长范围
    episode_duration_range: List[int] = Field(
        default=[30, 45],
        description="每集时长区间(分钟)"
    )

    # 场景数范围（可选）
    scenes_per_episode_range: Optional[List[int]] = Field(
        default=None,
        description="每集场景数范围(可选)，AI自动设计"
    )

    # 剧本格式标准
    format_standard: str = Field(
        default="标准格式",
        description="剧本格式标准（标准格式/简格式/网络平台格式/短剧格式）"
    )

    # 对白与叙述比例
    dialogue_narration_ratio: str = Field(
        default="均衡",
        description="对白与叙述比例（对话为主/均衡/叙述为主/动作导向）"
    )

    # 目标投放平台
    target_broadcast: Optional[str] = Field(
        None,
        description="投放平台（央视/卫视/爱奇艺/腾讯视频/抖音/快手/红果/河马等）"
    )

    # 总集数
    episode_count: Optional[int] = Field(
        None,
        description="总集数"
    )

    # 风格模仿参数
    style_reference: Optional[str] = Field(
        None,
        description="风格模仿文本（可粘贴喜欢的剧本片段，AI将模仿其风格）"
    )

    # 对话风格
    dialogue_style: str = Field(
        default="自然对话",
        description="对话风格（自然对话/文艺腔/口语化/台词化）"
    )

    # 叙事节奏
    narrative_rhythm: str = Field(
        default="紧凑",
        description="叙事节奏（紧凑/舒缓/起伏）"
    )

    # 剧本模式
    script_mode: str = Field(
        default="real",
        description="剧本模式（real=现实模式用于真人拍摄，virtual=虚拟模式用于AI视频生成）"
    )

    model_config = {
        "from_attributes": True
    }


# ==================== 电影剧本专属配置 ====================

class MovieScriptConfig(BaseModel):
    """电影剧本正文生成专属配置

    生成单位：场景（按大纲中的场景或段落划分）
    """
    # 电影类型
    movie_type: str = Field(
        default="院线电影",
        description="电影类型（院线电影/网络电影/微电影/纪录片/动画电影）"
    )

    # 电影总时长
    total_duration: int = Field(
        default=90,
        description="电影总时长(分钟)"
    )

    # 剧本格式标准
    format_standard: str = Field(
        default="标准格式",
        description="剧本格式标准（标准格式/影院格式/电视电影格式）"
    )

    # 对白与叙述比例
    dialogue_narration_ratio: str = Field(
        default="均衡",
        description="对白与叙述比例（对话为主/均衡/叙述为主/动作导向）"
    )

    # 目标投放平台
    target_platform: Optional[str] = Field(
        None,
        description="投放平台（院线发行/网络平台/电影节等）"
    )

    # 风格模仿参数
    style_reference: Optional[str] = Field(
        None,
        description="风格模仿文本（可粘贴喜欢的剧本片段，AI将模仿其风格）"
    )

    # 对话风格
    dialogue_style: str = Field(
        default="自然对话",
        description="对话风格（自然对话/文艺腔/口语化/台词化）"
    )

    # 叙事节奏
    narrative_rhythm: str = Field(
        default="紧凑",
        description="叙事节奏（紧凑/舒缓/起伏）"
    )

    # 剧本模式
    script_mode: str = Field(
        default="real",
        description="剧本模式（real=现实模式用于真人拍摄，virtual=虚拟模式用于AI视频生成）"
    )

    model_config = {
        "from_attributes": True
    }


# ==================== 旧版剧本配置（兼容用） ====================

class ScriptConfig(BaseModel):
    """剧本专用配置（兼容旧版，新代码请使用SeriesScriptConfig或MovieScriptConfig）"""
    # 剧集类型
    series_type: str = Field(default="电视剧", description="剧集类型")

    # 时长控制（核心参数）
    episode_duration_range: List[int] = Field(
        default=[30, 45],
        description="每集时长区间(分钟)"
    )

    # 场景控制（可选）
    scenes_per_episode_range: Optional[List[int]] = Field(
        default=None,
        description="每集场景数范围(可选)，AI自动设计"
    )

    # 格式标准
    format_standard: str = Field(
        default="标准格式",
        description="剧本格式标准(标准格式/简格式/网络平台格式/短剧格式)"
    )

    # 对白与叙述比例
    dialogue_narration_ratio: str = Field(
        default="均衡",
        description="对白与叙述比例(对话为主/均衡/叙述为主/动作导向)"
    )

    # 目标投放平台
    target_broadcast: Optional[str] = Field(
        None,
        description="目标投放平台"
    )

    # 集数
    episode_count: Optional[int] = Field(None, description="总集数")

    model_config = {
        "from_attributes": True
    }


# ==================== 项目相关 ====================

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
    outline_content: Optional[str] = None  # 大纲内容
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
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
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
    status: ChapterStatus
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
    status: ChapterStatus
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
    status: ChapterStatus
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
    status: ProjectStatus
    total_chapters: int
    completed_chapters: int
    current_chapter: int
    progress_percentage: float
    current_chapter_status: Optional[ChapterStatus] = None
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
    stop_on_error: bool = Field(default=True, description="出错时是否停止")


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
