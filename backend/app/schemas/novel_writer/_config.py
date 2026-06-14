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

    # 文风图书馆配置（新增）
    style_library_config: Optional[Dict[str, Any]] = Field(
        None,
        description="文风图书馆配置，包含 selected_style_ids, style_intensity, style_guide"
    )

    model_config = {
        "from_attributes": True
    }


# ==================== 剧集剧本专属配置 ====================



class SeriesScriptConfig(BaseModel):
    """剧集剧本正文生成专属配置

    生成单位：分集（按大纲中的集数划分）

    【核心指标说明】
    剧本以"时长"为核心控制指标，字数为参考值：
    - 时长控制：通过 episode_duration_range 设置每集时长范围
    - 字数参考：可选，仅作为LLM参考，不强制约束
    - 实际篇幅由剧情需要和场景规划决定
    """
    # 剧集类型
    series_type: str = Field(
        default="电视剧",
        description="剧集类型（电视剧/网络剧/短剧/微短剧/网剧/竖屏剧）"
    )

    # 每集时长范围（核心指标）
    # 注意：时长范围根据剧集类型动态确定，以下为通用默认值
    # 实际默认值在前端根据series_type设置：
    # - 电视剧: 45-60分钟
    # - 网络剧: 30-50分钟
    # - 短剧/微短剧: 3-15分钟
    # - 竖屏剧: 1-5分钟
    episode_duration_range: Optional[List[int]] = Field(
        default=None,
        description="每集时长区间(分钟) - 根据剧集类型自动设置，也可手动指定"
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

    # 每集字数（可选参考）
    words_per_episode: Optional[int] = Field(
        None,
        description="每集参考字数（可选，剧本以时长为核心指标，字数仅供参考）"
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

    # 叙事模式（连续剧 vs 单元剧 vs 主线串联单元剧）
    narrative_mode: str = Field(
        default="serialized",
        description="叙事模式（serialized=连续剧，各集情节连贯；episodic=纯单元剧，每集完全独立；episodic_with_arc=主线串联单元剧，各集独立但共享主线/常驻角色）"
    )

    # 风格选择器配置（新增）
    style_selector_config: Optional[Dict[str, Any]] = Field(
        None,
        description="剧集风格选择器配置，来自 SeriesStyleSelectorDialog"
    )

    model_config = {
        "from_attributes": True
    }


# ==================== 电影剧本专属配置 ====================



class MovieScriptConfig(BaseModel):
    """电影剧本正文生成专属配置

    生成单位：场景（按大纲中的场景或段落划分）

    【核心指标说明】
    电影剧本以"时长"为核心控制指标：
    - 总时长控制：通过 total_duration 设置电影总时长
    - 每场戏时长：根据场景大纲中的 duration_minutes 分配
    - 字数参考：约250字/分钟，不强制约束
    """
    # 电影类型
    movie_type: str = Field(
        default="院线电影",
        description="电影类型（院线电影/网络电影/微电影/纪录片/动画电影）"
    )

    # 电影总时长（核心指标）
    # 注意：时长根据电影类型动态确定，以下为通用默认值
    # 实际默认值在前端根据movie_type设置：
    # - 院线电影: 90-120分钟
    # - 网络电影: 60-90分钟
    # - 微电影: 20-45分钟
    # - 纪录片: 45-90分钟（灵活）
    # - 动画电影: 80-100分钟
    total_duration: Optional[int] = Field(
        default=None,
        description="电影总时长(分钟) - 根据电影类型自动设置，也可手动指定"
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

    # 叙事模式（连续叙事 vs 短片合集/单元电影 vs 主线串联单元电影）
    narrative_mode: str = Field(
        default="serialized",
        description="叙事模式（serialized=连续叙事，情节连贯推进；episodic=纯单元电影/短片合集，各段完全独立；episodic_with_arc=主线串联单元电影，各段独立但共享主线/常驻角色）"
    )

    # 风格选择器配置（新增）
    style_selector_config: Optional[Dict[str, Any]] = Field(
        None,
        description="电影风格选择器配置，来自 MovieStyleSelectorDialog"
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
