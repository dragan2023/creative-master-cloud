"""
多Agent协作文学作品生成系统 - 写作统计模型

模块: models
文件: writing_stat.py
功能: 定义写作任务统计的数据模型，记录各Agent的Token消耗和性能指标

依赖关系:
    - 依赖: app.models.base (BaseModel), sqlalchemy
    - 被依赖: app.models.writing_task

使用说明:
    WritingStat模型用于记录每个Agent的详细统计信息，包括Token消耗、耗时、
    费用估算等，用于成本分析和性能监控

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class WritingStat(BaseModel):
    """写作统计表 - 记录各Agent的Token消耗和性能指标"""
    __tablename__ = "writing_stats"

    # 注意：id, created_at, updated_at 由BaseModel提供（整数自增主键）
    task_id = Column(Integer, ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, comment="关联任务ID")
    agent_name = Column(String(50), nullable=False, comment="Agent名称")
    model_id = Column(String(100), nullable=False, comment="使用的模型ID")
    scene_id = Column(Integer, nullable=True, comment="关联场景ID")
    input_tokens = Column(Integer, default=0, comment="输入token数")
    output_tokens = Column(Integer, default=0, comment="输出token数")
    total_tokens = Column(Integer, default=0, comment="总token数")
    duration_sec = Column(Float, default=0.0, comment="耗时（秒）")
    estimated_cost = Column(Float, default=0.0, comment="估算费用")

    # 关联关系
    task = relationship("WritingTask", back_populates="stats")

    def __repr__(self):
        return f"<WritingStat(id={self.id}, task_id={self.task_id}, agent={self.agent_name}, tokens={self.total_tokens})>"
