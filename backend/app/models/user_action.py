"""
用户行为追踪模型
记录用户的复制、下载等行为以及体验事件用于统计分析
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, Boolean
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class ActionType(str, enum.Enum):
    """行为类型枚举"""
    # ---- 原有 UI 动作 ----
    COPY = "copy"           # 复制内容
    DOWNLOAD = "download"   # 下载内容
    REGENERATE = "regenerate"  # 重新生成
    LIKE = "like"           # 点赞/收藏
    SHARE = "share"         # 分享

    # ---- 体验事件（阶段04新增） ----
    CREATION_STARTED = "creation_started"      # 创作开始
    CREATION_COMPLETED = "creation_completed"   # 创作完成
    CREATION_CANCELLED = "creation_cancelled"   # 创作取消
    TASK_RESTORED = "task_restored"             # 任务恢复
    REVISION_APPLIED = "revision_applied"       # 修订应用
    REVISION_REVERTED = "revision_reverted"     # 修订撤销
    ERROR_RECOVERED = "error_recovered"         # 错误恢复


# 体验事件列表（便于前端过滤）
EXPERIENCE_EVENTS = {
    ActionType.CREATION_STARTED,
    ActionType.CREATION_COMPLETED,
    ActionType.CREATION_CANCELLED,
    ActionType.TASK_RESTORED,
    ActionType.REVISION_APPLIED,
    ActionType.REVISION_REVERTED,
    ActionType.ERROR_RECOVERED,
}


class UserAction(BaseModel):
    """用户行为追踪表"""
    __tablename__ = "user_actions"

    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    generation_id = Column(Integer, ForeignKey(
        "generations.id", ondelete="CASCADE"), nullable=True, comment="生成记录ID")
    module = Column(String(50), nullable=False, comment="模块名称")
    action = Column(Enum(ActionType), nullable=False, comment="行为类型")

    # ---- 原有字段 ----
    content_snippet = Column(Text, nullable=True, comment="内容片段(前100字符，仅用于 UI 动作)")

    # ---- 体验事件属性（阶段04新增） ----
    phase = Column(String(30), nullable=True, comment="创作阶段: outline/generation/qc/revision/finalize")
    duration_bucket = Column(String(20), nullable=True, comment="时长分桶: <10s/10-30s/30-60s/1-5min/5-15min/>15min")
    error_category = Column(String(30), nullable=True, comment="错误类别: network/unauthorized/rate-limited/model-unavailable/task-interrupted")
    is_retry = Column(Boolean, default=False, nullable=True, comment="是否重试操作")
    is_first_use = Column(Boolean, default=False, nullable=True, comment="是否用户首次使用")

    # ---- JSON 元数据（向后兼容） ----
    action_metadata = Column("metadata", String(
        500), nullable=True, comment="行为元数据(JSON)")

    # 关联关系
    user = relationship("User", back_populates="actions")
    generation = relationship("Generation")

    def __repr__(self):
        return f"<UserAction(id={self.id}, user_id={self.user_id}, action={self.action})>"

    def is_experience_event(self) -> bool:
        """判断当前记录是否为体验事件"""
        return self.action in EXPERIENCE_EVENTS
