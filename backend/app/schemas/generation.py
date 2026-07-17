"""
创意生成相关 Schema
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class GenerationModule(str, Enum):
    """生成模块"""
    SHORT_VIDEO = "short_video"
    NOVEL = "novel"
    PRINT_AD = "print_ad"
    TVC = "tvc"
    ORIGINAL_IP = "original_ip"
    MOVIE_OUTLINE = "movie_outline"  # 电影大纲
    SERIES_OUTLINE = "series_outline"  # 剧集大纲
    PRACTICAL_WRITING = "practical_writing"  # 应用文写作


class GenerationStatus(str, Enum):
    """生成状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==================== 短视频脚本 ====================

class ShortVideoInput(BaseModel):
    """短视频脚本输入"""
    topic: str = Field(..., description="主题")
    audience: str = Field(..., description="目标受众")
    description: Optional[str] = Field(None, description="详细描述")
    platform: str = Field(default="抖音", description="发布平台")
    style: str = Field(default="轻松有趣", description="风格调性")
    duration: int = Field(default=60, description="视频时长(秒)")
    mode: Optional[str] = Field(
        default="virtual", description="生成模式（real=现实模式用于真人拍摄，virtual=虚拟模式用于AI生成）")
    generate_ai_prompt: Optional[str] = Field(None, description="是否生成AI视频提示")
    ai_platforms: Optional[str] = Field(None, description="AI视频平台")
    generate_storyboard_images: Optional[str] = Field(
        default="否", description="是否生成分镜图提示词（用于AI绘图生成参考图）")
    reference_video: Optional[str] = Field(
        None, description="参考视频URL（仅Gemini 1.5 Pro/Flash支持）")
    # 参考资料上传功能
    reference_materials: Optional[str] = Field(
        None, description="参考资料URL（用户上传的文本文件，包含创作参考素材）")
    # 运营相关自定义变量
    account_tone: Optional[str] = Field(
        None, description="账号调性（如：专业干货型、搞笑娱乐型、情感治愈型等）")
    target_fans: Optional[str] = Field(
        None, description="目标粉丝群体（如：18-25岁女性、职场白领、宝妈群体等）")
    content_position: Optional[str] = Field(
        None, description="内容定位（如：知识科普、生活记录、好物推荐等）")
    custom_variables: Optional[Dict[str, Any]] = Field(
        None, description="其他自定义变量")


# ==================== 电影大纲 ====================

class MovieOutlineInput(BaseModel):
    """电影大纲输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    movie_type: str = Field(
        ...,
        description="电影类型(院线电影/网络电影/微电影/纪录片/动画电影)")
    theme: str = Field(
        ...,
        description="题材(爱情/喜剧/悬疑/科幻/奇幻/动作/剧情/历史/都市/青春/恐怖/犯罪/惊悚/灾难)")
    audience: str = Field(..., description="目标受众")
    platform: str = Field(
        default="院线发行",
        description="投放平台(院线发行/电影节展映/爱奇艺/腾讯视频/优酷/芒果TV/B站/抖音/快手/Netflix/HBO/Disney+)")
    reference_works: Optional[str] = Field(None, description="对标作品(可填写作品名称)")
    synopsis: str = Field(..., description="故事梗概")
    scene_count: Optional[str] = Field(
        None, description="场景/场次数（如：80场，留空AI自动估算）")
    custom_outline: Optional[str] = Field(
        None, description="自写大纲URL（用户上传的文本文件）")
    # 电影专业配置参数
    duration_range: Optional[str] = Field(
        default="90-120分钟", description="整片时长区间（如：90-120分钟）")
    scene_count_range: Optional[str] = Field(
        default="AI自动设计", description="场景数范围（如：80-150场）")
    format_standard: Optional[str] = Field(
        default="标准格式", description="剧本格式标准")
    dialogue_narration_ratio: Optional[str] = Field(
        default="均衡", description="对白与叙述比例")
    target_broadcast: Optional[str] = Field(
        default="未指定", description="目标投放平台")
    # 剧本模式（现实模式/虚拟模式）
    script_mode: Optional[str] = Field(
        default="real",
        description="剧本模式(real=现实模式用于真人拍摄，virtual=虚拟模式用于AI视频生成)")
    # 风格参数
    style_ids: Optional[List[str]] = Field(
        default=None,
        description="电影风格ID列表，最多3个")
    style_names: Optional[List[str]] = Field(
        default=None,
        description="电影风格名称列表")
    style_intensity: Optional[float] = Field(
        default=0.7,
        description="风格强度(0.0-1.0)")
    style_guide: Optional[Dict[str, Any]] = Field(
        default=None,
        description="融合后的风格指南")
    # 多维电影风格参数（新增）
    script_style_dimensions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="电影风格维度选择数据(如：{导演风格: [{name:'张艺谋'}], ...})")
    script_style_names: Optional[List[str]] = Field(
        default=None,
        description="选中的电影风格名称扁平化列表")
    script_style_intensity: Optional[float] = Field(
        default=0.7,
        description="剧本风格强度(0.0-1.0)")
    script_style_type: Optional[str] = Field(
        default=None,
        description="风格类型：'movie'")
    # 标题风格
    title_style: Optional[str] = Field(
        default=None,
        description="标题风格ID")
    title_style_name: Optional[str] = Field(
        default=None,
        description="标题风格中文名称")


# ==================== 剧集大纲（从剧本大纲拆分）====================

class SeriesOutlineInput(BaseModel):
    """剧集大纲输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    series_type: str = Field(
        ...,
        description="剧集类型(电视剧/网络剧/短剧/微短剧/竖屏剧/长剧)")
    theme: str = Field(
        ...,
        description="题材(爱情/喜剧/悬疑/科幻/奇幻/动作/剧情/历史/都市/青春/恐怖/犯罪/惊悚/灾难)")
    audience: str = Field(..., description="目标受众")
    platform: str = Field(
        default="爱奇艺",
        description="投放平台(央视/地方卫视/爱奇艺/腾讯视频/优酷/芒果TV/B站/抖音/快手/西瓜视频/红果短剧/河马剧场/Netflix/HBO/Disney+)")
    reference_works: Optional[str] = Field(None, description="对标作品(可填写作品名称)")
    synopsis: str = Field(..., description="故事梗概")
    episode_count: Optional[str] = Field(
        None, description="总集数（如：24集，自定义填写）")
    custom_outline: Optional[str] = Field(
        None, description="自写大纲URL（用户上传的文本文件）")
    # 剧集专业配置参数
    episode_duration_range: Optional[str] = Field(
        default="30-45分钟", description="每集时长区间（如：5-15分钟）")
    scenes_per_episode_range: Optional[str] = Field(
        default="AI自动设计", description="每集场景数范围（如：10-20场）")
    format_standard: Optional[str] = Field(
        default="标准格式", description="剧本格式标准")
    dialogue_narration_ratio: Optional[str] = Field(
        default="均衡", description="对白与叙述比例")
    target_broadcast: Optional[str] = Field(
        default="未指定", description="目标投放平台")
    # 剧本模式（现实模式/虚拟模式）
    script_mode: Optional[str] = Field(
        default="real",
        description="剧本模式(real=现实模式用于真人拍摄，virtual=虚拟模式用于AI视频生成)")
    # 风格参数
    style_ids: Optional[List[str]] = Field(
        default=None,
        description="剧集风格ID列表，最多3个")
    style_names: Optional[List[str]] = Field(
        default=None,
        description="剧集风格名称列表")
    style_intensity: Optional[float] = Field(
        default=0.7,
        description="风格强度(0.0-1.0)")
    style_guide: Optional[Dict[str, Any]] = Field(
        default=None,
        description="融合后的风格指南")
    # 多维剧集风格参数（新增）
    script_style_dimensions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="剧集风格维度选择数据(如：{风格流派: [{name:'谍战剧[中]'}], ...})")
    script_style_names: Optional[List[str]] = Field(
        default=None,
        description="选中的剧集风格名称扁平化列表")
    script_style_intensity: Optional[float] = Field(
        default=0.7,
        description="剧本风格强度(0.0-1.0)")
    script_style_type: Optional[str] = Field(
        default=None,
        description="风格类型：'series'")
    script_series_sub_type: Optional[str] = Field(
        default=None,
        description="剧集子类型：'long'(长篇电视剧) / 'short'(网络短剧)")
    # 标题风格
    title_style: Optional[str] = Field(
        default=None,
        description="标题风格ID")
    title_style_name: Optional[str] = Field(
        default=None,
        description="标题风格中文名称")


# ==================== 小说大纲 ====================

class NovelInput(BaseModel):
    """小说大纲输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    length: str = Field(default="中篇", description="篇幅(短篇/中篇/长篇)")
    target_platform: str = Field(
        default="起点", description="目标读者/平台(起点/晋江/番茄/实体出版/纯个人创作)")
    synopsis: str = Field(..., description="故事梗概")
    chapter_count: Optional[str] = Field(None, description="章节数")
    custom_outline: Optional[str] = Field(
        None, description="自写大纲URL（用户上传的文本文件）")
    writing_styles: Optional[List[str]] = Field(
        default=None,
        description="写作风格ID列表，如['realism', 'hemingway_concise']，最多3个")
    style_intensity: Optional[float] = Field(
        default=0.7,
        description="风格强度(0.0-1.0)，控制文风特征的应用程度")
    # 标题风格（新增）
    title_style: Optional[str] = Field(
        default=None,
        description="标题风格ID，如'classical_chapter_narrative'、'network_suspense'等")
    title_style_name: Optional[str] = Field(
        default=None,
        description="标题风格中文名称")


# ==================== 平面广告 ====================

class PrintAdInput(BaseModel):
    """平面设计输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    design_category: Optional[str] = Field(
        default="商业广告", description="设计类别（logo设计/商业广告/宣传单页/公益广告/政府宣传/海报设计/展架设计/包装设计/其他设计）")
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
    description: Optional[str] = Field(None, description="详细描述（用户对广告创意的详细要求说明，是生成的核心依据）")
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
    description: Optional[str] = Field(None, description="补充说明")
    # 生成模式（现实模式/虚拟模式）
    mode: Optional[str] = Field(
        default="real",
        description="生成模式(real=现实模式用于真人拍摄，virtual=虚拟模式用于AI生成)")
    generate_ai_prompt: Optional[str] = Field(
        default="否", description="是否生成AI视频生成提示")
    ai_platforms: Optional[str] = Field(
        default="可灵", description="AI视频生成平台(可灵/Seedance 2.0/Sora 2/Veo 3.1/Runway/Pika/Wan 2.2)")
    # 参考视频（多模态）
    reference_video: Optional[str] = Field(
        None, description="参考视频URL（仅Gemini 1.5 Pro/Flash支持）")


# ==================== 应用文写作 ====================

class PracticalWritingInput(BaseModel):
    """应用文写作输入"""
    title: Optional[str] = Field(None, description="标题/主题")
    doc_type: str = Field(
        ...,
        description="文案类型（演讲稿/新闻稿/会议纪要/商业计划书/财务报表/标书/求职信简历/工作总结/述职报告/市场调研报告/可行性分析报告/合同协议/通知公告/邀请函/感谢信道歉信/产品说明书/培训方案/活动策划方案/规章制度/社交媒体文案/学术白皮书）")
    industry: str = Field(
        ...,
        description="所属行业（金融保险证券/信息技术互联网/教育培训/医疗健康制药/制造业工业/零售电商/房地产建筑/法律咨询/餐饮酒店/交通物流/能源环保/农业食品/文化传媒广告/政府公共事业/汽车出行/游戏娱乐）")
    description: Optional[str] = Field(None, description="详细描述（具体需求，是生成的核心依据）")
    doc_length: Optional[str] = Field(
        default="中篇（1000-3000字）",
        description="文档长度（支持自由输入，如：5000字、10页、3-5页等）")
    formality: Optional[str] = Field(
        default="半正式",
        description="正式程度（正式/半正式/非正式）")
    target_audience: Optional[str] = Field(
        default="上级领导/管理层",
        description="目标受众（上级领导管理层/客户合作伙伴/下属团队成员/社会公众/特定群体）")
    language_style: Optional[str] = Field(
        default="专业严谨",
        description="语言风格（专业严谨/简洁明了/生动活泼/说服力强/情感共鸣/数据驱动）")
    additional_requirements: Optional[str] = Field(
        None, description="附加要求（补充说明）")
    reference_document: Optional[str] = Field(
        None, description="参考文档URL（上传的文档文件路径，内容将被解析并嵌入提示词作为核心参考资料）")
    reference_document_name: Optional[str] = Field(
        None, description="参考文档文件名")


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
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # 枚举类型序列化为字符串值
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }


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
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # 枚举类型序列化为字符串值
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }


class ActionStatsResponse(BaseModel):
    """行为统计响应"""
    total_actions: int
    copy_count: int
    download_count: int
    regenerate_count: int
    copy_rate: float  # 复制率 = 复制数/总生成数
    download_rate: float  # 下载率 = 下载数/总生成数


# ==================== 提示词优化 ====================

class OptimizeModule(str, Enum):
    """支持的优化模块"""
    SHORT_VIDEO = "short_video"
    NOVEL = "novel"
    PRINT_AD = "print_ad"
    TVC = "tvc"
    ORIGINAL_IP = "original_ip"
    MOVIE_OUTLINE = "movie_outline"
    SERIES_OUTLINE = "series_outline"
    PRACTICAL_WRITING = "practical_writing"


class OptimizeRequest(BaseModel):
    """提示词优化请求"""
    module: str = Field(
        ...,
        description="模块名称（short_video/script/novel/print_ad/tvc/original_ip/practical_writing/movie_outline/series_outline）"
    )
    original_text: str = Field(
        ...,
        description="原始描述文本，最少5个字符"
    )


class OptimizeResponse(BaseModel):
    """提示词优化响应"""
    optimized_text: str = Field(..., description="优化后的文本")
    original_length: int = Field(..., description="原始文本长度")
    optimized_length: int = Field(..., description="优化后文本长度")
    module: str = Field(..., description="模块名称")
    module_name: str = Field(..., description="模块中文名称")


# ==================== 原创IP计划 ====================

class OriginalIPInput(BaseModel):
    """原创IP计划输入（简化版 - 用户只需提供概括性描述）"""
    ip_description: str = Field(
        ...,
        description="IP角色概括性描述（自由文本，AI将自动解析并补足各维度信息）",
        min_length=10
    )
    target_platform: Optional[str] = Field(
        None,
        description="目标平台（漫画/动画/游戏/周边/短视频/综合）"
    )
    reference_ip: Optional[str] = Field(
        None,
        description="参考的知名IP（可选，用于风格借鉴）"
    )
    commercial_goal: Optional[str] = Field(
        None,
        description="商业目标（可选，如：品牌代言、周边开发、内容IP化等）"
    )
    custom_requirements: Optional[str] = Field(
        None,
        description="其他特殊要求（可选）"
    )


# ==================== 修订相关 ====================

class RevisionRequest(BaseModel):
    """修订请求"""
    generation_id: int = Field(..., description="生成记录ID")
    user_feedback: str = Field(..., description="用户修改意见")
    current_content: str = Field(..., description="当前完整内容")
    original_params: Dict[str, Any] = Field(..., description="原始生成参数")
    module: str = Field(..., description="模块名称")
    round_number: int = Field(..., description="当前修订轮次")
    provider: Optional[str] = Field(None, description="LLM提供者")
    temperature: float = Field(default=0.7, ge=0, le=1, description="温度参数")


class FinalizeRequest(BaseModel):
    """最终确认请求"""
    generation_id: int = Field(..., description="生成记录ID")
    final_content: str = Field(..., description="最终确认的内容")
    enable_knowledge_check: bool = Field(default=True, description="是否启用知识库验证")
    enable_self_reflection: bool = Field(default=True, description="是否启用自反思")


# ==================== 单元概述质控相关 ====================

class UnitSummariesQCRequest(BaseModel):
    """单元概述质控请求（v3.0：仅自动修正模式）"""
    content_type: str = Field(..., description="内容类型（novel/script等）")
    global_outline: str = Field(default="", description="全局大纲内容")
    unit_summaries: Dict[str, Any] = Field(..., description="单元概述字典")
    temperature: float = Field(default=0.7, description="LLM温度参数")
