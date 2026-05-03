"""
生成记录模型
记录用户的创意生成历史
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class GenerationModule(str, enum.Enum):
    """生成模块枚举"""
    SHORT_VIDEO = "short_video"       # 短视频脚本
    SCRIPT = "script"                 # [DEPRECATED] 剧本大纲已移除，保留用于数据库兼容
    NOVEL = "novel"                   # 小说大纲
    PRINT_AD = "print_ad"             # 平面广告
    TVC = "tvc"                       # TVC广告脚本
    ORIGINAL_IP = "original_ip"       # 原创IP计划
    MOVIE_OUTLINE = "movie_outline"   # 电影大纲
    SERIES_OUTLINE = "series_outline" # 剧集大纲


class GenerationStatus(str, enum.Enum):
    """生成状态枚举"""
    PENDING = "pending"     # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


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

    # 修订相关字段
    is_finalized = Column(Boolean, default=False, comment="是否已最终确认")
    revision_count = Column(Integer, default=0, comment="修订轮次总数")

    # 通用状态持久化字段(适用于所有模块)
    current_stage = Column(String(50), nullable=True,
                           comment="当前生成阶段标识(由各模块自定义)")
    stage_data = Column(JSON, nullable=True, comment="各阶段的完整状态数据(JSON格式)")
    session_context = Column(JSON, nullable=True, comment="会话上下文(修订历史、对话记录等)")

    # 关联关系
    user = relationship("User", back_populates="generations")
    revision_history = relationship(
        "GenerationRevisionHistory", back_populates="generation", cascade="all, delete-orphan")

    # ==================== 业务方法 ====================

    def is_completed(self) -> bool:
        """检查生成是否已完成"""
        return self.status == GenerationStatus.COMPLETED

    def is_failed(self) -> bool:
        """检查生成是否已失败"""
        return self.status == GenerationStatus.FAILED

    def is_processing(self) -> bool:
        """检查生成是否处理中"""
        return self.status == GenerationStatus.PROCESSING

    def can_delete(self) -> bool:
        """检查是否能删除（已完成或已失败时可删除）"""
        return self.status in (GenerationStatus.COMPLETED, GenerationStatus.FAILED)

    def get_duration_seconds(self) -> float:
        """获取执行时间（秒）"""
        return self.duration_ms / 1000.0 if self.duration_ms else 0.0

    def mark_completed(
        self,
        output_content: str,
        provider: str,
        model_name: str,
        token_count: int = 0,
        duration_ms: int = 0
    ) -> None:
        """标记为已完成"""
        self.status = GenerationStatus.COMPLETED
        self.output_content = output_content
        self.provider = provider
        self.model_name = model_name
        self.token_count = token_count
        self.duration_ms = duration_ms

    def mark_failed(self, error_message: str) -> None:
        """标记为已失败"""
        self.status = GenerationStatus.FAILED
        self.error_message = error_message

    def __repr__(self):
        return f"<Generation(id={self.id}, module={self.module}, status={self.status})>"


class GenerationRevisionHistory(BaseModel):
    """创意生成修订历史表"""
    __tablename__ = "generation_revision_history"

    generation_id = Column(Integer, ForeignKey(
        "generations.id", ondelete="CASCADE"), nullable=False, index=True, comment="生成记录ID")
    round_number = Column(Integer, nullable=False, comment="修订轮次(从1开始)")
    user_feedback = Column(Text, nullable=False, comment="用户修改意见")
    diff_instructions = Column(
        Text, nullable=True, comment="LLM输出的差异指令(JSON格式)")
    content_before = Column(Text, nullable=True, comment="修订前完整内容")
    content_after = Column(Text, nullable=True, comment="修订后完整内容")
    token_usage = Column(Integer, default=0, comment="该轮token消耗")

    # 关联关系
    generation = relationship("Generation", back_populates="revision_history")

    def __repr__(self):
        return f"<GenerationRevisionHistory(id={self.id}, generation_id={self.generation_id}, round={self.round_number})>"
