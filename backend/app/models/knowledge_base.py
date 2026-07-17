"""
知识库模型
支持临时知识库和静态知识库
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Text, Enum, JSON, DateTime
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class KnowledgeBaseType(str, enum.Enum):
    """知识库类型枚举"""
    TEMP = "temp"       # 临时知识库（用户上传，会话结束后清理）
    STATIC = "static"   # 静态知识库（管理员维护）
    API = "api"         # API数据源（网络数据API）


class KnowledgeBaseStatus(str, enum.Enum):
    """知识库状态枚举"""
    PENDING = "pending"         # 待处理
    PROCESSING = "processing"   # 处理中
    READY = "ready"             # 就绪
    FAILED = "failed"           # 失败


class KnowledgeBaseCategory(str, enum.Enum):
    """知识库业务板块分类

    注意：
    - NOVEL: 项目专属知识库（ProjectKnowledgeBase），用于存储具体项目的人物/情节/世界观，
             完全独立，不参与双轨检索
    - NOVEL_WRITING: 小说写作专业知识库，用于存储写作技巧/方法论/案例分析，
                     参与双轨检索，为创意生成提供理论指导
    """
    SHORT_VIDEO = "short-video"       # 短视频（垂直领域，参与双轨检索）
    SCRIPT = "script"                 # 剧本（垂直领域，参与双轨检索）
    NOVEL = "novel"                   # 【项目专属】正文生成知识库，不参与双轨检索
    NOVEL_WRITING = "novel-writing"   # 小说写作专业知识库（垂直领域，参与双轨检索）
    PRINT_AD = "print-ad"             # 平面广告（垂直领域，参与双轨检索）
    TVC = "tvc"                       # TVC广告（垂直领域，参与双轨检索）
    PRACTICAL_WRITING = "practical-writing"  # 应用文写作（垂直领域，参与双轨检索）
    GENERAL = "general"               # 通用知识库（理论知识库，固定调用）
    USER_SPECIFIC = "user-specific"   # 用户专属知识库（支持GraphRAG，用户选择启用）
    MANUAL = "manual"                 # 官方手册（不使用GraphRAG）


class KnowledgeBase(BaseModel):
    """知识库表"""
    __tablename__ = "knowledge_bases"

    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=True, comment="用户ID（临时知识库）")
    name = Column(String(100), nullable=False, comment="知识库名称")
    description = Column(Text, nullable=True, comment="描述")
    type = Column(
        Enum(KnowledgeBaseType),
        default=KnowledgeBaseType.TEMP,
        nullable=False,
        comment="知识库类型"
    )
    category = Column(
        Enum(KnowledgeBaseCategory),
        default=KnowledgeBaseCategory.GENERAL,
        nullable=False,
        comment="业务板块分类"
    )
    status = Column(
        Enum(KnowledgeBaseStatus),
        default=KnowledgeBaseStatus.PENDING,
        nullable=False,
        comment="状态"
    )

    # 文件信息
    file_path = Column(String(255), nullable=True, comment="原始文件路径")
    file_type = Column(String(20), nullable=True,
                       comment="文件类型 (pdf/docx/txt)")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")

    # 向量库信息
    collection_name = Column(
        String(100), nullable=True, comment="ChromaDB 集合名称")
    document_count = Column(Integer, default=0, comment="文档片段数量")

    # 过期时间（临时知识库）
    expires_at = Column(DateTime, nullable=True, comment="过期时间")

    # 预处理元数据
    preprocessor_metadata = Column(JSON, nullable=True, comment="预处理元数据")
    # preprocessor_metadata 结构示例:
    # {
    #     "preprocessor_enabled": true,
    #     "marker_used": true,
    #     "semantic_chunk_used": true,
    #     "summarization_used": true,
    #     "original_size": 10000,
    #     "filtered_size": 8500,
    #     "chunk_count": 15
    # }

    # API数据源配置（type=api时使用）
    api_config = Column(JSON, nullable=True, comment="API配置信息")
    # api_config 结构示例:
    # {
    #     "endpoint": "https://api.example.com/data",
    #     "method": "GET",
    #     "headers": {},
    #     "params": {},
    #     "auth_type": "bearer/api_key/none",
    #     "auth_value": "",
    #     "schedule": "daily/hourly/manual",
    #     "last_sync": "2024-01-01T00:00:00",
    #     "mapping": {
    #         "data_path": "$.data[*]",
    #         "title_field": "title",
    #         "content_field": "content"
    #     }
    # }

    # 关联关系
    user = relationship("User", back_populates="knowledge_bases")

    # ==================== 业务方法 ====================

    def is_expired(self) -> bool:
        """检查知识库是否已过期（仅临时知识库有过期时间）"""
        from datetime import datetime
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def is_ready_for_use(self) -> bool:
        """检查知识库是否就绪可用"""
        return self.status == KnowledgeBaseStatus.READY and not self.is_expired()

    def is_processing(self) -> bool:
        """检查知识库是否处理中"""
        return self.status == KnowledgeBaseStatus.PROCESSING

    def is_failed(self) -> bool:
        """检查知识库是否处理失败"""
        return self.status == KnowledgeBaseStatus.FAILED

    def mark_ready(self, document_count: int = 0) -> None:
        """标记为就绪"""
        self.status = KnowledgeBaseStatus.READY
        if document_count > 0:
            self.document_count = document_count

    def mark_failed(self) -> None:
        """标记为失败"""
        self.status = KnowledgeBaseStatus.FAILED

    def mark_processing(self) -> None:
        """标记为处理中"""
        self.status = KnowledgeBaseStatus.PROCESSING

    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, name='{self.name}', type={self.type}, category={self.category})>"
