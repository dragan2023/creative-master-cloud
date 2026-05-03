"""
多Agent协作文学作品生成系统 - 写手Agent 提示词模块

从 writer_agent.py 拆分，包含所有提示词构建方法。

@date: 2026-04-24
@version: v2.0.0
"""

from typing import Dict, Any, List

from app.agents.writing.base_agent import AgentContext


class WriterPromptsMixin:
    """写手Agent提示词构建 Mixin"""

    def _build_direct_writer_system_prompt(self, context: AgentContext) -> str:
        """构建整章生成模式的系统提示词

        增强版：根据内容类型（小说/剧本）选择不同的提示词，添加人物状态一致性提示。
        v2: 集成文风知识库，支持精细化风格注入。

        Args:
            context: 执行上下文

        Returns:
            系统提示词
        """
        # 获取内容类型
        content_type = context.config.get("content_type", "novel")

        # 使用专门的提示词获取函数，根据内容类型返回不同的系统提示词
        from app.agents.writing.prompts.character_state_prompts import get_writer_system_prompt
        base_prompt = get_writer_system_prompt(content_type)

        # 优先使用文风知识库风格指南（新增）
        style_library_guide = context.style_guide.get(
            "style_library_guide", {}) if context.style_guide else {}
        if style_library_guide:
            from app.tools.style_library import format_style_for_prompt
            style_section = format_style_for_prompt(style_library_guide)
            if style_section:
                base_prompt += "\n\n## 文风要求（**必须严格遵循**）\n\n"
                base_prompt += style_section
                base_prompt += "\n\n请在整个创作过程中始终保持上述文风特征，让读者能清晰感受到风格的独特性。\n"

        # 兼容旧版风格指南（简单文字描述）
        elif context.style_guide:
            style_guide = context.style_guide
            writing_style = style_guide.get("writing_style", "")
            tone = style_guide.get("tone", "")
            forbidden_words = style_guide.get("forbidden_words", [])

            if writing_style or tone:
                base_prompt += "\n## 风格要求\n\n"
                if writing_style:
                    base_prompt += f"**文风**：{writing_style}\n\n"
                if tone:
                    base_prompt += f"**基调**：{tone}\n\n"
                if forbidden_words:
                    base_prompt += f"**禁用词汇**：{', '.join(forbidden_words)}\n\n"

        if context.world_settings:
            base_prompt += "\n## 世界观提示\n\n"
            base_prompt += "创作时请注意以下世界观设定，确保内容符合设定：\n"
            base_prompt += "时间背景、地点特征、社会环境、特殊规则等要保持一致。\n\n"

        return base_prompt

    def _build_direct_writer_user_prompt(
        self,
        unit_title: str,
        unit_summary: str,
        previous_content: str,
        global_context: str,
        target_words: int,
        context: AgentContext = None
    ) -> str:
        """构建整章生成模式的用户提示词

        架构优化版：基于全局大纲+单元概述直接生成，增强前文参考机制。
        新增：集成风格文档特征，确保写作风格一致性。

        Args:
            unit_title: 单元标题
            unit_summary: 单元摘要（单元概述）
            previous_content: 前文内容
            global_context: 全局上下文（包含全局大纲信息）
            target_words: 目标字数
            context: 执行上下文（用于获取人物状态信息和风格文档特征）

        Returns:
            用户提示词
        """
        prompt_parts = []

        # 1. 故事背景（全局大纲）- 权重最高
        if global_context:
            prompt_parts.append("【全局故事背景（核心参考）】")
            prompt_parts.append("以下是整个故事的全局背景和主线设定，请务必遵循：")
            prompt_parts.append(f"{global_context}")
            prompt_parts.append("")

        # 2. 风格文档特征（如有上传）- 新增
        style_document_features = ""
        if context:
            # 从 context.config 中获取风格文档特征
            style_document_features = context.config.get(
                "style_document_features", "")
            if not style_document_features:
                # 兼容：也从 extra 中获取
                style_document_features = context.extra.get(
                    "style_document_features", "")

        if style_document_features:
            prompt_parts.append("【风格文档特征（重要：请遵循此风格）】")
            prompt_parts.append("以下是上传的风格文档分析结果，请在创作时严格遵循此风格特征：")
            prompt_parts.append(
                style_document_features[:2000])  # 限制长度避免超出token
            prompt_parts.append("")

        # 3. 本章信息（单元概述）- 核心指导
        prompt_parts.append("【本章创作指南（单元概述）】")
        prompt_parts.append(f"标题：{unit_title}")
        if unit_summary:
            prompt_parts.append(f"\n内容概要：\n{unit_summary}")
            prompt_parts.append("\n请以上述单元概述为核心指导进行创作，确保情节发展与全局主线一致。")
        prompt_parts.append("")

        # 4. 人物状态追踪信息
        if context:
            # 🆕 [知识图谱优化 v3.1] 使用合并后的完整知识图谱上下文
            # 包含: 人物状态 + 扩展实体 (设施、事件、群体、道具、伏笔、规则)
            knowledge_graph_context = context.extra.get(
                "knowledge_graph_context", "")
            if knowledge_graph_context:
                prompt_parts.append("【前文知识图谱参考（架构优化v3.1）】")
                prompt_parts.append("以下是从前文内容中提取的完整知识信息，包括人物状态、扩展实体等，请参考以保持连贯性：")
                prompt_parts.append(knowledge_graph_context)
                prompt_parts.append("")

            if context.character_state_snapshot:
                prompt_parts.append("【人物状态追踪（重要：请确保一致性）】")
                prompt_parts.append(context.character_state_snapshot)
                prompt_parts.append("")

            if context.relationship_summary and context.relationship_summary != "暂无人物关系变化记录":
                prompt_parts.append("【人物关系链】")
                prompt_parts.append(context.relationship_summary)
                prompt_parts.append("")

            if context.character_location_map:
                prompt_parts.append("【人物当前位置】")
                for char_name, char_location in context.character_location_map.items():
                    if char_location:
                        prompt_parts.append(f"  {char_name}: {char_location}")
                prompt_parts.append("")

            if context.character_identity_map:
                prompt_parts.append("【人物身份/官职】")
                for char_name, char_identity in context.character_identity_map.items():
                    if char_identity:
                        prompt_parts.append(f"  {char_name}: {char_identity}")
                prompt_parts.append("")

            # 🆕 [知识图谱优化 v3.1] 移除重复的 extended_consistency_context
            # 已合并到 knowledge_graph_context 中,避免提示词冗余
            # extended_consistency_context = context.extra.get("extended_consistency_context", "")
            # if extended_consistency_context:
            #     prompt_parts.append("【扩展实体一致性参考（重要）】")
            #     prompt_parts.append("以下是从知识图谱中提取的扩展实体状态，请确保内容与之保持一致：")
            #     prompt_parts.append(extended_consistency_context)
            #     prompt_parts.append("")

        # 5. 前文内容参考（增强滑动窗口）
        if previous_content:
            # 扩展前文参考长度到3000字，增强连贯性
            prev_excerpt = previous_content[-3000:] if len(
                previous_content) > 3000 else previous_content
            prompt_parts.append(f"【前文内容（最后部分，请紧密衔接）】")
            prompt_parts.append("..." + prev_excerpt)
            prompt_parts.append("")
            prompt_parts.append("【衔接要求】")
            prompt_parts.append("1. 内容开头要自然承接前文，不要出现剧情跳跃")
            prompt_parts.append("2. 保持人物性格、位置、身份与前文一致")
            prompt_parts.append("3. 延续前文的情感基调和叙事节奏")
            prompt_parts.append("")

        # 6. 字数/时长要求（根据内容类型区分）
        content_type = context.config.get(
            "content_type", "novel") if context else "novel"
        if content_type in ("script", "series_script", "movie_script"):
            # 剧本类型使用时长约束
            duration_minutes = context.config.get(
                "duration_minutes", 5) if context else 5
            prompt_parts.append(f"【时长要求】")
            prompt_parts.append(
                f"预计时长：约{duration_minutes}分钟（短剧剧本按1分钟≈150-200字估算）")
            prompt_parts.append("")
        else:
            prompt_parts.append(f"【字数要求】")
            prompt_parts.append(f"目标字数：{target_words}字（误差不超过±10%）")
            prompt_parts.append("")

        # 7. 创作要求
        prompt_parts.append("""【创作要求】
1. 直接输出正文内容，不要包含章节标题等标记
2. 内容要充实，有完整的故事情节，符合全局主线发展
3. 场景描写要生动，对话要自然
4. 注意节奏把控，有张有弛
5. 章节末尾设置适当的悬念或收束
6. 严格控制字数，不要超出或不足太多
7. **核心要求**：
   - 确保人物位置、身份、关系与状态追踪信息一致
   - 剧情发展不脱离全局故事背景设定的主线
   - 与前文内容紧密衔接，避免剧情跳脱

现在请开始创作整章内容：""")

        return "\n".join(prompt_parts)

    def _build_writer_system_prompt(self, context: AgentContext) -> str:
        """构建写手Agent的系统提示词

        增强版：根据内容类型（小说/剧本）选择不同的提示词，添加人物状态一致性提示。

        Args:
            context: 执行上下文

        Returns:
            系统提示词
        """
        # 获取内容类型
        content_type = context.config.get("content_type", "novel")

        # 使用专门的提示词获取函数，根据内容类型返回不同的系统提示词
        from app.agents.writing.prompts.character_state_prompts import get_writer_system_prompt
        base_prompt = get_writer_system_prompt(content_type)

        # 优先使用文风知识库风格指南（新增）
        style_library_guide = context.style_guide.get(
            "style_library_guide", {}) if context.style_guide else {}
        if style_library_guide:
            from app.tools.style_library import format_style_for_prompt
            style_section = format_style_for_prompt(style_library_guide)
            if style_section:
                base_prompt += "\n\n## 文风要求（**必须严格遵循**）\n\n"
                base_prompt += style_section
                base_prompt += "\n\n请在整个创作过程中始终保持上述文风特征，让读者能清晰感受到风格的独特性。\n"

        # 兼容旧版风格指南（简单文字描述）
        elif context.style_guide:
            style_guide = context.style_guide
            writing_style = style_guide.get("writing_style", "")
            tone = style_guide.get("tone", "")
            forbidden_words = style_guide.get("forbidden_words", [])

            if writing_style or tone:
                base_prompt += "\n## 风格要求\n\n"
                if writing_style:
                    base_prompt += f"**文风**：{writing_style}\n\n"
                if tone:
                    base_prompt += f"**基调**：{tone}\n\n"
                if forbidden_words:
                    base_prompt += f"**禁用词汇**：{', '.join(forbidden_words)}\n\n"

        if context.world_settings:
            base_prompt += "\n## 世界观提示\n\n"
            base_prompt += "创作时请注意以下世界观设定，确保内容符合设定：\n"
            base_prompt += "时间背景、地点特征、社会环境、特殊规则等要保持一致。\n\n"

        return base_prompt

    def _build_writer_user_prompt(
        self,
        scene_outline: Dict[str, Any],
        previous_content: str,
        global_context: str,
        context: AgentContext = None
    ) -> str:
        """构建用户提示词

        增强版：添加人物状态追踪信息，确保写作时遵循人物当前状态。

        Args:
            scene_outline: 场景大纲
            previous_content: 前文内容
            global_context: 全局上下文
            context: 执行上下文（用于获取人物状态信息）

        Returns:
            用户提示词
        """
        title = scene_outline.get("title", "")
        location = scene_outline.get("location", "")
        characters = scene_outline.get("characters", [])
        events = scene_outline.get("events", "")
        mood = scene_outline.get("mood", "")
        target_words = scene_outline.get("target_words", 800)
        key_points = scene_outline.get("key_points", [])
        conflict = scene_outline.get("conflict", "")
        ending_hook = scene_outline.get("ending_hook", "")

        prompt_parts = []

        if global_context:
            prompt_parts.append(f"【故事背景】\n{global_context}\n")

        prompt_parts.append(f"【当前场景】\n标题：{title}")
        if location:
            prompt_parts.append(f"地点：{location}")
        if characters:
            prompt_parts.append(f"出场人物：{', '.join(characters)}")
        if mood:
            prompt_parts.append(f"情绪基调：{mood}")
        prompt_parts.append("")

        if events:
            prompt_parts.append(f"【场景内容】\n{events}\n")

        if key_points:
            prompt_parts.append("【关键情节点】")
            for i, point in enumerate(key_points, 1):
                prompt_parts.append(f"{i}. {point}")
            prompt_parts.append("")

        if conflict:
            prompt_parts.append(f"【核心冲突】\n{conflict}\n")

        if context:
            if context.character_state_snapshot:
                prompt_parts.append("【人物状态追踪（重要：请确保一致性）】")
                prompt_parts.append(context.character_state_snapshot)
                prompt_parts.append("")

            if context.relationship_summary and context.relationship_summary != "暂无人物关系变化记录":
                prompt_parts.append("【人物关系链】")
                prompt_parts.append(context.relationship_summary)
                prompt_parts.append("")

            if context.character_location_map:
                prompt_parts.append("【人物当前位置】")
                for char_name, char_location in context.character_location_map.items():
                    if char_location:
                        prompt_parts.append(f"  {char_name}: {char_location}")
                prompt_parts.append("")

            if context.character_identity_map:
                prompt_parts.append("【人物身份/官职】")
                for char_name, char_identity in context.character_identity_map.items():
                    if char_identity:
                        prompt_parts.append(f"  {char_name}: {char_identity}")
                prompt_parts.append("")

            knowledge_graph_states = context.extra.get(
                "knowledge_graph_states", "") if context.extra else ""
            if knowledge_graph_states:
                prompt_parts.append("【知识图谱人物状态】")
                prompt_parts.append(knowledge_graph_states)
                prompt_parts.append("")

        if previous_content:
            prev_excerpt = previous_content[-2000:] if len(
                previous_content) > 2000 else previous_content
            prompt_parts.append(f"【前文内容（最后部分）】\n...{prev_excerpt}\n")
            prompt_parts.append("请在内容开头注意与前文自然衔接，并保持人物性格与前文一致。\n")

        if ending_hook:
            prompt_parts.append(f"【结尾要求】\n{ending_hook}\n")

        prompt_parts.append(f"【字数要求】\n目标字数：{target_words}字（误差不超过±10%）\n")

        prompt_parts.append("""【创作要求】
1. 直接输出正文内容，不要包含标题、章节号等标记
2. 内容要充实，避免空洞描写
3. 对话要自然，符合人物性格
4. 注意细节描写，增强画面感
5. 场景末尾设置悬念或转折，为下一场景铺垫
6. 严格控制字数，不要超出或不足太多
7. **重要**：确保人物位置、身份、关系与上述状态追踪信息一致

现在请开始创作：""")

        return "\n".join(prompt_parts)
