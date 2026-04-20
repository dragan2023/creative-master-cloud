"""
质量分析报告模型
存储质量分析结果和历史报告

@date: 2026-04-12
@version: v3.1.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON, Float, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models.base import BaseModel


class AnalysisScope(str, enum.Enum):
    """分析范围枚举"""
    SINGLE_CHAPTER = "single_chapter"      # 单章
    MULTI_CHAPTER = "multi_chapter"        # 多章
    FULL_BOOK = "full_book"                # 全书


class AnalysisStatus(str, enum.Enum):
    """分析状态枚举"""
    PENDING = "pending"           # 待分析
    GENERATING = "generating"     # 分析中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


class QualityReport(BaseModel):
    """质量分析报告表"""
    __tablename__ = "quality_reports"

    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    project_id = Column(Integer, ForeignKey(
        "novel_projects.id", ondelete="CASCADE"), nullable=False, comment="项目ID")

    # 分析配置
    analysis_scope = Column(
        Enum(AnalysisScope),
        nullable=False,
        comment="分析范围(single_chapter/multi_chapter/full_book)"
    )
    chapters_analyzed = Column(JSON, nullable=True, comment="分析的章节ID列表")
    dimensions = Column(JSON, nullable=False, comment="分析维度列表")
    analysis_depth = Column(
        String(20),
        default="standard",
        comment="分析深度(quick/standard/deep)"
    )

    # 分析结果
    overall_score = Column(Float, nullable=True, comment="综合评分(0-100)")
    dimension_scores = Column(JSON, nullable=True, comment="各维度得分")
    report_data = Column(JSON, nullable=True, comment="完整报告数据(JSON)")

    # 统计信息
    total_issues = Column(Integer, default=0, comment="问题总数")
    critical_issues = Column(Integer, default=0, comment="严重问题数")
    warning_issues = Column(Integer, default=0, comment="警告问题数")
    info_issues = Column(Integer, default=0, comment="建议问题数")

    # Token消耗统计
    total_tokens = Column(Integer, default=0, comment="总Token消耗")
    rule_engine_tokens = Column(Integer, default=0, comment="规则引擎Token(应为0)")
    llm_tokens = Column(Integer, default=0, comment="LLM Token消耗")

    # 状态信息
    status = Column(
        Enum(AnalysisStatus),
        default=AnalysisStatus.PENDING,
        nullable=False,
        comment="分析状态"
    )
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 时间统计
    started_at = Column(String(50), nullable=True, comment="开始分析时间")
    completed_at = Column(String(50), nullable=True, comment="完成分析时间")
    duration_ms = Column(Integer, default=0, comment="分析耗时(毫秒)")

    # 缓存相关
    content_hash = Column(String(64), nullable=True, comment="内容哈希(用于缓存)")
    cache_key = Column(String(200), nullable=True, comment="缓存键")
    is_cached = Column(Boolean, default=False, comment="是否来自缓存")

    # 关联关系
    project = relationship("NovelProject", backref="quality_reports")
    user = relationship("User", backref="quality_reports")

    def __repr__(self):
        return f"<QualityReport(id={self.id}, project={self.project_id}, score={self.overall_score}, status={self.status})>"

    def to_dict(self, exclude: list = None) -> dict:
        """转换为字典"""
        exclude = exclude or []
        result = super().to_dict(exclude)
        # 确保枚举值正确转换
        if self.analysis_scope:
            result["analysis_scope"] = self.analysis_scope.value
        if self.status:
            result["status"] = self.status.value
        return result

    def to_summary_dict(self) -> dict:
        """转换为摘要字典(用于列表展示)"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "analysis_scope": self.analysis_scope.value if self.analysis_scope else None,
            "dimensions": self.dimensions,
            "overall_score": self.overall_score,
            "total_issues": self.total_issues,
            "critical_issues": self.critical_issues,
            "warning_issues": self.warning_issues,
            "info_issues": self.info_issues,
            "status": self.status.value if self.status else None,
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
            "is_cached": self.is_cached,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at
        }
