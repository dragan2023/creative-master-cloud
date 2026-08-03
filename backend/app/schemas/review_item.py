"""
统一审阅项数据模型

定义质控问题与修订建议的结构化表达，作为前后端共享的数据契约。
历史报告缺少字段时，前端降级为只读报告。

@date: 2026-07-24
@version: v1.0
"""

from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field


# ════════════════════════════════════════════
# 枚举定义
# ════════════════════════════════════════════

class ReviewSeverity(str, Enum):
    """审阅项风险级别"""
    CRITICAL = "critical"   # 严重：阻塞性问题
    MAJOR = "major"         # 重要：影响质量
    MINOR = "minor"         # 建议：优化建议


class ReviewStatus(str, Enum):
    """审阅项应用状态"""
    PENDING = "pending"       # 待处理
    APPLIED = "applied"       # 已应用
    SKIPPED = "skipped"       # 已跳过
    REVERTED = "reverted"     # 已撤销


class KnowledgeSourceType(str, Enum):
    """知识来源类型"""
    KNOWLEDGE_BASE = "knowledge_base"    # 知识库驱动
    MODEL_INFERENCE = "model_inference"  # 模型推断
    HYBRID = "hybrid"                    # 混合来源


# ════════════════════════════════════════════
# 内嵌模型
# ════════════════════════════════════════════

class KnowledgeSource(BaseModel):
    """知识来源信息"""
    source_type: KnowledgeSourceType = Field(
        default=KnowledgeSourceType.MODEL_INFERENCE,
        description="知识来源类型"
    )
    material_name: Optional[str] = Field(
        default=None, description="资料名称（知识库来源时必填）"
    )
    hit_snippet: Optional[str] = Field(
        default=None, description="命中片段（知识库来源时提供）"
    )
    source_id: Optional[str] = Field(
        default=None, description="知识库条目ID（用于查看来源）"
    )


class ReviewLocation(BaseModel):
    """审阅项定位信息"""
    chapter_number: Optional[int] = Field(
        default=None, description="章节/单元编号"
    )
    paragraph_index: Optional[int] = Field(
        default=None, description="段落索引"
    )
    section_name: Optional[str] = Field(
        default=None, description="所属节名称"
    )
    character_range: Optional[str] = Field(
        default=None, description="字符偏移范围"
    )


class RevisionVersion(BaseModel):
    """修订版本记录"""
    version_id: str = Field(description="版本标识")
    qc_report_id: Optional[int] = Field(
        default=None, description="关联质控报告ID"
    )
    applied_at: Optional[str] = Field(
        default=None, description="应用时间（ISO格式）"
    )
    applied_by: Optional[str] = Field(
        default=None, description="操作者（user/system）"
    )


# ════════════════════════════════════════════
# 核心审阅项模型
# ════════════════════════════════════════════

class ReviewItem(BaseModel):
    """统一审阅项 - 单项修订的完整描述"""
    issue_id: str = Field(
        description="问题唯一标识（如 qc-42-style-3）"
    )
    dimension: str = Field(
        description="问题维度（style/structure/consistency/character/logic...）"
    )
    severity: ReviewSeverity = Field(
        default=ReviewSeverity.MINOR,
        description="风险级别"
    )

    # 问题描述
    reason: str = Field(
        description="问题说明（原因）"
    )
    evidence: Optional[str] = Field(
        default=None, description="原文证据定位"
    )

    # 修改内容
    before_text: Optional[str] = Field(
        default=None, description="原文（修改前）"
    )
    after_text: Optional[str] = Field(
        default=None, description="建议文本（修改后）"
    )

    # 状态与追踪
    status: ReviewStatus = Field(
        default=ReviewStatus.PENDING,
        description="当前应用状态"
    )
    location: Optional[ReviewLocation] = Field(
        default=None, description="定位信息"
    )
    knowledge_source: Optional[KnowledgeSource] = Field(
        default=None, description="知识来源"
    )
    versions: List[RevisionVersion] = Field(
        default_factory=list, description="修订版本历史"
    )

    # 兼容旧字段
    description: Optional[str] = Field(
        default=None, description="(兼容) 问题描述"
    )
    suggestion: Optional[str] = Field(
        default=None, description="(兼容) 修改建议"
    )
    category: Optional[str] = Field(
        default=None, description="(兼容) 问题分类"
    )

    def is_low_risk(self) -> bool:
        """是否为低风险项（可批量应用）"""
        return self.severity == ReviewSeverity.MINOR

    def can_apply(self) -> bool:
        """是否可应用"""
        return self.status in (ReviewStatus.PENDING, ReviewStatus.REVERTED)

    def to_dict(self, exclude_none: bool = True) -> dict:
        """转为字典（兼容旧版报告格式）"""
        data = self.model_dump(exclude_none=exclude_none)
        # 兼容旧字段映射
        if self.description:
            data["description"] = self.description
        if self.suggestion:
            data["suggestion"] = self.suggestion
        if self.category:
            data["category"] = self.category
        return data


# ════════════════════════════════════════════
# 请求/响应模型
# ════════════════════════════════════════════

class ApplyReviewItemsRequest(BaseModel):
    """批量应用审阅项请求"""
    issue_ids: List[str] = Field(
        description="要应用的问题ID列表"
    )
    project_id: Optional[int] = Field(
        default=None, description="项目ID"
    )
    qc_report_id: Optional[int] = Field(
        default=None, description="质控报告ID（用于版本关联）"
    )
    operator: str = Field(
        default="user", description="操作者标识"
    )


class ApplyReviewItemsResponse(BaseModel):
    """批量应用审阅项响应"""
    applied_count: int = Field(description="成功应用数量")
    skipped_count: int = Field(description="跳过数量")
    failed_items: List[str] = Field(
        default_factory=list, description="失败的问题ID列表"
    )
    version_id: Optional[str] = Field(
        default=None, description="生成的版本标识"
    )


class UndoReviewItemsRequest(BaseModel):
    """批量撤销审阅项请求"""
    issue_ids: List[str] = Field(
        description="要撤销的问题ID列表"
    )
    project_id: Optional[int] = Field(default=None, description="项目ID")
    operator: str = Field(
        default="user", description="操作者标识"
    )


class ReviewItemSummary(BaseModel):
    """审阅项摘要（用于列表）"""
    issue_id: str
    dimension: str
    severity: ReviewSeverity
    reason: str
    status: ReviewStatus
    has_knowledge_source: bool = Field(default=False)
