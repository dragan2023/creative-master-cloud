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



class VocabularyProfile(BaseModel):
    """词汇偏好"""
    word_preference: Optional[str] = Field(None, description="词汇偏好")
    vocabulary_density: Optional[str] = Field(None, description="词汇密度")
    signature_words: Optional[List[str]] = Field(
        default_factory=list, description="标志性词汇")
    special_expressions: Optional[List[str]] = Field(
        default_factory=list, description="特殊表达")




class SentenceStructureProfile(BaseModel):
    """句式结构"""
    average_length: Optional[str] = Field(None, description="平均句长")
    length_ratio: Optional[str] = Field(None, description="长短句比例")
    preferred_patterns: Optional[List[str]] = Field(
        default_factory=list, description="偏好句式")
    punctuation_style: Optional[str] = Field(None, description="标点风格")




class NarrativeStyleProfile(BaseModel):
    """叙事风格"""
    perspective: Optional[str] = Field(None, description="叙事视角")
    pacing: Optional[str] = Field(None, description="节奏控制")
    time_space_handling: Optional[str] = Field(None, description="时空处理")
    narrative_distance: Optional[str] = Field(None, description="叙事距离")




class DescriptionStyleProfile(BaseModel):
    """描写风格"""
    focus_areas: Optional[List[str]] = Field(
        default_factory=list, description="关注领域")
    sensory_usage: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="感官运用")
    rhetorical_devices: Optional[List[str]] = Field(
        default_factory=list, description="修辞手法")
    detail_level: Optional[str] = Field(None, description="细节程度")




class DialogueStyleProfile(BaseModel):
    """对话风格"""
    overall_style: Optional[str] = Field(None, description="整体风格")
    density: Optional[str] = Field(None, description="对话密度")
    character_distinction: Optional[str] = Field(None, description="角色区分")
    functional_focus: Optional[str] = Field(None, description="功能焦点")




class EmotionalExpressionProfile(BaseModel):
    """情感表达"""
    tone: Optional[str] = Field(None, description="情感基调")
    expression_method: Optional[str] = Field(None, description="表达方式")
    intensity: Optional[str] = Field(None, description="情感强度")
    complexity: Optional[str] = Field(None, description="情感复杂性")




class StructuralFeaturesProfile(BaseModel):
    """结构特征"""
    paragraph_length: Optional[str] = Field(None, description="段落长度")
    opening_style: Optional[str] = Field(None, description="开篇风格")
    transition_style: Optional[str] = Field(None, description="过渡风格")
    ending_style: Optional[str] = Field(None, description="结尾风格")
    hook_usage: Optional[str] = Field(None, description="悬念运用")




class StyleProfile(BaseModel):
    """风格画像"""
    name: Optional[str] = Field(None, description="风格名称")
    vocabulary: Optional[VocabularyProfile] = Field(None, description="词汇偏好")
    sentence_structure: Optional[SentenceStructureProfile] = Field(
        None, description="句式结构")
    narrative_style: Optional[NarrativeStyleProfile] = Field(
        None, description="叙事风格")
    description_style: Optional[DescriptionStyleProfile] = Field(
        None, description="描写风格")
    dialogue_style: Optional[DialogueStyleProfile] = Field(
        None, description="对话风格")
    emotional_expression: Optional[EmotionalExpressionProfile] = Field(
        None, description="情感表达")
    structural_features: Optional[StructuralFeaturesProfile] = Field(
        None, description="结构特征")




class ExampleTransformation(BaseModel):
    """示例转换"""
    original: Optional[str] = Field(None, description="原始文本")
    styled: Optional[str] = Field(None, description="风格化文本")
    explanation: Optional[str] = Field(None, description="转换说明")




class StyleDocumentResponse(BaseModel):
    """风格文档响应"""
    project_id: int
    style_document_uploaded: bool = Field(
        default=False, description="是否已上传风格文档")
    style_document_name: Optional[str] = Field(None, description="风格文档名称")
    style_profile: Optional[StyleProfile] = Field(None, description="风格画像")
    style_guide_for_writing: Optional[str] = Field(None, description="写作风格指南")
    key_imitation_points: Optional[List[str]] = Field(
        default_factory=list, description="关键模仿要点")
    example_transformations: Optional[List[ExampleTransformation]] = Field(
        default_factory=list, description="示例转换")
    avoid_patterns: Optional[List[str]] = Field(
        default_factory=list, description="避免模式")
    ai_elimination_enabled: bool = Field(
        default=True, description="是否启用AI文风消除")
    ai_elimination_threshold: int = Field(default=50, description="AI文风消除阈值")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")




class StyleDocumentUpdate(BaseModel):
    """风格文档更新请求"""
    ai_elimination_enabled: Optional[bool] = Field(
        None, description="是否启用AI文风消除")
    ai_elimination_threshold: Optional[int] = Field(
        None, ge=0, le=100, description="AI文风消除阈值")

