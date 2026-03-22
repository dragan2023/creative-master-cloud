"""
生成记录模型
记录用户的创意生成历史
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class GenerationModule(str, enum.Enum):
    """生成模块枚举"""
    SHORT_VIDEO = "short_video"     # 短视频脚本
    SCRIPT = "script"               # 剧本大纲
    NOVEL = "novel"                 # 小说大纲
    PRINT_AD = "print_ad"           # 平面广告
    TVC = "tvc"                     # TVC广告脚本
    ORIGINAL_IP = "original_ip"     # 原创IP计划


class GenerationStatus(str, enum.Enum):
    """生成状态枚举"""
    PENDING = "pending"     # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"         # 失败


class Generation(BaseModel):
    """生成记录表"""
    __tablename__ = "generations"

    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    module = Column(
        Enum(GenerationModule),
        nullable=False,
        comment="生成模块"
    )
    status = Column(
        Enum(GenerationStatus),
        default=GenerationStatus.PENDING,
        nullable=False,
        comment="生成状态"
    )

    # 输入参数
    input_params = Column(JSON, nullable=True, comment="输入参数")

    # 标题（从input_params中提取）
    title = Column(String(200), nullable=True, comment="生成标题")

    # 输出结果
    output_content = Column(Text, nullable=True, comment="生成内容")

    # 使用的模型
    provider = Column(String(50), nullable=True, comment="LLM 提供商")
    model_name = Column(String(100), nullable=True, comment="使用的模型")

    # 统计信息
    token_count = Column(Integer, default=0, comment="Token 数量")
    duration_ms = Column(Integer, default=0, comment="耗时(毫秒)")

    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 关联关系
    user = relationship("User", back_populates="generations")

    def __repr__(self):
        return f"<Generation(id={self.id}, module={self.module}, status={self.status})>"
