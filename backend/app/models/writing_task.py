"""
多Agent协作文学作品生成系统 - 写作任务模型

模块: models
文件: writing_task.py
功能: 定义写作任务的数据模型，管理多Agent协作生成任务的生命周期

依赖关系:
    - 依赖: app.models.base (BaseModel), sqlalchemy, enum
    - 被依赖: app.models.writing_unit, app.models.writing_checkpoint, app.models.writing_stat

使用说明:
    WritingTask模型用于存储和管理多Agent协作写作任务，包含任务状态、进度、配置等信息
    通过relationship关联到WritingUnit、WritingCheckpoint和WritingStat

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant
"""
from uuid import uuid4
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON, Float, DateTime
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class TaskStatus(str, enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"         # 等待中
    RUNNING = "running"         # 运行中
    CANCELLING = "cancelling"   # 取消中（已发送取消信号，尚未落地）
    INTERRUPTED = "interrupted" # 已中断
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消


class WritingTask(BaseModel):
    """写作任务表 - 管理多Agent协作文学作品生成任务"""
    __tablename__ = "writing_tasks"

    # 注意：id, created_at, updated_at 由BaseModel提供（整数自增主键）
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid4()), comment="外部引用UUID")
    project_id = Column(Integer, ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, comment="关联项目ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, comment="任务状态")
    total_units = Column(Integer, default=0, comment="总单元数")
    completed_units = Column(Integer, default=0, comment="已完成单元数")
    config = Column(JSON, default=dict, comment="任务配置JSON")
    start_from = Column(Integer, default=1, comment="起始单元序号")
    unit_count = Column(Integer, nullable=True, comment="生成单元数(None=全部)")
    total_tokens = Column(Integer, default=0, comment="总token消耗")
    total_cost = Column(Float, default=0.0, comment="总费用估算")
    error_message = Column(Text, nullable=True, comment="错误信息")
    start_time = Column(DateTime, nullable=True, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")

    # 关联关系
    units = relationship("WritingUnit", back_populates="task", cascade="all, delete-orphan")
    checkpoints = relationship("WritingCheckpoint", back_populates="task", cascade="all, delete-orphan")
    stats = relationship("WritingStat", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WritingTask(id={self.id}, uuid='{self.uuid}', status={self.status}, completed={self.completed_units}/{self.total_units})>"

    def get_progress_percentage(self) -> float:
        """获取任务进度百分比"""
        if self.total_units == 0:
            return 0.0
        return (self.completed_units / self.total_units) * 100

    def transition_to(self, new_status: "TaskStatus", reason: Optional[str] = None,
                      ended_at: Optional[datetime] = None) -> None:
        """按单一迁移表将任务状态推进到 new_status。

        非法迁移抛出 InvalidTaskTransitionException 并保留原状态；
        迁入终态时自动写入 end_time，失败/中断时将 reason 记录到 error_message。

        Args:
            new_status: 目标状态
            reason: 迁移原因（失败/中断时作为可查询原因写入 error_message）
            ended_at: 终态结束时间，缺省为当前时间
        """
        from app.services.task_manager_constants import (
            assert_task_transition_allowed,
            is_terminal_task_status,
        )
        assert_task_transition_allowed(self.status, new_status, reason=reason, ended_at=ended_at)
        self.status = new_status
        if is_terminal_task_status(new_status):
            self.end_time = ended_at or datetime.now()
        else:
            # 恢复、重试和继续生成会开启新一轮执行，旧的结束时间和错误原因不应残留。
            self.end_time = None
            self.error_message = None
        if reason and new_status in (TaskStatus.FAILED, TaskStatus.INTERRUPTED):
            self.error_message = reason
