"""
多Agent协作文学作品生成系统 - 写作单元模型

模块: models
文件: writing_unit.py
功能: 定义写作单元的数据模型，管理文学作品生成中的单元级任务

依赖关系:
    - 依赖: app.models.base (BaseModel), sqlalchemy, enum
    - 被依赖: app.models.writing_task, app.models.writing_scene

使用说明:
    WritingUnit模型表示一个写作单元（如小说的一章或剧本的一集），包含单元状态、
    结构信息、最终内容等，通过relationship关联到WritingTask和WritingScene

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class UnitStatus(str, enum.Enum):
    """单元状态枚举"""
    PENDING = "pending"         # 等待中
    STRUCTURING = "structuring" # 结构分析中
    PROCESSING = "processing"   # 内容生成中
    COMPLETED = "completed"     # 已完成
    INTERRUPTED = "interrupted" # 已中断


class WritingUnit(BaseModel):
    """写作单元表 - 存储文学作品生成的单元级任务"""
    __tablename__ = "writing_units"
    __table_args__ = (
        UniqueConstraint('task_id', 'unit_index', name='uq_writing_units_task_unit'),
    )

    # 注意：id, created_at, updated_at 由BaseModel提供（整数自增主键）
    task_id = Column(Integer, ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, comment="关联任务ID")
    unit_index = Column(Integer, nullable=False, comment="单元序号")
    unit_title = Column(String(200), nullable=True, comment="单元标题")
    unit_summary = Column(Text, nullable=True, comment="单元概述")
    status = Column(Enum(UnitStatus), default=UnitStatus.PENDING, nullable=False, comment="单元状态")
    scenes_data = Column(JSON, default=list, comment="结构师输出的场景列表JSON")
    final_content = Column(Text, nullable=True, comment="最终合成内容")
    word_count = Column(Integer, default=0, comment="字数统计")
    token_count = Column(Integer, default=0, comment="Token消耗统计")
    duration_ms = Column(Integer, default=0, comment="生成耗时(毫秒)")

    # 关联关系
    task = relationship("WritingTask", back_populates="units")
    scenes = relationship("WritingScene", back_populates="unit", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WritingUnit(id={self.id}, task_id={self.task_id}, index={self.unit_index}, status={self.status})>"
