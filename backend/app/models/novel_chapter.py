"""
小说/剧本章节模型
存储章节元数据、内容和生成状态
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class ChapterStatus(str, enum.Enum):
    """章节状态枚举"""
    PENDING = "pending"       # 待生成
    DRAFTING = "drafting"     # 草稿生成中
    REVIEWING = "reviewing"   # 审核中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败


class NovelChapter(BaseModel):
    """小说/剧本章节表"""
    __tablename__ = "novel_chapters"

    project_id = Column(Integer, ForeignKey(
        "novel_projects.id", ondelete="CASCADE"), nullable=False, comment="项目ID")

    # 章节信息
    chapter_number = Column(Integer, nullable=False, comment="章节序号")
    chapter_title = Column(String(200), nullable=True, comment="章节标题")

    # 剧本场景编号（剧本专用）
    episode_number = Column(Integer, nullable=True, comment="集数（剧本专用）")
    scene_number = Column(Integer, nullable=True, comment="场景编号（剧本专用）")

    # 章节元数据（从目录解析，用于约束生成）
    chapter_metadata = Column(JSON, nullable=True, comment="章节元数据")
    # chapter_metadata 结构示例:
    # {
    #     "chapter_role": "本章定位（角色/事件/主题）",
    #     "chapter_purpose": "核心作用（推进/转折/揭示）",
    #     "suspense_level": "悬念密度（紧凑/渐进/爆发）",
    #     "foreshadowing": "伏笔操作（埋设A线索→强化B矛盾）",
    #     "plot_twist_level": "认知颠覆强度（★☆☆☆☆）",
    #     "chapter_summary": "本章简述（一句话概括）"
    # }
    #
    # 剧本专用字段:
    # {
    #     "scene_metadata": {
    #         "location": "某咖啡厅",
    #         "interior_exterior": "内",
    #         "time_of_day": "日",
    #         "weather": "晴",
    #         "characters_present": ["张三", "李四"],
    #         "duration_minutes": 5,
    #         "transition": "切至"
    #     }
    # }

    # 生成状态
    status = Column(
        Enum(ChapterStatus),
        default=ChapterStatus.PENDING,
        nullable=False,
        comment="章节状态"
    )
    draft_content = Column(Text, nullable=True, comment="草稿内容")
    final_content = Column(Text, nullable=True, comment="最终内容")

    # 文件路径
    content_file = Column(String(255), nullable=True, comment="章节文件路径")

    # 统计信息
    word_count = Column(Integer, default=0, comment="字数")
    token_count = Column(Integer, default=0, comment="Token消耗")
    duration_ms = Column(Integer, default=0, comment="生成耗时(毫秒)")

    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 用户编辑
    user_edited = Column(Integer, default=0, comment="用户是否编辑过(0/1)")
    edit_history = Column(JSON, nullable=True, comment="编辑历史")

    # 关联关系
    project = relationship("NovelProject", back_populates="chapters")

    def __repr__(self):
        return f"<NovelChapter(id={self.id}, chapter={self.chapter_number}, title='{self.chapter_title}', status={self.status})>"

    def to_dict(self, exclude: list = None) -> dict:
        """转换为字典"""
        exclude = exclude or []
        result = super().to_dict(exclude)
        # 确保枚举值正确转换
        if self.status:
            result["status"] = self.status.value
        return result

    def to_summary_dict(self) -> dict:
        """转换为摘要字典（用于列表展示）"""
        return {
            "id": self.id,
            "chapter_number": self.chapter_number,
            "chapter_title": self.chapter_title,
            "episode_number": self.episode_number,  # 剧本专用：集数
            "scene_number": self.scene_number,  # 剧本专用：场景号
            "status": self.status.value if self.status else None,
            "word_count": self.word_count,
            "has_content": bool(self.final_content),
            "chapter_metadata": self.chapter_metadata,  # 包含合规性检测结果等元数据
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def get_content_preview(self, max_length: int = 200) -> str:
        """获取内容预览"""
        content = self.final_content or self.draft_content or ""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."

    def get_metadata_value(self, key: str, default=None):
        """获取章节元数据值"""
        if not self.chapter_metadata:
            return default
        return self.chapter_metadata.get(key, default)
