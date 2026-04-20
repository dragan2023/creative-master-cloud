"""
多Agent协作文学作品生成系统 - 写手Agent

模块: agents.writing
文件: writer_agent.py
功能: 根据场景大纲生成文学内容，是多Agent协作系统的核心内容生成器

依赖关系:
    - 依赖: app.agents.writing.base_agent, app.agents.writing.agent_config
    - 被依赖: orchestrator_agent, 写作流水线

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, Optional
import time

from app.agents.writing.base_agent import (
    BaseWritingAgent,
    AgentContext,
    AgentResult,
    AgentRole
)


class WriterAgent(BaseWritingAgent):
    """写手Agent - 核心内容生成器

    根据场景大纲生成文学内容，是整个多Agent协作系统中最重要的内容生产者。

    主要职责：
    1. 根据场景大纲创作文学内容
    2. 与前文自然衔接
    3. 保持角色性格一致性
    4. 达到目标字数要求
    5. 在场景末尾设置钩子/悬念

    特点：
    - 使用较高温度(0.8)增强创意性
    - 提示词设计注重文学性和连贯性
    - 支持流式输出用于实时预览
    """

    agent_name = "写手Agent"
    agent_role = AgentRole.WRITER
    default_model = ""
    default_temperature = 0.8

    async def execute(self, context: AgentContext) -> AgentResult:
        """根据场景大纲生成文学内容

        Args:
            context: Agent执行上下文，包含：
                - context.extra["scene_outline"]: 场景大纲
                    - title: 场景标题
                    - location: 地点
                    - characters: 出场角色列表
                    - events: 事件描述
                    - mood: 情绪基调
                    - target_words: 目标字数
                - context.extra["direct_mode"]: 是否为整章生成模式
                - context.extra["unit_title"]: 整章标题（direct_mode时使用）
                - context.extra["unit_summary"]: 整章摘要（direct_mode时使用）
                - context.previous_content: 前文内容（用于衔接）
                - context.character_profiles: 角色设定
                - context.world_settings: 世界观设定
                - context.style_guide: 风格指南
                - context.global_context: 全局上下文

        Returns:
            AgentResult: 包含生成内容和统计信息
                - content: 生成的文学内容
                - data["summary"]: 场景摘要
                - data["word_count"]: 实际字数
        """
        start_time = time.time()

        try:
            # 检查是否为整章生成模式
            direct_mode = context.extra.get("direct_mode", False)

            if direct_mode:
                # 整章生成模式
                return await self._execute_direct_mode(context, start_time)

            # 场景拆解模式（原有逻辑）
            # 提取场景大纲
            scene_outline = context.extra.get("scene_outline", {})
            if not scene_outline:
                return self._build_error_result("缺少场景大纲数据")

            # 提取场景信息
            scene_title = scene_outline.get("title", "未命名场景")
            location = scene_outline.get("location", "")
            characters = scene_outline.get("characters", [])
            events = scene_outline.get("events", "")
            mood = scene_outline.get("mood", "平静")

            # 字数优先级获取：1. context.config 2. scene_outline 3. 默认值800
            target_words = context.config.get(
                "words_per_scene") or scene_outline.get("target_words") or 800

            self.logger.info(
                f"开始生成场景内容 - 标题: {scene_title}, "
                f"目标字数: {target_words}, 角色: {characters}"
            )

            system_prompt = self._build_writer_system_prompt(context)

            user_prompt = self._build_writer_user_prompt(
                scene_outline=scene_outline,
                previous_content=context.previous_content,
                global_context=context.global_context,
                context=context
            )

            # 调用LLM生成内容（不传递max_tokens，让LLM自主控制输出长度）
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                task_id=context.task_id,
                scene_id=f"{context.unit_index}_{context.scene_index}"
            )

            # 提取结果
            content = response.get("content", "")

            # 清理内容（移除可能的markdown格式）
            content = self._clean_content(content)

            # 计算字数
            word_count = len(content)

            # 生成场景摘要
            summary = await self._generate_summary(content, scene_title)

            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)

            self.logger.info(
                f"场景内容生成完成 - 字数: {word_count}, "
                f"目标: {target_words}, 偏差: {word_count - target_words}"
            )

            return self._build_success_result(
                content=content,
                token_usage={
                    "input_tokens": response.get("input_tokens", 0),
                    "output_tokens": response.get("output_tokens", 0),
                    "total_tokens": response.get("total_tokens", 0)
                },
                duration_ms=duration_ms,
                model_id=response.get("model", self.default_model),
                summary=summary,
                word_count=word_count,
                scene_title=scene_title
            )

        except Exception as e:
            # 使用 {e!r} 避免异常消息中的花括号被误解析为格式化占位符
            self.logger.error(f"写手Agent执行失败: {e!r}", exc_info=True)
            return self._build_error_result(f"内容生成失败: {str(e)[:200]}")

    async def _execute_direct_mode(self, context: AgentContext, start_time: float) -> AgentResult:
        """整章生成模式

        直接根据单元标题和摘要生成整章内容，跳过场景拆解步骤。

        Args:
            context: 执行上下文
            start_time: 开始时间

        Returns:
            AgentResult: 执行结果
        """
        # 提取单元信息
        unit_title = context.extra.get("unit_title", "未命名章节")
        unit_summary = context.extra.get("unit_summary", "")

        # 架构优化：不再使用章节详细大纲，直接基于全局大纲+单元概述生成
        # chapter_detailed_outline 固定为 None

        # 字数配置
        target_words = context.config.get("words_per_scene", 3000)

        self.logger.info(
            f"[整章生成] 开始生成章节内容 - 标题: {unit_title}, "
            f"目标字数: {target_words}, 模式: 全局大纲+单元概述"
        )

        system_prompt = self._build_direct_writer_system_prompt(context)

        user_prompt = self._build_direct_writer_user_prompt(
            unit_title=unit_title,
            unit_summary=unit_summary,
            previous_content=context.previous_content,
            global_context=context.global_context,
            target_words=target_words,
            context=context
        )

        # 调用LLM生成内容
        response = await self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            task_id=context.task_id,
            scene_id=f"{context.unit_index}_direct"
        )

        # 提取结果
        content = response.get("content", "")

        # 清理内容
        content = self._clean_content(content)

        # 计算字数
        word_count = len(content)

        # 生成摘要
        summary = await self._generate_summary(content, unit_title)

        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)

        self.logger.info(
            f"[整章生成] 章节内容生成完成 - 字数: {word_count}, "
            f"目标: {target_words}, 偏差: {word_count - target_words}"
        )

        return self._build_success_result(
            content=content,
            token_usage={
                "input_tokens": response.get("input_tokens", 0),
                "output_tokens": response.get("output_tokens", 0),
                "total_tokens": response.get("total_tokens", 0)
            },
            duration_ms=duration_ms,
            model_id=response.get("model", self.default_model),
            summary=summary,
            word_count=word_count,
            scene_title=unit_title
        )

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
            # 架构优化：添加前文知识图谱参考
            knowledge_graph_context = context.extra.get(
                "knowledge_graph_context", "")
            if knowledge_graph_context:
                prompt_parts.append("【前文知识图谱参考（架构优化）】")
                prompt_parts.append("以下是从前文内容中自动提取的知识图谱信息，请参考以保持连贯性：")
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

            # v3.0.0: 扩展实体一致性上下文
            extended_consistency_context = context.extra.get(
                "extended_consistency_context", "")
            if extended_consistency_context:
                prompt_parts.append("【扩展实体一致性参考（重要）】")
                prompt_parts.append("以下是从知识图谱中提取的扩展实体状态，请确保内容与之保持一致：")
                prompt_parts.append(extended_consistency_context)
                prompt_parts.append("")

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
            # 尝试从配置中获取时长信息
            duration_minutes = context.config.get(
                "duration_minutes", 5) if context else 5
            prompt_parts.append(f"【时长要求】")
            prompt_parts.append(
                f"预计时长：约{duration_minutes}分钟（短剧剧本按1分钟≈150-200字估算）")
            prompt_parts.append("")
        else:
            # 小说类型使用字数约束
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

    def _clean_content(self, content: str) -> str:
        """清理生成的内容

        移除可能的markdown格式和其他多余标记，清理人物状态追踪信息。

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        import re

        # 移除markdown代码块标记
        if content.startswith("```"):
            # 找到第一个换行
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1:]

        if content.endswith("```"):
            content = content[:-3]

        # 移除可能的人物状态追踪信息（这些信息不应该出现在正文中）
        # 匹配模式：【人物状态追踪】或【人物状态快照】等开头的段落块
        patterns_to_remove = [
            r'【人物状态追踪】[\s\S]*?(?=\n【|\n##|$)',
            r'【人物状态快照】[\s\S]*?(?=\n【|\n##|$)',
            r'【人物关系链】[\s\S]*?(?=\n【|\n##|$)',
            r'【人物当前位置】[\s\S]*?(?=\n【|\n##|$)',
            r'【人物身份[\s\S]*?(?=\n【|\n##|$)',
            r'【扩展实体一致性参考[\s\S]*?(?=\n【|\n##|$)',
            r'### 当前人物状态快照[\s\S]*?(?=\n###|\n##|$)',
            r'### 人物关系链[\s\S]*?(?=\n###|\n##|$)',
            r'### 人物当前位置[\s\S]*?(?=\n###|\n##|$)',
            r'### 人物身份[\s\S]*?(?=\n###|\n##|$)',
        ]
        for pattern in patterns_to_remove:
            content = re.sub(pattern, '', content, flags=re.MULTILINE)

        # 移除可能的标题标记
        lines = content.split("\n")
        cleaned_lines = []
        for line in lines:
            # 移除开头的#标题标记
            if line.startswith("#"):
                line = line.lstrip("#").strip()
            cleaned_lines.append(line)

        content = "\n".join(cleaned_lines)

        # 移除首尾空白
        content = content.strip()

        # 清理多余的空行（超过2个连续空行变为2个）
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content

    async def _generate_summary(self, content: str, scene_title: str) -> str:
        """生成场景摘要

        Args:
            content: 场景内容
            scene_title: 场景标题

        Returns:
            场景摘要
        """
        # 如果内容较短，直接返回标题
        if len(content) < 200:
            return f"【{scene_title}】{content[:100]}"

        # 否则取前200字作为摘要
        summary = content[:200]
        # 尝试在句号处截断
        last_period = summary.rfind("。")
        if last_period > 50:
            summary = summary[:last_period + 1]
        else:
            summary = summary + "..."

        return f"【{scene_title}】{summary}"

    async def generate_stream(
        self,
        context: AgentContext
    ):
        """流式生成内容（用于实时预览）

        Args:
            context: 执行上下文

        Yields:
            str: 内容片段
        """
        try:
            # 提取场景大纲
            scene_outline = context.extra.get("scene_outline", {})
            if not scene_outline:
                yield "[错误] 缺少场景大纲数据"
                return

            # 构建提示词
            system_prompt = self._build_writer_system_prompt(context)
            user_prompt = self._build_writer_user_prompt(
                scene_outline=scene_outline,
                previous_content=context.previous_content,
                global_context=context.global_context
            )

            # 流式生成（不传递max_tokens，让LLM自主控制输出长度）
            async for chunk in self.call_llm_stream(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                task_id=context.task_id,
                scene_id=f"{context.unit_index}_{context.scene_index}"
            ):
                yield chunk

        except Exception as e:
            # 使用 {e!r} 避免异常消息中的花括号被误解析
            self.logger.error(f"流式生成失败: {e!r}")
            yield f"\n[错误] 生成中断: {str(e)[:200]}"
