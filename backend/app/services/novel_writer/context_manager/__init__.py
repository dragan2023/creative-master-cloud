"""
上下文窗口管理器
管理章节生成时的上下文构建，包括滑动窗口、摘要压缩等
支持知识库三层检索、GraphRAG增强、内容规则应用

从原始 context_manager.py (1979行) 拆分为以下Mixin模块：
- _compression.py: 语义压缩/截断
- _chapter_data.py: 章节数据获取（摘要/角色/近章/大纲元信息/单元摘要）
- _retrieval.py: 向量检索与知识库
- _outline_extraction.py: 大纲提取与剧本/电影上下文构建
- _compat.py: 兼容导入

@date: 2026-04-24
@version: v3.1.0 (从context_manager.py拆分)
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import asyncio
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models import NovelProject
from app.services.novel_writer.vector_store import ProjectVectorStore
from app.services.proofread.document_formatter import DocumentFormatter
from app.services.novel_writer.semantic_compressor import SemanticCompressor

from ._compression import CompressionMixin
from ._chapter_data import ChapterDataMixin
from ._retrieval import RetrievalMixin
from ._outline_extraction import OutlineExtractionMixin


class ContextWindowManager(
    CompressionMixin,
    ChapterDataMixin,
    RetrievalMixin,
    OutlineExtractionMixin,
):
    """上下文窗口管理器

    负责构建章节生成时的上下文，包括：
    1. 前文摘要（压缩后）
    2. 角色状态
    3. 最近N章内容（滑动窗口）
    4. 当前章节元数据
    5. 向量检索相关内容
    6. 知识库内容
    """

    def __init__(
        self,
        db: AsyncSession,
        max_context_tokens: int = 8192,
        recent_chapters_count: int = 5,
        summary_max_chars: int = 8000,
        vector_retrieve_k: int = 5
    ):
        self.db = db
        self.max_context_tokens = max_context_tokens
        self.recent_chapters_count = recent_chapters_count
        self.summary_max_chars = summary_max_chars
        self.vector_retrieve_k = vector_retrieve_k
        self.logger = get_logger("context_manager")
        self.vector_store = ProjectVectorStore()
        # 初始化文档格式化器
        self.formatter = DocumentFormatter(content_type="novel")
        # 上下文压缩配置 - 分级语义压缩机制
        self.compression_threshold = 10000  # 超过10000字符时触发压缩
        self.target_compressed_length = 8000  # 压缩目标长度
        self.semantic_compressor: SemanticCompressor = None  # 延迟初始化，需要llm_provider

    def set_llm_provider(self, llm_provider):
        """设置LLM提供者并初始化语义压缩器"""
        self.semantic_compressor = SemanticCompressor(
            llm_provider=llm_provider,
            max_context_chars=self.max_context_tokens * 2,  # 粗估：1 token ~ 2 字符
            compression_threshold=self.compression_threshold
        )
        self.logger.info("语义压缩器已初始化")

    async def build_chapter_context(
        self,
        project: NovelProject,
        chapter_num: int,
        chapter_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建章节生成上下文（并行化优化版）

        将10步串行IO改为asyncio.gather并行执行：
        - 第一组：独立的IO操作并行执行（摘要/角色/近章/向量/知识库/大纲元信息）
        - 第二组：依赖第一组结果的后续操作（单元摘要/当前大纲/剧集大纲）
        - 第三组：上下文压缩
        """
        context = {
            "global_summary": "",
            "character_state": "",
            "short_summary": "",
            "previous_scene_ending": "",
            "knowledge_context": "",
            "vector_context": "",
            "outline_metadata": "",
            "current_unit_outline": "",
            "episode_outline": "",
            "previous_episodes_summary": "",
            "previous_content_summaries": "",
            "previous_outline_summaries": "",
            "unit_outline_summary": "",
            "chapter_detailed_outline": ""
        }

        try:
            # ========== 第一组：独立的IO操作并行执行 ==========
            results = await asyncio.gather(
                self._get_summary(project),
                self._get_character_state(project),
                self._get_recent_chapters(project, chapter_num),
                self._get_vector_context(project, chapter_metadata, chapter_num),
                self._get_knowledge_context(project, chapter_metadata),
                self._get_outline_metadata(project),
                return_exceptions=True
            )

            # 处理并行结果，异常项降级为空字符串/空字典
            context["global_summary"] = (
                results[0] if not isinstance(results[0], Exception) else ""
            )
            context["character_state"] = (
                results[1] if not isinstance(results[1], Exception) else ""
            )
            recent_context = (
                results[2] if not isinstance(results[2], Exception) else {
                    "endings": "", "summary": ""}
            )
            context["previous_scene_ending"] = recent_context.get("endings", "")
            context["short_summary"] = recent_context.get("summary", "")
            context["vector_context"] = (
                results[3] if not isinstance(results[3], Exception) else ""
            )
            context["knowledge_context"] = (
                results[4] if not isinstance(results[4], Exception) else ""
            )
            context["outline_metadata"] = (
                results[5] if not isinstance(results[5], Exception) else ""
            )

            # 记录并行执行中的异常
            names = ["前文摘要", "角色状态", "近章内容", "向量检索", "知识库", "大纲元信息"]
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(
                        f"并行获取{names[i] if i < len(names) else '未知'}失败: {result}"
                    )

            # ========== 第二组：依赖第一组结果的后续操作 ==========
            content_type = getattr(project, 'content_type', 'novel')
            unit_summaries = await self._build_unit_summaries(project, chapter_num, content_type, chapter_metadata)
            context["previous_content_summaries"] = unit_summaries.get("previous_content_summaries", "")
            context["previous_outline_summaries"] = unit_summaries.get("previous_outline_summaries", "")
            context["unit_outline_summary"] = unit_summaries.get("unit_outline_summary", "")

            context["current_unit_outline"] = await self._get_current_unit_outline(
                project, chapter_num, chapter_metadata
            )

            if content_type in ('series_script', 'script'):
                episode_num = chapter_metadata.get('episode_number', 1)
                context["episode_outline"] = await self._get_episode_outline(
                    project, episode_num
                )
                context["previous_episodes_summary"] = await self._get_previous_episodes_summary(
                    project, episode_num
                )

            # ========== 第三组：上下文压缩 ==========
            context = await self._compress_context(context)

            return context

        except Exception as e:
            self.logger.error(f"构建章节上下文失败: {str(e)}")
            return context
