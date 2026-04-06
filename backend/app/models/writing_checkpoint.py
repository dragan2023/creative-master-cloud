"""
多Agent协作文学作品生成系统 - 检查点模型

模块: models
文件: writing_checkpoint.py
功能: 定义写作任务检查点的数据模型，支持任务中断恢复

依赖关系:
    - 依赖: app.models.base (BaseModel), sqlalchemy
    - 被依赖: app.models.writing_task

使用说明:
    WritingCheckpoint模型用于保存任务执行状态检查点，支持任务中断后恢复执行。
    记录最后完成的单元、场景、操作以及各Agent的中间状态

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant
"""
from sqlalchemy import Column, String, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class WritingCheckpoint(BaseModel):
    """写作检查点表 - 存储任务执行状态检查点，支持中断恢复"""
    __tablename__ = "writing_checkpoints"

    # 注意：id, created_at, updated_at 由BaseModel提供（整数自增主键）
    task_id = Column(Integer, ForeignKey("writing_tasks.id", ondelete="CASCADE"), nullable=False, comment="关联任务ID")
    last_completed_unit = Column(Integer, default=0, comment="最后完成的单元序号")
    last_completed_scene_id = Column(Integer, nullable=True, comment="最后完成的场景ID")
    last_operation = Column(String(50), nullable=True, comment="最后执行的操作")
    agent_states = Column(JSON, default=dict, comment="各Agent的中间状态JSON")

    # 关联关系
    task = relationship("WritingTask", back_populates="checkpoints")

    def __repr__(self):
        return f"<WritingCheckpoint(id={self.id}, task_id={self.task_id}, last_unit={self.last_completed_unit})>"
