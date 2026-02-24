"""
用户行为追踪模型
记录用户的复制、下载等行为用于统计分析
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class ActionType(str, enum.Enum):
    """行为类型枚举"""
    COPY = "copy"           # 复制内容
    DOWNLOAD = "download"   # 下载内容
    REGENERATE = "regenerate"  # 重新生成
    LIKE = "like"           # 点赞/收藏
    SHARE = "share"         # 分享


class UserAction(BaseModel):
    """用户行为追踪表"""
    __tablename__ = "user_actions"

    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    generation_id = Column(Integer, ForeignKey(
        "generations.id", ondelete="CASCADE"), nullable=True, comment="生成记录ID")
    module = Column(String(50), nullable=False, comment="模块名称")
    action = Column(Enum(ActionType), nullable=False, comment="行为类型")

    # 行为详情
    content_snippet = Column(Text, nullable=True, comment="内容片段(前100字符)")
    action_metadata = Column("metadata", String(
        500), nullable=True, comment="行为元数据(JSON)")

    # 关联关系
    user = relationship("User", back_populates="actions")
    generation = relationship("Generation")

    def __repr__(self):
        return f"<UserAction(id={self.id}, user_id={self.user_id}, action={self.action})>"
