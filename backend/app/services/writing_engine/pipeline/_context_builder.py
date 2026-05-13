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
                    except (json.JSONDecodeError, AttributeError) as e:
                        logger.warning(f"[上下文构建] 大纲JSON解析失败，使用raw_content: {e}")
                        outline = {"raw_content": project.outline_content}

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
                    logger.info(f"[上下文构建] 从大纲JSON提取人物设定: {len(character_profiles)} 个角色")

            # 🔴 Markdown人物小传解析：当JSON提取失败时，尝试从Markdown格式大纲解析
            if not character_profiles and outline.get("raw_content"):
                md_characters = self._extract_characters_from_markdown_outline(
                    outline["raw_content"]
                )
                if md_characters:
                    character_profiles = md_characters
                    logger.info(
                        f"[上下文构建] 从Markdown大纲解析人物小传: {len(character_profiles)} 个角色"
                    )
                    # 持久化到项目记录，使QC质控模块也能读取
                    if project and hasattr(project, 'character_profiles'):
                        project.character_profiles = character_profiles
                        try:
                            await db_session.commit()
                            logger.info(
                                f"[上下文构建] 人物设定已持久化到 project.character_profiles"
                            )
                        except Exception as e:
                            logger.warning(f"[上下文构建] 持久化人物设定失败: {e}")

            # 🔴 正则切片增强：从大纲原始文本中提取每个人物的详细描述段落
            if character_profiles and outline:
                enriched = self._enrich_characters_from_outline_text(
                    character_profiles=character_profiles,
                    outline=outline
                )
                if enriched:
                    character_profiles = enriched
                    logger.info(f"[上下文构建] 正则切片增强人物设定完成: {len(character_profiles)} 个角色")

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

        # Task 1.2/2.2: 提取风格选择器配置
        style_selector_config = None
        if content_type == "series_script":
            style_selector_config = task_config.get("series_style_dimensions")
            if not style_selector_config and project and project.series_script_config:
                ssc = project.series_script_config if isinstance(project.series_script_config, dict) else {}
                style_selector_config = ssc.get("style_selector_config")
        elif content_type == "movie_script":
            style_selector_config = task_config.get("movie_style_dimensions")
            if not style_selector_config and project and project.movie_script_config:
                msc = project.movie_script_config if isinstance(project.movie_script_config, dict) else {}
                style_selector_config = msc.get("style_selector_config")

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

        # Task 1.2: 将风格选择器配置注入 style_guide
        if style_selector_config:
            style_config_section = self._build_style_config_section(style_selector_config)
            if style_config_section:
                existing_guide = style_guide.get("style_library_guide", "")
                style_guide["style_library_guide"] = f"{style_config_section}\n\n{existing_guide}" if existing_guide else style_config_section
                logger.info(f"[上下文构建] 注入风格选择器配置到 style_guide，长度: {len(style_config_section)}")

        if temp_session:
            await db_session.close()

        # Task 1.2: 按内容类型构建专属配置
        type_specific_config = {}
        if content_type == "series_script":
            type_specific_config = {
                "series_type": task_config.get("series_type", "电视剧"),
                "episode_duration_range": task_config.get("episode_duration_range", [30, 45]),
                "scenes_per_episode_range": task_config.get("scenes_per_episode_range", None),
                "script_mode": task_config.get("script_mode", "real"),
                "series_style_dimensions": task_config.get("series_style_dimensions", {}),
                "series_style_names": task_config.get("series_style_names", []),
                "series_style_intensity": task_config.get("series_style_intensity", 0.7),
                "series_style_type": task_config.get("series_style_type", "long"),
            }
        elif content_type == "movie_script":
            type_specific_config = {
                "movie_type": task_config.get("movie_type", "电影"),
                "duration_range": task_config.get("duration_range", [10, 15]),
                "total_scenes": task_config.get("total_scenes", 0),
                "script_mode": task_config.get("script_mode", "real"),
                "movie_style_dimensions": task_config.get("movie_style_dimensions", {}),
                "movie_style_names": task_config.get("movie_style_names", []),
                "movie_style_intensity": task_config.get("movie_style_intensity", 0.7),
            }

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
                **type_specific_config,
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
                        "description": char.get("description", ""),
                        "age": char.get("age", char.get("年龄", "")),
                        "gender": char.get("gender", char.get("性别", ""))
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
                        "description": char.get("description", ""),
                        "age": char.get("age", char.get("年龄", "")),
                        "gender": char.get("gender", char.get("性别", ""))
                    })

        if not characters and outline.get("main_characters"):
            for char in outline.get("main_characters", []):
                if isinstance(char, dict):
                    characters.append({
                        "name": char.get("name", ""),
                        "role": char.get("role", "主角"),
                        "personality": char.get("personality", ""),
                        "background": char.get("background", ""),
                        "description": char.get("description", ""),
                        "age": char.get("age", char.get("年龄", "")),
                        "gender": char.get("gender", char.get("性别", ""))
                    })
                elif isinstance(char, str):
                    characters.append({"name": char, "role": "角色"})

        return characters

    @staticmethod
    def _enrich_characters_from_outline_text(
        character_profiles: list,
        outline: dict
    ) -> list:
        """从大纲原始文本中正则切片提取每个人物的详细描述段落

        当大纲为 JSON 结构化数据时，character_profiles 已包含字段化的人物信息。
        此方法进一步扫描大纲的原始文本内容（如 raw_content 或 JSON 序列化文本），
        查找每个人物名称周围的上下文描述，将其作为「大纲原文参考」补充到 profile 中。

        正则策略：
        - 获取大纲的文本表示（优先 raw_content，其次 JSON 序列化）
        - 对每个人物名称，搜索其在文本中的所有出现位置
        - 提取名称前后各 N 个字符的上下文窗口
        - 合并多个出现位置的上下文，取前 800 字作为原文参考

        Args:
            character_profiles: 已提取的人物设定列表
            outline: 全局大纲字典（可能包含 raw_content 或章节结构）

        Returns:
            增强后的人物设定列表（新增 outline_context 字段）
        """
        import re as _re

        # 获取大纲的文本表示
        outline_text = ""
        if outline.get("raw_content"):
            outline_text = outline.get("raw_content", "")
        else:
            # 尝试 JSON 序列化（确保 ascii 不转义中文）
            try:
                outline_text = json.dumps(outline, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                return character_profiles

        if not outline_text or len(outline_text) < 50:
            return character_profiles

        enriched_profiles = []
        context_window = 400  # 名称前后各取 400 字符

        for char in character_profiles:
            if not isinstance(char, dict):
                enriched_profiles.append(char)
                continue

            name = char.get("name", "")
            if not name or len(name) < 2:
                enriched_profiles.append(char)
                continue

            # 搜索名称在文本中的所有出现位置
            contexts = []
            escaped_name = _re.escape(name)
            pattern = _re.compile(r'(?<!\w)' + escaped_name + r'(?!\w)')

            for match in pattern.finditer(outline_text):
                start = max(0, match.start() - context_window)
                end = min(len(outline_text), match.end() + context_window)
                snippet = outline_text[start:end].strip()
                if len(snippet) > 20:  # 过滤太短的片段
                    contexts.append(snippet)

            if contexts:
                # 合并上下文，取前 800 字符
                merged = " …… ".join(contexts)
                if len(merged) > 800:
                    merged = merged[:800] + "…"

                # 创建增强后的 profile（不修改原对象）
                enriched_char = dict(char)
                existing_desc = enriched_char.get("description", "")
                # 将原文参考追加到 description 或独立字段
                if existing_desc:
                    enriched_char["description"] = (
                        f"{existing_desc}\n\n【大纲原文参考】{merged}"
                    )
                else:
                    enriched_char["description"] = f"【大纲原文参考】{merged}"
                enriched_char["outline_context"] = merged
                enriched_profiles.append(enriched_char)
            else:
                enriched_profiles.append(char)

        return enriched_profiles

    @staticmethod
    def _extract_characters_from_markdown_outline(raw_text: str) -> list:
        """从 Markdown 格式的全局大纲中解析人物小传

        解析策略：
        1. 定位「## 四、人物谱系」章节
        2. 解析 ### 4.1 主角档案：XXX → **字段名**：值
        3. 解析 ### 4.2 反派档案：XXX → **字段名**：值
        4. 解析 ### 4.5 人物小传 → **角色名**\\n\\n+ **字段名**：值
        5. 从「基本信息」中提取性别、年龄；从「性格核心/性格维度」提取性格；
           从「背景故事」提取背景；从「外貌特征」提取外貌；从「核心动机/在故事中的作用」提取动机/身份

        Args:
            raw_text: Markdown 格式的大纲全文

        Returns:
            结构化人物设定列表，每项含 name/age/gender/personality/background/appearance/goals/role/description
        """
        import re as _re

        if not raw_text or len(raw_text) < 100:
            return []

        characters = []
        seen_names = set()

        # ---- 辅助函数：从文本中提取 **字段名**：值 ----
        def _extract_field(text: str, field_names: list) -> str:
            """从 Markdown 文本中提取指定字段的值，多个候选字段名按优先级匹配"""
            for fn in field_names:
                # 匹配 **字段名**：值（值到下一个 ** 或 +++ 或换行+空行为止）
                pattern = _re.compile(
                    r'\*\*' + _re.escape(fn) + r'\*\*[：:]\s*(.+?)(?=\n\n|\n\*\*|\n\+\s+\*\*|\n#{1,6}\s|\Z)',
                    _re.DOTALL
                )
                m = pattern.search(text)
                if m:
                    value = m.group(1).strip()
                    # 去除内部的换行和多余空格
                    value = _re.sub(r'\n+', '；', value)
                    value = _re.sub(r'\s+', ' ', value).strip()
                    # 清理 markdown 列表标记
                    value = _re.sub(r'[+\-]\s+', '', value)
                    value = _re.sub(r'；[+\-]\s+', '；', value)
                    # 截断过长内容
                    if len(value) > 600:
                        value = value[:600] + '…'
                    return value
            return ''

        def _parse_basic_info(text: str, full_text: str = '') -> dict:
            """从「基本信息」字段中提取性别、年龄

            Args:
                text: 角色所在文本块
                full_text: 完整的人物谱系文本（兜底用）
            """
            info = _extract_field(text, ['基本信息'])
            result = {'gender': '', 'age': ''}
            if not info:
                return result
            # 提取性别: 在基本信息前50个字符中搜索「男」或「女」
            search_text = info[:50]
            if '男' in search_text:
                result['gender'] = '男'
            elif '女' in search_text:
                result['gender'] = '女'
            # 兜底：从完整文本块中搜索性别（主角档案可能基本信息不含性别）
            if not result['gender'] and full_text:
                # 搜索外貌特征或前200字符
                search_full = full_text[:200]
                if '男' in search_full:
                    result['gender'] = '男'
                elif '女' in search_full:
                    result['gender'] = '女'
            # 提取年龄: 匹配「出场约X岁」「约X岁」「X岁」等模式
            age_patterns = [
                r'出场约(\d+)岁',
                r'出场约(\d+)\s*岁',
                r'约(\d+)岁',
                r'(\d+)岁',
                r'穿越时约(\d+)岁',
            ]
            for ap in age_patterns:
                am = _re.search(ap, info)
                if am:
                    result['age'] = am.group(1)
                    break
            return result

        # ---- 步骤0：定位人物谱系章节 ----
        # 找到「## 四、人物谱系」或「## 四、」之后到下一个「## 五、」或文末
        char_section_match = _re.search(
            r'##\s*四[、,，]\s*人物谱系.*?(?=\n##\s*五[、,，]|\Z)',
            raw_text, _re.DOTALL
        )
        if not char_section_match:
            # 尝试更宽松的匹配
            char_section_match = _re.search(
                r'##\s*四[、,，].*?(?=\n##\s*五[、,，]|\Z)',
                raw_text, _re.DOTALL
            )
        char_section = char_section_match.group(0) if char_section_match else raw_text

        # ---- 步骤1：解析 4.1 主角档案 ----
        protag_match = _re.search(
            r'###\s*4\.1\s*主角档案[：:]\s*(.+?)(?=\n###\s*4\.2|\n##|\Z)',
            char_section, _re.DOTALL
        )
        if protag_match:
            protag_name = protag_match.group(1).strip()
            protag_text = protag_match.group(0)
            basic = _parse_basic_info(protag_text, full_text=protag_text)
            char = {
                'name': protag_name,
                'age': basic['age'],
                'gender': basic['gender'],
                'personality': _extract_field(protag_text, ['性格维度', '性格核心', '性格特点']),
                'background': _extract_field(protag_text, ['背景故事']),
                'appearance': _extract_field(protag_text, ['外貌特征']),
                'goals': _extract_field(protag_text, ['人物弧光']),
                'role': '主角',
                'description': protag_text[:600],
            }
            if protag_name and protag_name not in seen_names:
                seen_names.add(protag_name)
                characters.append(char)
                logger.debug(f"[Markdown人物解析] 主角: {protag_name}, age={basic['age']}, gender={basic['gender']}")

        # ---- 步骤2：解析 4.2 反派档案 ----
        antag_match = _re.search(
            r'###\s*4\.2\s*反派档案[：:]\s*(.+?)(?=\n###\s*4\.3|\n##|\Z)',
            char_section, _re.DOTALL
        )
        if antag_match:
            antag_name = antag_match.group(1).strip()
            antag_text = antag_match.group(0)
            basic = _parse_basic_info(antag_text, full_text=antag_text)
            char = {
                'name': antag_name,
                'age': basic['age'],
                'gender': basic['gender'],
                'personality': _extract_field(antag_text, ['性格核心', '性格维度']),
                'background': '',
                'appearance': _extract_field(antag_text, ['外貌特征']),
                'goals': _extract_field(antag_text, ['核心动机']),
                'role': _extract_field(antag_text, ['身份定位']),
                'description': antag_text[:600],
            }
            if antag_name and antag_name not in seen_names:
                seen_names.add(antag_name)
                characters.append(char)
                logger.debug(f"[Markdown人物解析] 反派: {antag_name}, age={basic['age']}, gender={basic['gender']}")

        # ---- 步骤3：解析 4.5 人物小传 ----
        # 找到 ### 4.5 人物小传 之后的所有内容（直到下一个 ## 或文末）
        bio_section_match = _re.search(
            r'###\s*4\.5\s*人物小传.*?(?=\n##\s|\Z)',
            char_section, _re.DOTALL
        )
        if bio_section_match:
            bio_section = bio_section_match.group(0)
            # 匹配每个角色块: **角色名** 后跟 + **字段名**：值 的行
            # 角色块以 **名字** 开头（名字后可能紧跟换行），随后是连续的 + **字段** 行
            char_blocks = _re.split(
                r'\n(?=\*\*[^*\n]{2,20}\*\*\s*\n)',
                bio_section
            )
            for block in char_blocks:
                # 提取角色名: 开头的 **Name**
                name_match = _re.match(r'\*\*([^*\n]+)\*\*', block)
                if not name_match:
                    continue
                char_name = name_match.group(1).strip()
                # 过滤掉非人名的标题（如「关系性质」）
                if not char_name or len(char_name) < 2 or char_name in ('关系性质', '播州核心人物小传', '外部势力人物小传'):
                    continue
                if char_name in seen_names:
                    continue

                basic = _parse_basic_info(block, full_text=char_section)
                personality = _extract_field(block, ['性格核心', '性格维度', '性格特点'])
                background = _extract_field(block, ['背景故事'])
                appearance = _extract_field(block, ['外貌特征'])
                goals = _extract_field(block, ['核心动机', '在故事中的作用'])
                role = _extract_field(block, ['身份定位', '在故事中的作用'])
                relationship = _extract_field(block, ['与主角的关系'])

                # 构建 description: 合并关系、作用、台词等次要字段
                desc_parts = []
                if relationship:
                    desc_parts.append(f"【与主角关系】{relationship}")
                key_lines = _extract_field(block, ['关键台词'])
                if key_lines:
                    desc_parts.append(f"【关键台词】{key_lines}")

                char = {
                    'name': char_name,
                    'age': basic['age'],
                    'gender': basic['gender'],
                    'personality': personality,
                    'background': background,
                    'appearance': appearance,
                    'goals': goals,
                    'role': role,
                    'description': '\n'.join(desc_parts) if desc_parts else block[:500],
                }
                seen_names.add(char_name)
                characters.append(char)
                logger.debug(
                    f"[Markdown人物解析] 配角: {char_name}, "
                    f"age={basic['age']}, gender={basic['gender']}, "
                    f"personality={personality[:40] if personality else 'N/A'}"
                )

        # ---- 步骤4：兜底——从 4.3 表格中提取人名 ----
        if not characters:
            # 解析 Markdown 表格中的人名
            table_rows = _re.findall(
                r'\|\s*\*\*(.+?)\*\*\s*\|',
                char_section
            )
            for row_name in table_rows:
                name = row_name.strip()
                if name and len(name) >= 2 and name not in seen_names:
                    seen_names.add(name)
                    characters.append({'name': name, 'role': '', 'personality': '', 'background': '', 'description': ''})

        logger.info(f"[Markdown人物解析] 共解析出 {len(characters)} 个角色")
        return characters

    @staticmethod
    def _build_style_config_section(config: dict) -> str:
        """Task 1.2: 将风格选择器配置转为提示词可用的文本段落"""
        if not config or not config.get("dimensions"):
            return ""

        intensity = config.get("intensity", 0.7)
        intensity_desc = "淡入-轻微体现" if intensity <= 0.4 else (
            "适中-明显但不突兀" if intensity <= 0.7 else "强烈-非常突出"
        )

        lines = [f"## 用户选择的创作风格（强度: {intensity_desc}）"]
        for dim_name, styles in config["dimensions"].items():
            if styles:
                s = styles[0] if isinstance(styles, list) else styles
                lines.append(
                    f"- **{dim_name}**: {s.get('name', '')} — {s.get('description', '')}"
                )
        return "\n".join(lines)
