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

        # 7. 输出格式（按内容类型独立化）
        if content_type == "series_script":
            prompt_parts.append(self._build_series_output_format(context))
        elif content_type == "movie_script":
            prompt_parts.append(self._build_movie_output_format(context))
        elif content_type == "script":
            # 兼容旧的统一script类型
            prompt_parts.append(self._build_legacy_script_output_format(context))
        else:
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

    # ==================== Task 4: 剧集/电影独立输出格式 ====================

    def _build_legacy_script_output_format(self, context: AgentContext) -> str:
        """兼容旧的统一script类型的输出格式（向后兼容）"""
        return """【创作要求】
1. 使用标准剧本格式输出
2. 对话简洁有力，动作描述清晰
3. 场景转换流畅
4. 在场景结尾设置适当的钩子或过渡
5. 严格控制时长，不要超出或不足太多
6. **核心要求**：
   - 确保人物位置、身份、关系与状态追踪信息一致
   - 剧情发展不脱离全局故事背景设定的主线
   - 与前文内容紧密衔接，避免剧情跳脱

现在请开始创作剧本内容："""

    def _build_series_output_format(self, context: AgentContext) -> str:
        """Task 4.2: 构建剧集专属输出格式模板

        嵌入剧集风格选择器配置（5维度）和系列参数。
        """
        series_type = context.config.get("series_type", "电视剧")
        duration = context.config.get("episode_duration_range", [30, 45])
        style_dims = context.config.get("series_style_dimensions", {})
        style_names = context.config.get("series_style_names", [])
        style_intensity = context.config.get("series_style_intensity", 0.7)
        script_mode = context.config.get("script_mode", "real")
        scenes_per_episode = context.config.get("scenes_per_episode_range", None)

        style_guidance = self._format_series_style_for_prompt(
            style_dims, style_names, style_intensity)

        parts = []
        parts.append(f"""# 剧集剧本输出格式要求

## 已选剧集风格（强度{int(style_intensity * 100)}%）
{style_guidance}
请在叙事风格、对话特点、场景描述中充分体现上述风格特征。

## 本集信息
- 剧集类型：{series_type}
- 时长控制：{duration[0]}-{duration[1]}分钟""")

        if scenes_per_episode:
            parts.append(f"- 场景数范围：{scenes_per_episode[0]}-{scenes_per_episode[1]}个场景")

        parts.append(f"""
## 输出结构
### 第X集：[标题]
**场景列表**：（标注场景号、日/夜景、室内/室外、地点）
**剧本正文**：（标准剧本格式，含动作描述与对白）

### 拍摄脚本参考
#### 运镜设计
每一场关键场景标注：推/拉/摇/移/跟/升降 + 景别（特写/近景/中景/全景/远景）
#### 光影方案
光源方向、色温（暖/冷/中性）、氛围关键词
#### 演出指导
关键节点的演员表情、肢体动作、台词节奏与停顿建议
#### 剪辑思路
转场方式（切/淡入淡出/叠化/闪回）、本集节奏控制、蒙太奇建议
#### 连续性衔接
本集与上一集的衔接设计、本集结尾为下一集铺设的悬念/过渡

## 创作要求
1. **集间连续性**：本集开头自然承接上一集结尾状态；本集结尾铺设明确的悬念或过渡
2. **场景密度**：每集场景数量合理，情节密度适中
3. **时长控制**：严格遵守{series_type}每集{duration[0]}-{duration[1]}分钟的时长范围
4. **集内结构**：开头（3-5分钟）→ 中段（核心冲突展开）→ 结尾（悬念/收束）
5. **多线叙事**：合理安排主线与支线的交织节奏""")

        if script_mode == "virtual":
            parts.append(self._build_virtual_mode_section("series"))
            parts.append(f"\n> 当前风格参考：{', '.join(style_names) if style_names else '通用剧集风格'}")

        parts.append("\n现在请开始创作本集剧本内容：")
        return "\n".join(parts)

    def _build_movie_output_format(self, context: AgentContext) -> str:
        """Task 4.3: 构建电影专属输出格式模板

        嵌入电影风格选择器配置（6维度，含台词风格）和电影参数。
        """
        movie_type = context.config.get("movie_type", "电影")
        duration = context.config.get("duration_range", [10, 15])
        style_dims = context.config.get("movie_style_dimensions", {})
        style_names = context.config.get("movie_style_names", [])
        style_intensity = context.config.get("movie_style_intensity", 0.7)
        script_mode = context.config.get("script_mode", "real")
        total_scenes = context.config.get("total_scenes", 0)

        style_guidance = self._format_movie_style_for_prompt(
            style_dims, style_names, style_intensity)

        parts = []
        parts.append(f"""# 电影剧本输出格式要求

## 已选电影风格（强度{int(style_intensity * 100)}%）
{style_guidance}
请在叙事风格、台词设计、场景描述中充分体现上述风格特征。

## 本场信息
- 电影类型：{movie_type}
- 时长控制：每场约{duration[0]}-{duration[1]}分钟""")

        if total_scenes > 0:
            parts.append(f"- 总场次数：{total_scenes}场")

        parts.append(f"""
## 场次结构要求（核心）
每场须包含完整的：开场（建立氛围/引入冲突）→ 发展（矛盾升级/角色关系变化）→ 高潮（冲突爆发/关键转折）→ 结局（场景收尾/为下一场铺垫）

## 输出结构
### 第X场：[标题]
**场次结构**：（开场→发展→高潮→结局简述）
**剧本正文**：（标准剧本格式）

### 拍摄脚本参考
#### 运镜设计
标注：景别 + 镜头运动 + 画面描述 + 情感意图
#### 光影方案
光源方向、色温倾向、氛围关键词、色彩基调
#### 演出指导
表情序列设计、肢体动作编排、台词节奏（语速/停顿/重音）
#### 剪辑思路
转场方式、本场节奏曲线、蒙太奇风格（基于已选剪辑/蒙太奇流派）
#### 台词风格
基于已选台词风格维度，标注对白的语言特征（简练/诗意/生活化/戏剧化等）

## 创作要求
1. **场次起承转合**：每场完整包含 开场→发展→高潮→结局 四个阶段
2. **戏剧张力**：每场有明确的戏剧冲突和情感高潮，避免平铺直叙
3. **视听语言**：每场至少标注3处关键镜头语言（特写/长镜头/蒙太奇/跟拍/俯拍/仰拍）
4. **台词风格**：严格遵循已选台词风格维度，对白体现该风格的语言特征
5. **时长控制**：严格遵守每场{duration[0]}-{duration[1]}分钟时长范围，节奏紧凑
6. **类型特征**：电影叙事比剧集更凝练，每场都需要推动主线或揭示关键信息""")

        if script_mode == "virtual":
            parts.append(self._build_virtual_mode_section("movie"))
            parts.append(f"\n> 当前风格参考：{', '.join(style_names) if style_names else '通用电影风格'}")

        parts.append("\n现在请开始创作本场电影剧本内容：")
        return "\n".join(parts)

    def _build_virtual_mode_section(self, content_type: str) -> str:
        """Task 4.4 + Task 7 集成: 构建虚拟模式AIGC提示词段落

        在剧本正文下方提供分镜设计 + AI场景图提示词 + AI视频提示词，
        使用 Gemini/豆包 和 Seedance 2.0/Veo 最佳实践。
        模板来源：virtual_mode_prompts.py（单一数据源）

        Args:
            content_type: "series" 或 "movie"
        """
        from app.agents.writing.prompts.virtual_mode_prompts import (
            STORYBOARD_TEMPLATE, IMAGE_PROMPT_INTRO, IMAGE_PROMPT_EXAMPLE,
            VIDEO_PROMPT_INTRO,
        )
        unit_label = "集" if content_type == "series" else "场"

        storyboard_section = STORYBOARD_TEMPLATE.format(
            storyboard_rows=f"| 1 | — | — | 待LLM根据剧本内容生成 | — | — |\n| ... | ... | ... | ... | ... | ... |"
        )

        return f"""
### 虚拟模式 — AI视频生成分镜设计

## 分镜设计表（为每{unit_label}关键场景填写）
{storyboard_section}

{IMAGE_PROMPT_INTRO}

{IMAGE_PROMPT_EXAMPLE}

{VIDEO_PROMPT_INTRO}

请为每一场关键场景分别生成上述格式的生成提示词，确保视觉风格与已选风格维度保持一致。
"""

    def _format_series_style_for_prompt(
        self, style_dims: dict, style_names: list, intensity: float
    ) -> str:
        """Task 4.4: 将剧集风格选择器的维度选择格式化为提示词段落

        剧集5维度：风格流派/导演风格/叙事风格/镜头剪辑风格/演绎风格
        """
        if not style_dims:
            return "（未选择特定风格，使用通用剧集风格）"

        dim_labels = {
            "genre": "风格流派", "director": "导演风格",
            "narrative": "叙事风格", "cinematography": "镜头剪辑风格",
            "performance": "演绎风格"
        }
        lines = []
        for dim_id, style_obj in style_dims.items():
            dim_name = dim_labels.get(dim_id, dim_id)
            if isinstance(style_obj, dict):
                lines.append(
                    f"- **{dim_name}**：{style_obj.get('name', '')} — {style_obj.get('description', '')}")
            elif isinstance(style_obj, list) and style_obj:
                s = style_obj[0] if isinstance(style_obj[0], dict) else {}
                lines.append(
                    f"- **{dim_name}**：{s.get('name', '') if isinstance(s, dict) else ''}")

        if style_names:
            lines.append(f"\n已选风格标签：{'、'.join(style_names)}")

        # 阈值与 _context_builder._build_style_config_section() 保持一致
        intensity_level = "强烈-非常突出" if intensity > 0.7 else (
            "适中-明显但不突兀" if intensity > 0.4 else "淡入-轻微体现")
        return f"风格强度：{intensity_level}\n" + "\n".join(lines) if lines else "（未选择特定风格）"

    def _format_movie_style_for_prompt(
        self, style_dims: dict, style_names: list, intensity: float
    ) -> str:
        """Task 4.4: 将电影风格选择器的维度选择格式化为提示词段落

        电影6维度：电影风格流派/导演风格/叙事风格/剪辑蒙太奇流派/演绎表演风格/台词风格
        """
        if not style_dims:
            return "（未选择特定风格，使用通用电影风格）"

        dim_labels = {
            "genre": "电影风格流派", "director": "导演风格",
            "narrative": "叙事风格", "editing": "剪辑/蒙太奇流派",
            "performance": "演绎/表演风格", "dialogue": "台词风格"
        }
        lines = []
        for dim_id, style_obj in style_dims.items():
            dim_name = dim_labels.get(dim_id, dim_id)
            if isinstance(style_obj, dict):
                lines.append(
                    f"- **{dim_name}**：{style_obj.get('name', '')} — {style_obj.get('description', '')}")
            elif isinstance(style_obj, list) and style_obj:
                s = style_obj[0] if isinstance(style_obj[0], dict) else {}
                lines.append(
                    f"- **{dim_name}**：{s.get('name', '') if isinstance(s, dict) else ''}")

        if style_names:
            lines.append(f"\n已选风格标签：{'、'.join(style_names)}")

        # 阈值与 _context_builder._build_style_config_section() 保持一致
        intensity_level = "强烈-非常突出" if intensity > 0.7 else (
            "适中-明显但不突兀" if intensity > 0.4 else "淡入-轻微体现")
        return f"风格强度：{intensity_level}\n" + "\n".join(lines) if lines else "（未选择特定风格）"
