"""
多Agent协作文学作品生成系统 - 写作场景模型

模块: models
文件: writing_scene.py
功能: 定义写作场景的数据模型，管理场景级的内容生成和Agent协作

依赖关系:
    - 依赖: app.models.base (BaseModel), sqlalchemy, enum
    - 被依赖: app.models.writing_unit

使用说明:
    WritingScene模型表示一个写作场景，记录场景的结构信息、各Agent处理结果、
    最终内容等，通过relationship关联到WritingUnit

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class SceneStatus(str, enum.Enum):
    """场景状态枚举"""
    PENDING = "pending"     # 等待中
    WRITING = "writing"     # 写手生成中
    REVIEWING = "reviewing" # 审核中
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 失败


class WritingScene(BaseModel):
    """写作场景表 - 存储场景级内容生成和Agent协作结果"""
    __tablename__ = "writing_scenes"
    __table_args__ = (
        UniqueConstraint('unit_id', 'scene_index', name='uq_writing_scenes_unit_scene'),
    )

    # 注意：id, created_at, updated_at 由BaseModel提供（整数自增主键）
    unit_id = Column(Integer, ForeignKey("writing_units.id", ondelete="CASCADE"), nullable=False, comment="关联单元ID")
    scene_index = Column(Integer, nullable=False, comment="场景序号")
    scene_title = Column(String(200), nullable=True, comment="场景标题")
    scene_outline = Column(JSON, default=dict, comment="场景大纲JSON {location, characters, event, mood, word_target, hook}")
    status = Column(Enum(SceneStatus), default=SceneStatus.PENDING, nullable=False, comment="场景状态")
    writer_result = Column(JSON, nullable=True, comment="写手Agent输出")
    editor_result = Column(JSON, nullable=True, comment="逻辑编辑Agent输出")
    stylist_result = Column(JSON, nullable=True, comment="风格润色Agent输出")
    compliance_result = Column(JSON, nullable=True, comment="合规审查Agent输出")
    final_content = Column(Text, nullable=True, comment="最终内容")
    word_count = Column(Integer, default=0, comment="字数统计")
    token_count = Column(Integer, default=0, comment="Token消耗统计")
    duration_ms = Column(Integer, default=0, comment="生成耗时(毫秒)")

    # 关联关系
    unit = relationship("WritingUnit", back_populates="scenes")

    def __repr__(self):
        return f"<WritingScene(id={self.id}, unit_id={self.unit_id}, index={self.scene_index}, status={self.status})>"
