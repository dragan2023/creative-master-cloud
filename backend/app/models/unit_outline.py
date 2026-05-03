"""
单元大纲独立存储模型（P1状态：迁移暂停）

将大型JSON字段(unit_summaries/episode_outlines/scene_outlines/chapter_outlines)
迁移到独立表，支持增量查询/更新，避免100+章项目单行数据过大。

当前状态（2026-04-27）:
- 独立表已创建但暂未启用写入
- 所有大纲仍通过JSON字段存储（chapter_outlines等）
- 双写策略暂停，待下个版本完整迁移

迁移计划:
- Phase 1: 创建表结构（已完成）
- Phase 2: 双写测试（暂停）
- Phase 3: 单写迁移（待定）
- Phase 4: 移除JSON字段（待定）

@date: 2026-04-19
@version: v1.0.0
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class UnitOutline(BaseModel):
    """单元大纲独立表

    存储每个单元（章节/集/场）的大纲数据，替代原来存储在
    NovelProject.unit_summaries等JSON字段中的方式。

    优势：
    - 查询单章大纲无需加载全部JSON
    - 支持增量更新单章大纲
    - 大纲修改可独立追踪
    """
    __tablename__ = "unit_outlines"

    project_id = Column(
        Integer,
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联项目ID"
    )
    unit_number = Column(
        Integer,
        nullable=False,
        comment="单元编号（章节号/集号/场号）"
    )
    content_type = Column(
        String(20),
        nullable=False,
        comment="内容类型(novel/series_script/movie_script)"
    )
    title = Column(
        String(200),
        nullable=True,
        comment="单元标题"
    )
    summary = Column(
        Text,
        nullable=True,
        comment="单元概述（100-200字）"
    )
    detailed_outline = Column(
        Text,
        nullable=True,
        comment="详细大纲"
    )
    key_events = Column(
        JSON,
        nullable=True,
        comment="关键事件列表"
    )
    character_arcs = Column(
        Text,
        nullable=True,
        comment="角色发展线"
    )
    status = Column(
        String(20),
        default="pending",
        comment="状态(pending/generated/edited)"
    )

    # 关联关系
    project = relationship("NovelProject", backref="unit_outline_records")

    __table_args__ = (
        Index('ix_unit_outline_project_unit',
              'project_id', 'unit_number', unique=True),
        Index('ix_unit_outline_project_type', 'project_id', 'content_type'),
    )

    def __repr__(self):
        return f"<UnitOutline(id={self.id}, project_id={self.project_id}, unit={self.unit_number}, type={self.content_type})>"

    def to_dict(self) -> dict:
        """转换为字典（兼容JSON字段格式）"""
        return {
            "unit_number": self.unit_number,
            "title": self.title or "",
            "summary": self.summary or "",
            "detailed_outline": self.detailed_outline or "",
            "key_events": self.key_events or [],
            "character_arcs": self.character_arcs or "",
            "status": self.status or "pending",
        }
