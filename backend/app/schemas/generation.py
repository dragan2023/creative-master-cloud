"""
创意生成相关 Schema
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class GenerationModule(str, Enum):
    """生成模块"""
    SHORT_VIDEO = "short_video"
    SCRIPT = "script"
    NOVEL = "novel"
    PRINT_AD = "print_ad"
    TVC = "tvc"


class GenerationStatus(str, Enum):
    """生成状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== 短视频脚本 ====================

class ShortVideoInput(BaseModel):
    """短视频脚本输入"""
    topic: str = Field(..., description="主题")
    audience: str = Field(..., description="目标受众")
    description: Optional[str] = Field(None, description="详细描述")
    platform: str = Field(default="抖音", description="发布平台")
    style: str = Field(default="轻松有趣", description="风格调性")
    duration: int = Field(default=60, description="视频时长(秒)")
    generate_ai_prompt: Optional[str] = Field(None, description="是否生成AI视频提示")
    ai_platforms: Optional[str] = Field(None, description="AI视频平台")
    reference_video: Optional[str] = Field(
        None, description="参考视频URL（仅Gemini 1.5 Pro/Flash支持）")
    # 运营相关自定义变量
    account_tone: Optional[str] = Field(
        None, description="账号调性（如：专业干货型、搞笑娱乐型、情感治愈型等）")
    target_fans: Optional[str] = Field(
        None, description="目标粉丝群体（如：18-25岁女性、职场白领、宝妈群体等）")
    content_position: Optional[str] = Field(
        None, description="内容定位（如：知识科普、生活记录、好物推荐等）")
    custom_variables: Optional[Dict[str, Any]] = Field(
        None, description="其他自定义变量")


# ==================== 剧本大纲 ====================

class ScriptInput(BaseModel):
    """剧本大纲输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    series_type: str = Field(...,
                             description="剧集类型(院线电影/网络电影/长剧/短剧/微电影/纪录片/动画电影/网络剧/竖屏剧)")
    theme: str = Field(...,
                       description="题材(爱情/喜剧/悬疑/科幻/奇幻/动作/剧情/历史/都市/青春/恐怖/犯罪/惊悚/灾难)")
    audience: str = Field(..., description="目标受众")
    platform: str = Field(
        default="爱奇艺", description="投放平台(央视/地方卫视/爱奇艺/腾讯视频/优酷/芒果TV/B站/抖音/快手/西瓜视频/红果短剧/河马剧场/Netflix/HBO/Disney+/院线发行/电影节展映)")
    reference_works: Optional[str] = Field(None, description="对标作品(可填写作品名称)")
    synopsis: str = Field(..., description="故事梗概")
    episode_count: Optional[str] = Field(None, description="集数")
    custom_outline: Optional[str] = Field(
        None, description="自写大纲URL（用户上传的文本文件）")


# ==================== 小说大纲 ====================

class NovelInput(BaseModel):
    """小说大纲输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    length: str = Field(default="中篇", description="篇幅(短篇/中篇/长篇)")
    genre: str = Field(...,
                       description="类型标签(言情/悬疑推理/科幻/奇幻玄幻/历史/现实题材/轻小说/恐怖惊悚)")
    target_platform: str = Field(
        default="起点", description="目标读者/平台(起点/晋江/番茄/实体出版/纯个人创作)")
    tone: str = Field(default="正剧", description="基调氛围(正剧/喜剧/虐恋催泪/爽文/治愈温暖)")
    theme: Optional[str] = Field(None, description="故事主题——想表达的核心思想")
    unique_selling_point: Optional[str] = Field(
        None, description="独特卖点——最吸引人的钩子")
    synopsis: str = Field(..., description="故事梗概")
    chapter_count: Optional[str] = Field(None, description="章节数")
    custom_outline: Optional[str] = Field(
        None, description="自写大纲URL（用户上传的文本文件）")


# ==================== 平面广告 ====================

class PrintAdInput(BaseModel):
    """平面广告输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    brand_product: str = Field(..., description="品牌/产品名称（具体品牌+产品，新品牌需说明调性）")
    ad_purpose: str = Field(..., description="广告目的")
    core_message: str = Field(..., description="核心信息（如果受众看完只记住一件事，必须用一句话说清楚）")
    audience_profile: str = Field(..., description="受众特征（年龄+性别+学历+职业+收入+地域）")
    contact_scene: str = Field(..., description="接触场景（他们通常在哪里看到这则广告？）")
    style_tone: str = Field(default="视觉冲击", description="风格调性")
    copy_content: Optional[str] = Field(None, description="文案内容")
    size_spec: Optional[str] = Field(None, description="具体尺寸")
    publish_media: Optional[str] = Field(None, description="发布媒介")
    ai_platforms: Optional[str] = Field(default="豆包", description="AI提示词目标平台")
    # 多模态支持
    images: Optional[List[str]] = Field(
        None, description="参考图片URL列表（支持上传或网络图片链接，最大50MB）")


# ==================== TVC广告脚本 ====================

class TVCInput(BaseModel):
    """TVC广告脚本输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    brand_product: str = Field(..., description="品牌/产品名称（具体品牌+产品线）")
    ad_purpose: str = Field(..., description="广告目的")
    core_message: str = Field(..., description="核心信息（如果观众看完只记住一句话）")
    audience_profile: str = Field(..., description="受众特征（年龄+性别+学历+职业+收入+地域）")
    broadcast_platform: str = Field(default="视频平台", description="投放平台")
    style_tone: str = Field(default="温情走心", description="风格调性")
    duration: int = Field(default=30, description="时长(秒)")
    generate_ai_prompt: Optional[str] = Field(
        default="否", description="是否生成AI视频生成提示")
    ai_platforms: Optional[str] = Field(
        default="可灵", description="AI视频生成平台(可灵/Seedance 2.0/Sora 2/Veo 3.1/Runway/Pika/Wan 2.2)")
    # 参考视频（多模态）
    reference_video: Optional[str] = Field(
        None, description="参考视频URL（仅Gemini 1.5 Pro/Flash支持）")


# ==================== 通用请求/响应 ====================

class GenerateRequest(BaseModel):
    """通用生成请求"""
    input_params: Dict[str, Any] = Field(..., description="输入参数")
    session_id: Optional[str] = Field(None, description="会话ID(用于多轮对话)")
    enable_search: bool = Field(default=False, description="是否启用联网搜索")
    knowledge_base_id: Optional[str] = Field(None, description="知识库ID")
    provider: Optional[str] = Field(None, description="指定LLM提供者")
    temperature: float = Field(default=0.7, ge=0, le=1, description="温度参数")


class GenerateResponse(BaseModel):
    """生成响应"""
    success: bool
    content: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    duration_ms: Optional[int] = None
    generation_id: Optional[int] = None
    error: Optional[str] = None


class GenerationHistoryResponse(BaseModel):
    """生成历史响应"""
    id: int
    module: GenerationModule
    status: GenerationStatus
    title: Optional[str] = None
    input_params: Optional[Dict[str, Any]] = None
    output_content: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    token_count: int
    duration_ms: int
    created_at: str

    class Config:
        from_attributes = True


class SessionCreateResponse(BaseModel):
    """创建会话响应"""
    session_id: str
    message: str = "会话创建成功"


# ==================== 用户行为追踪 ====================

class ActionType(str, Enum):
    """行为类型"""
    COPY = "copy"
    DOWNLOAD = "download"
    REGENERATE = "regenerate"
    LIKE = "like"
    SHARE = "share"


class UserActionCreate(BaseModel):
    """创建用户行为"""
    generation_id: Optional[int] = Field(None, description="生成记录ID")
    module: str = Field(..., description="模块名称")
    action: ActionType = Field(..., description="行为类型")
    content_snippet: Optional[str] = Field(None, description="内容片段")


class UserActionResponse(BaseModel):
    """用户行为响应"""
    id: int
    user_id: int
    generation_id: Optional[int] = None
    module: str
    action: ActionType
    content_snippet: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ActionStatsResponse(BaseModel):
    """行为统计响应"""
    total_actions: int
    copy_count: int
    download_count: int
    regenerate_count: int
    copy_rate: float  # 复制率 = 复制数/总生成数
    download_rate: float  # 下载率 = 下载数/总生成数
