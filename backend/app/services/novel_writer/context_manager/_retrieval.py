"""
上下文窗口管理器 - 检索Mixin

提供向量检索与知识库检索功能。

@date: 2026-04-24
@version: v3.1.0 (从context_manager.py拆分)
"""
from typing import Dict, Any, List


class RetrievalMixin:
    """向量检索与知识库Mixin"""

    async def _get_vector_context(
        self,
        project,
        chapter_metadata: Dict[str, Any],
        current_chapter_num: int = 1
    ) -> str:
        """从项目向量库检索相关内容"""
        if not project.vectorstore_path:
            return ""

        try:
            # 构建检索查询
            query = self._build_vector_query(chapter_metadata)

            # 检索
            results = await self.vector_store.retrieve(
                collection_name=f"project_{project.id}",
                query=query,
                n_results=self.vector_retrieve_k
            )

            if results:
                return self._format_vector_results(results, current_chapter_num)
            return ""

        except Exception as e:
            self.logger.warning(f"向量检索失败: {str(e)}")
            return ""

    def _build_vector_query(self, chapter_metadata: Dict[str, Any]) -> str:
        """构建向量检索查询"""
        parts = []

        # 章节摘要
        if chapter_metadata.get("chapter_summary"):
            parts.append(chapter_metadata["chapter_summary"])

        # 伏笔信息
        if chapter_metadata.get("foreshadowing"):
            parts.append(chapter_metadata["foreshadowing"])

        # 章节定位
        if chapter_metadata.get("chapter_role"):
            parts.append(chapter_metadata["chapter_role"])

        return " ".join(parts)

    def _format_vector_results(self, results: List[Dict[str, Any]], current_chapter: int = 1) -> str:
        """格式化向量检索结果（应用时间距离规则）"""
        formatted = []
        for i, result in enumerate(results, 1):  # 不再限制结果数量
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            ref_chapter = metadata.get("chapter_number", 0)

            # 应用时间距离规则 - 不再截断内容
            if isinstance(ref_chapter, int) and ref_chapter > 0:
                distance = current_chapter - ref_chapter
                if distance <= 2:
                    rule_tag = f"[SKIP] 跳过近{distance}章内容"
                elif 3 <= distance <= 5:
                    rule_tag = "[MOD40%] 需修改≥40%"
                else:
                    rule_tag = "[OK] 可引用核心"
                formatted.append(
                    # 完整内容
                    f"[历史参考 {i}] {rule_tag} - 第{ref_chapter}章:\n{content}")
            else:
                formatted.append(
                    f"[历史参考 {i}] 第{ref_chapter}章相关内容:\n{content}")  # 完整内容
        return "\n\n".join(formatted)

    async def _get_knowledge_context(
        self,
        project,
        chapter_metadata: Dict[str, Any]
    ) -> str:
        """获取知识库内容（支持项目专属知识库 + 公共知识库）"""
        from ._compat import _HAS_KNOWLEDGE_INTEGRATION
        if _HAS_KNOWLEDGE_INTEGRATION:
            from ._compat import NovelKnowledgeIntegration

        kb_config = project.knowledge_base_config or {}

        # 构建结果容器
        context_parts = []

        # 1. 检索项目专属知识库（如果已构建）
        if project.kb_status == 'ready':
            try:
                from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
                project_kb = ProjectKnowledgeBase(db=self.db)

                # 获取当前单元号
                unit_number = chapter_metadata.get(
                    'unit_number', chapter_metadata.get('chapter_number', 1))

                # 构建查询文本（使用章节摘要）
                query_text = chapter_metadata.get(
                    'chapter_summary', '') or chapter_metadata.get('chapter_title', '')

                # 检索项目专属知识库
                kb_result = await project_kb.retrieve_for_revision(
                    project_id=project.id,
                    current_unit=unit_number,
                    query_text=query_text,
                    n_results=5
                )

                if kb_result.get('combined_context'):
                    context_parts.append("【项目专属知识库】")
                    context_parts.append(kb_result['combined_context'])
                    self.logger.info(f"项目专属知识库检索成功: project_id={project.id}")
            except Exception as e:
                self.logger.warning(f"项目专属知识库检索失败: {str(e)}")

        # 2. 检索公共知识库（如果配置了且模块可用）
        if _HAS_KNOWLEDGE_INTEGRATION and any([
            kb_config.get("kb_vertical_enabled"),
            kb_config.get("kb_user_specific_enabled"),
            kb_config.get("kb_manual_enabled")
        ]):
            try:
                # 使用知识库集成服务
                kb_integration = NovelKnowledgeIntegration(
                    self.db, project.user_id)

                # 构建章节信息
                chapter_info = self._build_chapter_info(chapter_metadata)

                # 验证并规范化配置
                kb_config_validated = kb_integration.validate_kb_config(
                    kb_config)

                # 检索知识库
                kb_result = await kb_integration.retrieve_knowledge_for_chapter(
                    project=project,
                    chapter_info=chapter_info,
                    kb_config=kb_config_validated
                )

                # 格式化知识库内容
                formatted = kb_integration.format_knowledge_for_prompt(
                    kb_result)
                if formatted:
                    context_parts.append("\n【公共知识库参考】")
                    context_parts.append(formatted)

            except Exception as e:
                self.logger.warning(f"公共知识库检索失败: {str(e)}")

        return "\n".join(context_parts) if context_parts else ""

    def _build_chapter_info(self, chapter_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """构建用于知识库检索的章节信息"""
        return {
            "chapter_summary": chapter_metadata.get("chapter_summary", ""),
            "chapter_role": chapter_metadata.get("chapter_role", ""),
            "chapter_purpose": chapter_metadata.get("chapter_purpose", ""),
            "foreshadowing": chapter_metadata.get("foreshadowing", ""),
            "scene_metadata": chapter_metadata.get("scene_metadata", {})
        }

    def _build_knowledge_query(self, chapter_metadata: Dict[str, Any]) -> str:
        """构建知识库检索查询"""
        parts = []

        if chapter_metadata.get("chapter_summary"):
            parts.append(chapter_metadata["chapter_summary"])
        if chapter_metadata.get("chapter_role"):
            parts.append(f"章节类型: {chapter_metadata['chapter_role']}")
        if chapter_metadata.get("chapter_purpose"):
            parts.append(f"叙事目的: {chapter_metadata['chapter_purpose']}")

        return " ".join(parts)

    def _format_knowledge_contexts(self, kb_contexts: Dict[str, str]) -> str:
        """格式化知识库内容"""
        formatted = []

        if kb_contexts.get("theory"):
            formatted.append(f"【理论知识】\n{kb_contexts['theory']}")
        if kb_contexts.get("case"):
            formatted.append(f"【案例参考】\n{kb_contexts['case']}")
        if kb_contexts.get("user_specific"):
            formatted.append(f"【用户知识】\n{kb_contexts['user_specific']}")
        if kb_contexts.get("manual"):
            formatted.append(f"【官方手册】\n{kb_contexts['manual']}")

        return "\n\n".join(formatted)
