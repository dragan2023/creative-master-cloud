"""
小说/剧本项目模型
存储项目基本信息、生成配置和文件路径
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class ProjectType(str, enum.Enum):
    """项目类型枚举"""
    NOVEL = "novel"     # 小说
    SCRIPT = "script"   # 剧本


class ProjectStatus(str, enum.Enum):
    """项目状态枚举"""
    INIT = "init"               # 初始化（已上传大纲）
    DIRECTORY = "directory"     # 目录生成中
    GENERATING = "generating"   # 正文生成中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    PAUSED = "paused"           # 已暂停


class NovelProject(BaseModel):
    """小说/剧本项目表"""
    __tablename__ = "novel_projects"

    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")

    # 基本信息
    title = Column(String(200), nullable=False, comment="项目标题")
    project_type = Column(
        Enum(ProjectType),
        nullable=False,
        comment="项目类型(novel/script)"
    )
    # 新版内容类型（三种独立类型）
    content_type = Column(String(20), nullable=True,
                          comment="内容类型(novel/series_script/movie_script)")
    genre = Column(String(50), nullable=True, comment="类型标签（言情/悬疑/科幻等）")
    target_platform = Column(String(50), nullable=True, comment="目标平台")

    # 大纲信息（兼容旧版）
    outline_file_path = Column(
        String(255), nullable=True, comment="用户上传的大纲文件路径")
    outline_content = Column(Text, nullable=True, comment="大纲原始内容")

    # ==================== 两阶段大纲生成（新版） ====================
    # 全局大纲（第一阶段生成结果）
    global_outline_content = Column(Text, nullable=True, comment="全局大纲内容（详细版）")
    global_outline_status = Column(
        String(20), default="pending", comment="全局大纲状态(pending/generating/completed)")
    global_outline_created_at = Column(
        String(50), nullable=True, comment="全局大纲生成时间")
    global_outline_file_path = Column(
        String(255), nullable=True, comment="全局大纲文件路径")

    # 单元简要概述（第二阶段生成结果）
    unit_summaries = Column(JSON, nullable=True, comment="单元简要概述")
    # unit_summaries 结构示例:
    # {
    #     "1": {"unit_number": 1, "title": "第1章标题", "summary": "100-200字概要", "status": "completed"},
    #     "2": {"unit_number": 2, "title": "第2章标题", "summary": "...", "status": "pending"},
    #     ...
    # }
    unit_summaries_status = Column(
        String(20), default="pending", comment="单元概述状态(pending/generating/completed)")
    unit_summaries_created_at = Column(
        String(50), nullable=True, comment="单元概述生成时间")
    unit_summaries_file_path = Column(
        String(255), nullable=True, comment="单元概述文件路径")

    # 分集详细大纲（剧本专用，存储各集的详细大纲）
    episode_outlines = Column(JSON, nullable=True, comment="分集详细大纲")
    # episode_outlines 结构示例:
    # {
    #     "1": {
    #         "episode_number": 1,
    #         "episode_title": "第1集标题",
    #         "episode_summary": "200-300字梗概",
    #         "detailed_outline": "500-800字详细大纲",
    #         "estimated_duration": 40,
    #         "scenes": [
    #             {"scene_number": 1, "location": "...", "interior_exterior": "内", ...}
    #         ],
    #         "status": "generated",  # pending/generated/edited
    #         "created_at": "2024-...",
    #         "updated_at": "2024-..."
    #     },
    #     "2": { ... }
    # }

    # 章节详细大纲（小说专用，存储各章的详细大纲）
    chapter_outlines = Column(JSON, nullable=True, comment="章节详细大纲")
    # chapter_outlines 结构示例:
    # {
    #     "1": {
    #         "chapter_number": 1,
    #         "chapter_title": "第1章标题",
    #         "chapter_summary": "200-300字梗概",
    #         "detailed_outline": "500-800字详细大纲",
    #         "key_events": ["事件1", "事件2"],
    #         "character_arcs": "角色发展",
    #         "status": "generated",  # pending/generated/edited
    #         "content_status": "generated",  # 正文生成状态
    #         "created_at": "2024-...",
    #         "updated_at": "2024-..."
    #     },
    #     "2": { ... }
    # }

    # 场景详细大纲（电影剧本专用，存储各场景的详细大纲）
    scene_outlines = Column(JSON, nullable=True, comment="场景详细大纲")
    # scene_outlines 结构示例:
    # {
    #     "1": {
    #         "scene_number": 1,
    #         "scene_title": "场景标题",
    #         "location": "内景 办公室-日",
    #         "scene_summary": "100-200字梗概",
    #         "detailed_outline": "300-500字详细大纲",
    #         "characters": ["张三", "李四"],
    #         "estimated_duration": 3,
    #         "status": "generated",  # pending/generated/edited
    #         "content_status": "generated",  # 正文生成状态
    #         "created_at": "2024-...",
    #         "updated_at": "2024-..."
    #     },
    #     "2": { ... }
    # }

    # 项目状态
    status = Column(
        Enum(ProjectStatus),
        default=ProjectStatus.INIT,
        nullable=False,
        comment="项目状态"
    )
    total_chapters = Column(Integer, default=0, comment="总章节数")
    completed_chapters = Column(Integer, default=0, comment="已完成章节数")
    current_chapter = Column(Integer, default=0, comment="当前生成章节")

    # 生成配置
    generation_config = Column(JSON, nullable=True, comment="生成配置")
    # generation_config 结构示例:
    # {
    #     "provider": "t8star",
    #     "model_name": "deepseek-v3",
    #     "temperature": 0.8,
    #     "words_per_chapter": 3000,
    #     "max_context_tokens": 4096,
    #     "recent_chapters_count": 3,
    #     "summary_max_chars": 2000
    # }

    # 知识库配置
    knowledge_base_config = Column(JSON, nullable=True, comment="知识库配置")
    # knowledge_base_config 结构示例:
    # {
    #     "kb_vertical_enabled": true,
    #     "kb_vertical_ids": [1, 2],
    #     "kb_user_specific_enabled": true,
    #     "kb_user_specific_ids": [3],
    #     "kb_manual_enabled": false,
    #     "kb_manual_ids": [],
    #     "graphrag_enabled": true
    # }

    # 剧本专用配置
    script_config = Column(JSON, nullable=True, comment="剧本专用配置")
    # script_config 结构示例:
    # {
    #     "series_type": "电视剧",          # 电视剧/网络剧/短剧/电影/微电影
    #     "episode_count": 24,              # 总集数
    #     "scenes_per_episode": 15,         # 每集场景数
    #     "avg_scene_duration": 3,          # 平均每场时长(分钟)
    #     "format_style": "标准格式",        # 标准格式/简格式
    #     "dialogue_style": "自然对话",      # 对话风格
    #     "narrative_rhythm": "紧凑"         # 叙事节奏
    # }

    # 新版类型专属配置（三种独立类型，参数完全隔离）
    novel_config = Column(JSON, nullable=True, comment="小说专属配置")
    # novel_config 结构示例:
    # {
    #     "target_platform": "起点中文网",
    #     "words_per_chapter": 3000,
    #     "narrative_perspective": "第三人称",
    #     "tone": "正剧",
    #     "temperature": 0.8
    # }

    series_script_config = Column(JSON, nullable=True, comment="剧集剧本专属配置")
    # series_script_config 结构示例:
    # {
    #     "series_type": "电视剧",
    #     "episode_count": 24,
    #     "episode_duration_range": [30, 45],
    #     "format_standard": "标准格式",
    #     "dialogue_narration_ratio": "均衡",
    #     "script_mode": "real"         # real=现实模式(真人拍摄), virtual=虚拟模式(AI视频生成)
    # }

    movie_script_config = Column(JSON, nullable=True, comment="电影剧本专属配置")
    # movie_script_config 结构示例:
    # {
    #     "movie_type": "院线电影",
    #     "total_duration": 120,
    #     "format_standard": "标准格式",
    #     "dialogue_narration_ratio": "均衡",
    #     "script_mode": "real"         # real=现实模式(真人拍摄), virtual=虚拟模式(AI视频生成)
    # }

    # 项目文件路径（使用特色命名）
    project_code = Column(String(50), unique=True,
                          nullable=True, comment="项目代码（如NW_20260228_a3b7c9）")
    architecture_file = Column(String(255), nullable=True, comment="架构文件路径")
    directory_file = Column(String(255), nullable=True, comment="章节目录文件")
    summary_file = Column(String(255), nullable=True, comment="前文摘要文件")
    characters_file = Column(String(255), nullable=True, comment="角色状态文件")
    vectorstore_path = Column(String(255), nullable=True, comment="向量库路径")
    chapters_dir = Column(String(255), nullable=True, comment="章节文件目录")

    # 统计信息
    total_tokens = Column(Integer, default=0, comment="总Token消耗")
    total_duration_ms = Column(Integer, default=0, comment="总耗时(毫秒)")

    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")

    # ==================== 项目专属知识库配置 ====================
    # 项目专属知识库ID（关联到knowledge_bases表，可选）
    project_kb_id = Column(Integer, nullable=True, comment="项目专属知识库ID")

    # 知识库集合名称（用于向量数据库）
    project_kb_collection = Column(
        String(100), nullable=True, comment="知识库集合名称")

    # 全局大纲图谱文件路径
    global_outline_graph_path = Column(
        String(255), nullable=True, comment="全局大纲图谱文件路径")

    # 人物设定（从大纲中提取的结构化角色信息，供写作提示词和质控模块使用）
    character_profiles = Column(
        JSON, nullable=True, comment="人物设定列表(从大纲提取的结构化角色信息)")

    # 知识库状态
    kb_status = Column(
        String(20),
        default="pending",
        comment="知识库状态(pending/building/ready/failed)"
    )

    # 是否启用GraphRAG
    kb_graphrag_enabled = Column(Boolean, default=True, comment="是否启用GraphRAG")

    # ==================== 合规审核配置 ====================
    # ==================== 风格文档配置 ====================
    # 风格文档相关字段
    style_document_path = Column(String(255), nullable=True, comment="风格文档路径")
    style_document_name = Column(String(200), nullable=True, comment="风格文档名称")
    style_analysis_status = Column(
        String(20), default="pending", comment="风格分析状态(pending/analyzing/completed/failed)")
    style_analysis_error = Column(Text, nullable=True, comment="风格分析错误信息")
    style_config = Column(JSON, nullable=True, comment="风格配置(JSON)")
    # style_config 结构示例:
    # {
    #     "style_profile": {...},           # 风格画像
    #     "style_guide_for_writing": "...",  # 写作风格指南
    #     "key_imitation_points": [...],    # 关键模仿要点
    #     "example_transformations": [...], # 示例转换
    #     "avoid_patterns": [...]           # 避免模式
    # }

    # AI文风消除配置
    ai_elimination_enabled = Column(
        Boolean, default=True, comment="是否启用AI文风消除")
    ai_elimination_threshold = Column(
        Integer, default=50, comment="AI文风消除阈值(0-100)")

    # 合规审核配置
    compliance_config = Column(JSON, nullable=True, comment="合规审核配置")
    # compliance_config 结构示例:
    # {
    #     "enabled": true,                    # 是否启用合规审核
    #     "level": "normal",                  # strict/normal/loose
    #     "platform": "起点中文网",            # 目标平台
    #     "check_categories": [               # 启用的检测类别
    #         "sensitive_words",
    #         "sensitive_locations",
    #         "sensitive_persons",
    #         "sensitive_events"
    #     ]
    # }

    # 知识库构建进度信息
    kb_build_progress = Column(JSON, nullable=True, comment="知识库构建进度")
    # kb_build_progress 结构示例:
    # {
    #     "stage": "extracting_entities",  # 当前阶段
    #     "progress": 50,  # 进度百分比
    #     "message": "正在提取实体...",
    #     "entity_count": 120,
    #     "relation_count": 85,
    #     "started_at": "2024-...",
    #     "updated_at": "2024-..."
    # }

    # 关联关系
    user = relationship("User", back_populates="novel_projects")
    chapters = relationship(
        "NovelChapter", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NovelProject(id={self.id}, title='{self.title}', type={self.project_type}, status={self.status})>"

    def get_progress_percentage(self) -> float:
        """获取生成进度百分比"""
        if self.total_chapters == 0:
            return 0.0
        return (self.completed_chapters / self.total_chapters) * 100

    def to_summary_dict(self) -> dict:
        """转换为摘要字典（用于列表展示）"""
        return {
            "id": self.id,
            "title": self.title,
            "project_type": self.project_type.value if self.project_type else None,
            "genre": self.genre,
            "status": self.status.value if self.status else None,
            "total_chapters": self.total_chapters,
            "completed_chapters": self.completed_chapters,
            "progress_percentage": self.get_progress_percentage(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
