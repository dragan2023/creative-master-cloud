"""
写作流水线 - 上下文构建 Mixin

从 _execute.py 拆分，包含 _build_context 和 _extract_characters_from_outline 方法。

@date: 2026-04-24
@version: v1.0.0
"""
import json
import os
from typing import Any, Optional

from app.agents.writing.base_agent import AgentContext
from app.core.logger import get_logger
from app.models.writing_task import TaskStatus
from ._config import PipelineConfigMixin

logger = get_logger("writing_engine.pipeline")


class ContextBuilderMixin(PipelineConfigMixin):
    """上下文构建 Mixin

    提供 _build_context 方法 - 构建Orchestrator执行上下文。
    """

    db: Optional[Any]
    task: Optional[Any]
    _ws_manager: Optional[Any]
    _stats_interceptor: Optional[Any]
    _orchestrator: Optional[Any]

    _result: Optional[Any]
    _execution_task: Optional[Any]

    async def _build_context(self) -> AgentContext:
        """构建Orchestrator执行上下文"""
        task_config = self.task.config or {}

        project = None
        outline = task_config.get("outline", {})
        character_profiles = task_config.get("character_profiles", [])
        world_settings = task_config.get("world_settings", {})

        from app.models.novel_project import NovelProject
        from sqlalchemy import select
        from app.core.database import async_session_maker

        db_session = self.db
        temp_session = False
        if not db_session:
            db_session = async_session_maker()
            temp_session = True

        if db_session:
            project_result = await db_session.execute(
                select(NovelProject).where(
                    NovelProject.id == self.task.project_id).limit(1)
            )
            project = project_result.scalar_one_or_none()

        if project:
            if not outline or not isinstance(outline, dict) or not outline.get("chapters"):
                if project.outline_content:
                    try:
                        outline_data = json.loads(project.outline_content) if project.outline_content.strip().startswith('{') else {"raw_content": project.outline_content}
                        if outline_data.get("chapters"):
                            outline = outline_data
                            logger.info(f"[上下文构建] 从项目加载大纲，章节数: {len(outline_data.get('chapters', []))}")
                    except (json.JSONDecodeError, AttributeError):
                        pass

            if not task_config.get("unit_summaries") and project.unit_summaries:
                task_config["unit_summaries"] = project.unit_summaries
                logger.info(f"[上下文构建] 从项目加载 unit_summaries，单元数: {len(project.unit_summaries) if isinstance(project.unit_summaries, dict) else 0}")

            if not character_profiles and project.global_outline_graph_path:
                try:
                    from app.tools.novel_graph_rag import NovelKnowledgeGraph
                    graph_path = project.global_outline_graph_path
                    if os.path.exists(graph_path):
                        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
                        if knowledge_graph.load():
                            character_profiles = knowledge_graph.get_character_profiles()
                            logger.info(f"[上下文构建] 从知识图谱加载人物设定: {len(character_profiles)} 个角色")
                            world_settings = knowledge_graph.get_world_settings()
                            logger.info(f"[上下文构建] 从知识图谱加载世界观设定: {len(world_settings.get('rules', []))} 条规则, {len(world_settings.get('locations', []))} 个地点")
                    else:
                        logger.warning(f"[上下文构建] 知识图谱文件不存在: {graph_path}")
                except Exception as e:
                    logger.warning(f"[上下文构建] 加载知识图谱失败: {e}")

            if not character_profiles and outline:
                character_profiles = self._extract_characters_from_outline(outline)
                if character_profiles:
                    logger.info(f"[上下文构建] 从大纲内容提取人物设定: {len(character_profiles)} 个角色")

        words_per_unit = task_config.get("words_per_chapter", 3000)

        content_type = "novel"
        if project and hasattr(project, 'content_type') and project.content_type:
            content_type = project.content_type

        generation_mode = "direct"
        logger.info(f"[上下文构建] 项目类型: {content_type}, 生成模式: {generation_mode} (架构优化版)")

        unit_summaries = task_config.get("unit_summaries", {})
        logger.info(f"[上下文构建] 最终配置: unit_summaries数量={len(unit_summaries)}, outline章节={len(outline.get('chapters', []))}, 人物数={len(character_profiles)}")

        if unit_summaries:
            sample_keys = list(unit_summaries.keys())[:3]
            for key in sample_keys:
                unit_data = unit_summaries.get(key, {})
                logger.debug(f"[上下文构建] 单元{key}: title={unit_data.get('title', 'N/A')}, summary_len={len(unit_data.get('summary', ''))}")

        if character_profiles:
            for char in character_profiles[:3]:
                logger.info(f"[上下文构建] 人物: {char.get('name', '未知')} - {char.get('role', '')} - {char.get('personality', '')[:50]}")

        ai_elimination_enabled = True
        ai_elimination_threshold = 50
        style_document_features = ""

        if project:
            ai_elimination_enabled = project.ai_elimination_enabled if project.ai_elimination_enabled is not None else True
            ai_elimination_threshold = project.ai_elimination_threshold if project.ai_elimination_threshold is not None else 50

            if project.style_config:
                style_config = project.style_config if isinstance(project.style_config, dict) else {}
                style_parts = []

                style_guide_text = style_config.get("style_guide_for_writing", "")
                if style_guide_text:
                    style_parts.append(f"【写作风格指南】\n{style_guide_text}")

                key_points = style_config.get("key_imitation_points", [])
                if key_points:
                    points_text = "\n".join([f"- {p}" for p in key_points])
                    style_parts.append(f"【模仿要点】\n{points_text}")

                style_profile = style_config.get("style_profile", {})
                if style_profile:
                    profile_parts = []
                    vocab = style_profile.get("vocabulary", {})
                    if vocab:
                        word_pref = vocab.get("word_preference", "")
                        sig_words = vocab.get("signature_words", [])
                        if word_pref:
                            profile_parts.append(f"用词偏好: {word_pref}")
                        if sig_words:
                            profile_parts.append(f"标志性词汇: {', '.join(sig_words[:5])}")

                    sentence = style_profile.get("sentence_structure", {})
                    if sentence:
                        avg_len = sentence.get("average_length", "")
                        patterns = sentence.get("preferred_patterns", [])
                        if avg_len:
                            profile_parts.append(f"句式特点: {avg_len}")
                        if patterns:
                            profile_parts.append(f"偏好句式: {'; '.join(patterns[:2])}")

                    narrative = style_profile.get("narrative_style", {})
                    if narrative:
                        perspective = narrative.get("perspective", "")
                        pacing = narrative.get("pacing", "")
                        if perspective:
                            profile_parts.append(f"叙事视角: {perspective}")
                        if pacing:
                            profile_parts.append(f"叙事节奏: {pacing}")

                    dialogue = style_profile.get("dialogue_style", {})
                    if dialogue:
                        dial_style = dialogue.get("overall_style", "")
                        if dial_style:
                            profile_parts.append(f"对话风格: {dial_style}")

                    emotional = style_profile.get("emotional_expression", {})
                    if emotional:
                        tone = emotional.get("tone", "")
                        if tone:
                            profile_parts.append(f"情感基调: {tone}")

                    if profile_parts:
                        style_parts.append(f"【风格画像摘要】\n" + "\n".join(profile_parts))

                examples = style_config.get("example_transformations", [])
                if examples:
                    example_texts = []
                    for i, ex in enumerate(examples[:2], 1):
                        orig = ex.get("original", "")
                        styled = ex.get("styled", "")
                        if orig and styled:
                            example_texts.append(f'示例{i}: "{orig}" → "{styled}"')
                    if example_texts:
                        style_parts.append(f"【风格转换示例】\n" + "\n".join(example_texts))

                avoid_patterns = style_config.get("avoid_patterns", [])
                if avoid_patterns:
                    avoid_text = "\n".join([f"- {p}" for p in avoid_patterns])
                    style_parts.append(f"【应避免的模式】\n{avoid_text}")

                style_document_features = "\n\n".join(style_parts)
                logger.info(f"[上下文构建] 加载完整风格文档特征，长度: {len(style_document_features)}，包含{len(style_parts)}个部分")

            logger.info(f"[上下文构建] AI文风消除: enabled={ai_elimination_enabled}, threshold={ai_elimination_threshold}")

        style_guide = task_config.get("style_guide", {})
        if not isinstance(style_guide, dict):
            style_guide = {}

        if not style_guide.get("style_library_guide") and project:
            style_ids = style_guide.get("writing_styles") or []
            intensity = style_guide.get("style_intensity", 0.7)

            if not style_ids and project.generation_config and isinstance(project.generation_config, dict):
                style_ids = project.generation_config.get("writing_styles", [])
                intensity = project.generation_config.get("style_intensity", 0.7)

            if not style_ids and project.novel_config and isinstance(project.novel_config, dict):
                style_ids = project.novel_config.get("writing_styles", [])
                intensity = project.novel_config.get("style_intensity", 0.7)

            if style_ids:
                try:
                    from app.tools.style_library import build_style_guide
                    rebuilt_guide = build_style_guide(style_ids, intensity)
                    if rebuilt_guide:
                        style_guide["style_library_guide"] = rebuilt_guide
                        logger.info(f"[上下文构建] 兜底重建 style_library_guide, style_ids={style_ids}, intensity={intensity}")
                except Exception as e:
                    logger.warning(f"[上下文构建] 兜底重建 style_library_guide 失败: {e}")

        if temp_session:
            await db_session.close()

        return AgentContext(
            task_id=self.task.uuid,
            unit_index=0,
            project_id=self.task.project_id,
            user_id=self.task.user_id,
            outline=outline,
            previous_content=task_config.get("previous_content", ""),
            global_context=task_config.get("global_context", ""),
            character_profiles=character_profiles,
            world_settings=world_settings,
            style_guide=style_guide,
            config={
                "total_units": self.task.total_units,
                "start_from": self.task.start_from,
                "unit_count": self.task.unit_count,
                "words_per_unit": words_per_unit,
                "max_concurrent_writers": task_config.get("max_concurrent_writers", 3),
                "stop_on_error": task_config.get("stop_on_error", True),
                "unit_summaries": unit_summaries,
                "generation_mode": generation_mode,
                "content_type": content_type,
                "ai_elimination_enabled": ai_elimination_enabled,
                "ai_elimination_threshold": ai_elimination_threshold,
                "style_document_features": style_document_features,
                **task_config.get("agent_config", {})
            }
        )

    def _extract_characters_from_outline(self, outline: dict) -> list:
        """从大纲内容中提取人物设定（备选方案）"""
        characters = []

        if outline.get("characters"):
            for char in outline.get("characters", []):
                if isinstance(char, dict):
                    characters.append({
                        "name": char.get("name", ""),
                        "role": char.get("role", char.get("身份", "")),
                        "personality": char.get("personality", char.get("性格", "")),
                        "background": char.get("background", char.get("背景", "")),
                        "description": char.get("description", "")
                    })
                elif isinstance(char, str):
                    characters.append({"name": char})

        if not characters and outline.get("人物设定"):
            for char in outline.get("人物设定", []):
                if isinstance(char, dict):
                    characters.append({
                        "name": char.get("name", char.get("姓名", "")),
                        "role": char.get("role", char.get("身份", "")),
                        "personality": char.get("personality", char.get("性格", "")),
                        "background": char.get("background", char.get("背景", "")),
                        "description": char.get("description", "")
                    })

        if not characters and outline.get("main_characters"):
            for char in outline.get("main_characters", []):
                if isinstance(char, dict):
                    characters.append({
                        "name": char.get("name", ""),
                        "role": char.get("role", "主角"),
                        "personality": char.get("personality", ""),
                        "background": char.get("background", ""),
                        "description": char.get("description", "")
                    })
                elif isinstance(char, str):
                    characters.append({"name": char, "role": "角色"})

        return characters
