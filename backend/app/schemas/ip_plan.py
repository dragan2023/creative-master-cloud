"""
原创IP计划相关 Schema
支持简化的用户输入，AI自动解析和构建完整角色IP档案
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OriginalIPInput(BaseModel):
    """原创IP计划输入（简化版）"""
    # 核心输入：用户只需提供一个概括性描述
    ip_description: str = Field(
        ...,
        description="IP角色概括性描述（自由文本，AI将自动解析并补足各维度信息）",
        min_length=10
    )

    # 可选的辅助输入
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


# ==================== AI解析后的结构化输出 ====================

class CharacterBasicInfo(BaseModel):
    """角色基本信息"""
    name: str = Field(..., description="角色名称")
    species: str = Field(..., description="物种/身份")
    one_line_intro: str = Field(..., description="一句话介绍")
    age_appearance: str = Field(..., description="年龄外貌")


class VisualDesign(BaseModel):
    """视觉设计"""
    silhouette_feature: str = Field(..., description="轮廓特征（即使黑白剪影也能认出）")
    main_color: str = Field(..., description="主色调（1-2种主色）")
    iconic_prop: str = Field(..., description="标志道具")
    dynamic_feature: str = Field(..., description="动态特点")
    eye_feature: str = Field(..., description="眼睛特征（最吸睛的部位）")


class BackgroundStory(BaseModel):
    """背景故事"""
    origin_story: str = Field(..., description="起源一句话")
    current_residence: str = Field(..., description="现居地")
    existence_meaning: str = Field(..., description="存在意义")
    secret: str = Field(..., description="小秘密（只有自己知道的事）")


class PersonalityTag(BaseModel):
    """性格标签"""
    tag: str = Field(..., description="标签名称")
    behavior: str = Field(..., description="行为表现")


class LanguageStyle(BaseModel):
    """语言风格"""
    catchphrase: str = Field(..., description="口头禅")
    tone_words: str = Field(..., description="语气词")
    speaking_habit: str = Field(..., description="说话习惯")
    unique_expression: str = Field(..., description="独特表达方式")


class BehaviorPattern(BaseModel):
    """行为模式"""
    signature_action: str = Field(..., description="标志性动作")
    daily_routine: str = Field(..., description="日常流程")
    special_ability: str = Field(..., description="特殊能力")
    weakness: str = Field(..., description="弱点/克星")


class RelationshipNetwork(BaseModel):
    """关系网络"""
    important_people: str = Field(..., description="重要的人")
    peers_rivals: str = Field(..., description="同类/对手")
    want_to_approach: str = Field(..., description="想亲近的人")
    want_to_escape: str = Field(..., description="想逃离的人")


class StoryDirection(BaseModel):
    """故事方向"""
    direction: str = Field(..., description="方向描述")
    potential: str = Field(..., description="发展潜力")


class ExtendabilityDesign(BaseModel):
    """可扩展性设计"""
    relationship_network: List[str] = Field(..., description="关系网设计要点")
    growth_space: List[str] = Field(..., description="成长空间")
    world_expansion: List[str] = Field(..., description="世界扩展接口")


class IPValidationResult(BaseModel):
    """IP检验结果"""
    silhouette_test: str = Field(..., description="剪影测试结果")
    dialogue_test: str = Field(..., description="台词测试结果")
    interaction_expectation: str = Field(..., description="互动预期")
    fan_creation_space: str = Field(..., description="二创空间")
    emotional_projection: str = Field(..., description="情感投射点")


class PracticalGuide(BaseModel):
    """实操流程"""
    concept_phase: str = Field(..., description="概念确认阶段")
    design_phase: str = Field(..., description="设计深化阶段")
    test_phase: str = Field(..., description="测试验证阶段")
    iteration_phase: str = Field(..., description="迭代优化阶段")


class CommercialPlan(BaseModel):
    """落地方案"""
    commercial_path: str = Field(..., description="商业化路径")
    promotion_strategy: str = Field(..., description="推广策略")
    derivative_products: str = Field(..., description="衍生品开发建议")


class AIAssistedPlan(BaseModel):
    """AI辅助执行方案"""
    visual_design_tools: str = Field(..., description="视觉设计AI工具推荐")
    content_generation_workflow: str = Field(..., description="内容生成工作流")
    promotion_copy_generation: str = Field(..., description="推广文案生成方案")


class DevelopmentRoadmap(BaseModel):
    """角色发展路线图"""
    short_term: str = Field(..., description="短期规划（1-3个月）")
    mid_term: str = Field(..., description="中期规划（3-12个月）")
    long_term: str = Field(..., description="长期规划（1-3年）")


class IPPlanOutput(BaseModel):
    """原创IP计划完整输出"""
    # 完整角色IP档案
    basic_info: CharacterBasicInfo = Field(..., description="角色基本信息")
    visual_design: VisualDesign = Field(..., description="视觉设计")
    background_story: BackgroundStory = Field(..., description="背景故事")
    personality_tags: List[PersonalityTag] = Field(
        ..., description="性格标签（3-5个）")
    language_style: LanguageStyle = Field(..., description="语言风格")
    behavior_pattern: BehaviorPattern = Field(..., description="行为模式")
    relationship_network: RelationshipNetwork = Field(..., description="关系网络")
    story_directions: List[StoryDirection] = Field(
        ..., description="潜在故事线（3个方向）")

    # 可扩展性设计
    extendability: ExtendabilityDesign = Field(..., description="可扩展性设计")

    # IP检验结果
    validation: IPValidationResult = Field(..., description="IP检验结果")

    # 实操指导
    practical_guide: PracticalGuide = Field(..., description="实操流程")
    commercial_plan: CommercialPlan = Field(..., description="落地方案")
    ai_assisted_plan: AIAssistedPlan = Field(..., description="AI辅助执行方案")
    roadmap: DevelopmentRoadmap = Field(..., description="角色发展路线图")

    # 元信息
    generation_summary: str = Field(..., description="生成摘要")
    suggestions: str = Field(..., description="进一步优化建议")


class IPPlanGenerateRequest(BaseModel):
    """IP计划生成请求"""
    input_params: OriginalIPInput = Field(..., description="输入参数")
    session_id: Optional[str] = Field(None, description="会话ID（用于多轮对话）")
    provider: Optional[str] = Field(None, description="指定LLM提供者")
    temperature: float = Field(
        default=0.8, ge=0, le=1, description="温度参数（创意性任务建议0.8）")


class IPPlanGenerateResponse(BaseModel):
    """IP计划生成响应"""
    success: bool
    content: Optional[str] = None  # Markdown格式的完整输出
    structured_output: Optional[IPPlanOutput] = None  # 结构化输出（可选）
    model: Optional[str] = None
    provider: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    duration_ms: Optional[int] = None
    generation_id: Optional[int] = None
    error: Optional[str] = None
