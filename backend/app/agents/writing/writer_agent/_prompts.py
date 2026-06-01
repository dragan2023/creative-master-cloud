"""
多Agent协作文学作品生成系统 - 写手Agent 提示词模块

从 writer_agent.py 拆分，包含所有提示词构建方法。

@date: 2026-04-24
@version: v2.0.0
"""

import re
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
        # 🔴 防御：确保 config / style_guide 是 dict，防止字符串导致的 .get() 崩溃
        _config = context.config if isinstance(context.config, dict) else {}
        _style_guide = context.style_guide if isinstance(context.style_guide, dict) else {}

        # 获取内容类型
        content_type = _config.get("content_type", "novel")

        # 使用专门的提示词获取函数，根据内容类型返回不同的系统提示词
        from app.agents.writing.prompts.character_state_prompts import get_writer_system_prompt
        base_prompt = get_writer_system_prompt(content_type)

        # 优先使用文风知识库风格指南（新增）
        # 🔴 防御：style_library_guide 必须是 dict，非 dict 时忽略（防止字符串覆盖导致的崩溃）
        has_style_section = False
        style_library_guide = _style_guide.get(
            "style_library_guide", {}) if _style_guide else {}
        if style_library_guide and isinstance(style_library_guide, dict):
            from app.tools.style_library import format_style_for_prompt
            style_section = format_style_for_prompt(style_library_guide)
            if style_section:
                base_prompt += "\n\n## 文风要求（**必须严格遵循**）\n\n"
                base_prompt += style_section
                base_prompt += "\n\n请在整个创作过程中始终保持上述文风特征，让读者能清晰感受到风格的独特性。\n"
                has_style_section = True

        # 🆕 风格选择器配置文本（剧集/电影专属，_context_builder 注入）
        style_config_section = _style_guide.get(
            "style_config_section", "") if _style_guide else ""
        if style_config_section:
            base_prompt += "\n\n## 创作风格配置\n\n"
            base_prompt += style_config_section
            base_prompt += "\n"
            has_style_section = True

        # 兼容旧版风格指南（简单文字描述）
        if not has_style_section and _style_guide:
            style_guide = _style_guide
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

        # Seedance 2.0 全能参考模式：剧集/电影始终输出AI视觉资源生成提示词（中文）
        if content_type in ("series_script", "movie_script"):
            base_prompt += "\n## AI视觉资源生成要求（Seedance 2.0 全能参考模式）\n\n"
            base_prompt += "你需要在输出剧本正文内容的同时，生成以下AI视觉资源提示词。**所有视觉资源提示词必须使用中文输出，不得使用英文。**\n\n"
            base_prompt += "1. **人物参考图生成提示词**：为当前单元出场的每位主要角色生成角色概念图提示词。"
            base_prompt += "假设用户已拥有角色定妆照/概念图作为参考，你需要提供用于生成这些参考图的中文提示词。"
            base_prompt += "提示词必须包含：角色外貌特征、服装风格、姿态动作、光影氛围、画幅比例。\n\n"
            base_prompt += "2. **场景参考图生成提示词**：为每个关键场景生成场景概念图提示词。"
            base_prompt += "提示词必须包含：地点描述、时间/天气、氛围基调、电影级构图、画幅比例。\n\n"
            base_prompt += "3. **物品参考图生成提示词**：为重要道具/物品生成道具概念图提示词。"
            base_prompt += "提示词必须包含：物品外观描述、材质质感、光影、白底产品图风格。\n\n"
            base_prompt += "4. **视频生成提示词（Seedance 2.0）**：基于上述已生成的参考图，为每个关键镜头提供视频生成提示词。"
            base_prompt += "必须包含12个字段：【参考模式】、【人物参考图】、【场景参考图】、【物品参考图】、"
            base_prompt += "【镜头类型】、【主体动作】、【环境描述】、【运镜方式】、【风格要求】、【首帧描述】、【尾帧描述】、【负面提示词】。"
            base_prompt += "所有12个字段内容必须使用中文输出。\n\n"
            base_prompt += "5. **知识补充**：如需确定特定历史时期、地点、道具的准确视觉描述，请根据你已有的知识进行推理和补充。\n"
            base_prompt += "确保视觉风格与已选风格维度保持一致，每个提示词都应具体、可操作、可直接用于AI图像/视频生成工具。\n"

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
        """构建直接生成模式的用户提示词

        架构优化版：基于全局大纲+单元概述直接生成，增强前文参考机制。
        新增：集成风格文档特征，确保写作风格一致性。
        支持三种内容类型：小说(novel)→章、剧集(series_script)→集、电影(movie_script)→场

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

        # 🔴 防御：确保 config / extra / style_guide 是 dict，防止字符串导致的 .get() 崩溃
        _cfg = context.config if context and isinstance(context.config, dict) else {}
        _ext = context.extra if context and isinstance(context.extra, dict) else {}
        _sg = context.style_guide if context and isinstance(context.style_guide, dict) else {}

        # 0. 根据内容类型确定单元标签（novel→章, series_script→集, movie_script→场）
        content_type = _cfg.get(
            "content_type", "novel") if context else "novel"
        _unit_label_map = {"novel": "章", "series_script": "集", "movie_script": "场", "script": "场"}
        unit_label = _unit_label_map.get(content_type, "章")

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
            style_document_features = _cfg.get(
                "style_document_features", "")
            if not style_document_features:
                # 兼容：也从 extra 中获取
                style_document_features = _ext.get(
                    "style_document_features", "")

        if style_document_features:
            prompt_parts.append("【风格文档特征（重要：请遵循此风格）】")
            prompt_parts.append("以下是上传的风格文档分析结果，请在创作时严格遵循此风格特征：")
            prompt_parts.append(
                style_document_features[:2000])  # 限制长度避免超出token
            prompt_parts.append("")

        # 3. 本单元信息（单元概述）- 重要剧情约束
        prompt_parts.append(f"【本{unit_label}创作指南（单元概述）— 必须严格遵循】")
        prompt_parts.append(f"标题：{unit_title}")
        if unit_summary:
            prompt_parts.append(f"\n内容概要：\n{unit_summary}")
            prompt_parts.append("")
            prompt_parts.append(f"⚠️ 本{unit_label}创作强制要求：")
            prompt_parts.append(f"1. 以上述单元概述为剧情蓝图，严格控制本{unit_label}的内容边界")
            prompt_parts.append(f"2. 概述中指定的事件、情节发展必须全部覆盖，不得遗漏")
            prompt_parts.append(f"3. 概述中未提及的新人物或重大事件不得在本{unit_label}中引入")
            prompt_parts.append(f"4. 若概述中提到前序单元的伏笔或铺垫，须在正文中合理呼应")
        else:
            prompt_parts.append(f"\n⚠️ 本{unit_label}缺少单元概述，请根据前文内容和全局故事背景合理推断本{unit_label}应有的剧情进展。")
        prompt_parts.append("")

        # 3.6 🔴 冲突检测与处理规则（v2.6新增 — 最高优先级）
        prompt_parts.append(f"【⚠️ 单元概述与人物前文状态冲突检测规则 — 最高优先级】")
        prompt_parts.append(f"在创作本{unit_label}内容前，必须先进行以下冲突检测：")
        prompt_parts.append("")
        prompt_parts.append(f"1. **人物位置冲突检测**：如果单元概述中安排了某人物在某地点出现，但前文人物状态追踪信息显示该人物在其他地点（或明确写明了该人物未跟随/已离开/已死亡等），")
        prompt_parts.append(f"   则**必须以前文人物状态为准**。禁止让该人物以任何方式出现在单元概述指定的地点。")
        prompt_parts.append(f"   处理方式：省略该人物的出场，或调整剧情使其合理到达（需添加明确的移动描写）。")
        prompt_parts.append("")
        prompt_parts.append(f"2. **人物身份/关系冲突检测**：如果单元概述中的人物身份、关系与前文人物状态追踪信息不一致，**必须以前文人物状态为准**。")
        prompt_parts.append("")
        prompt_parts.append(f"3. **人物生死状态冲突检测**：如果前文明确定某人已死亡/失踪/离开，而单元概述又安排其出场，**必须以前文状态为准**，不得让其出场。")
        prompt_parts.append("")
        prompt_parts.append(f"4. **冲突裁决原则**：当单元概述与前文人物状态追踪信息冲突时，优先级规则如下：")
        prompt_parts.append("   ```")
        prompt_parts.append(f"   前文人物状态 > 单元概述 > 全局大纲背景")
        prompt_parts.append("   ```")
        prompt_parts.append(f"   **说明**：前文人物状态追踪信息是已写定的事实，具有最高权威，单元概述不得覆盖已确立的人物状态。")
        prompt_parts.append("")
        relevant_characters = []
        if context and context.character_profiles and unit_summary:
            relevant_characters = self._identify_characters_in_unit_summary(
                unit_summary=unit_summary,
                character_profiles=context.character_profiles
            )
        elif context and context.character_profiles:
            # 没有单元概述时回退到所有角色
            relevant_characters = context.character_profiles

        # 4. 角色设定（人物小传）— 仅本单元出场人物，优先级最高
        if relevant_characters:
            prompt_parts.append("【本单元角色设定（人物小传）— 必须严格遵循】")
            prompt_parts.append("以下是从全局大纲中提取的本单元出场人物基础信息（年龄、性别、身份、性格、背景等）。")
            prompt_parts.append("**仅本单元出场的人物列于此处；所有人物描写必须与此处的设定完全一致，严禁自由修改年龄、性别、身份等基础信息！**")
            prompt_parts.append("")
            for char in relevant_characters:
                if not isinstance(char, dict):
                    continue
                char_name = char.get("name", "")
                if not char_name:
                    continue
                lines = [f"### {char_name}"]
                char_age = char.get("age", "")
                char_gender = char.get("gender", "")
                if char_age or char_gender:
                    basic_parts = []
                    if char_gender:
                        basic_parts.append(char_gender)
                    if char_age:
                        basic_parts.append(f"{char_age}岁" if isinstance(char_age, str) and (char_age.isdigit() or char_age.replace('.','',1).replace('-','',1).isdigit()) else str(char_age))
                    lines.append(f"- 基本信息：{'，'.join(basic_parts)}" if basic_parts else "")
                char_role = char.get("role", char.get("identity", ""))
                if char_role:
                    lines.append(f"- 身份/角色：{char_role}")
                char_personality = char.get("personality", "")
                if char_personality:
                    lines.append(f"- 性格特点：{char_personality}")
                char_background = char.get("background", "")
                if char_background:
                    lines.append(f"- 背景/小传：{char_background}")
                char_appearance = char.get("appearance", "")
                if char_appearance:
                    lines.append(f"- 外貌特征：{char_appearance}")
                char_goals = char.get("goals", "")
                if char_goals:
                    lines.append(f"- 目标/动机：{char_goals}")
                char_desc = char.get("description", "")
                if char_desc and char_desc != char_background:
                    lines.append(f"- 补充描述：{char_desc}")
                # 过滤掉空行
                lines = [l for l in lines if l.strip()]
                if len(lines) > 1:  # 不只是标题行
                    prompt_parts.extend(lines)
                    prompt_parts.append("")
            prompt_parts.append("")

            # 4.5 🔴 OOC防偏约束段 — 基于本单元出场人物的强约束
            ooc_section = self._build_character_ooc_section(relevant_characters)
            if ooc_section:
                prompt_parts.extend(ooc_section)

            # 4.6 🆕 剧本视觉呈现一致性约束（仅适用于剧集/电影）
            if content_type in ("series_script", "movie_script", "script"):
                prompt_parts.append("【视觉呈现一致性约束 — 剧本专用】")
                prompt_parts.append(
                    "同一人物的服装风格、标志性物品、外貌特征在整部作品中必须保持一致。"
                    "如有变化（如角色受伤、伪装、成长），必须有明确的情节解释和过渡。"
                    "场景道具的布置和状态应保持连续性，避免前一场的道具在后一场凭空消失或变化。"
                )
                prompt_parts.append("")

        # 5. 人物状态追踪信息
        if context:
            # 🆕 [知识图谱优化 v3.1] 使用合并后的完整知识图谱上下文
            # 包含: 人物状态 + 扩展实体 (设施、事件、群体、道具、伏笔、规则)
            knowledge_graph_context = _ext.get(
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

        # 6. 前文内容参考（增强滑动窗口 + 精确接续点）
        if previous_content:
            # 扩展前文参考长度到3000字，增强连贯性
            prev_excerpt = previous_content[-3000:] if len(
                previous_content) > 3000 else previous_content
            # 提取最后 ~500 字符作为精确接续点，帮助 LLM 定位上一单元结尾位置
            prev_tail = previous_content[-500:] if len(
                previous_content) > 500 else previous_content
            prompt_parts.append("【前文内容（最后部分，了解故事进展）】")
            prompt_parts.append("..." + prev_excerpt)
            prompt_parts.append("")
            prompt_parts.append(f"【上一{unit_label}结尾处（请由此直接继续，不要回溯）】")
            prompt_parts.append(prev_tail)
            prompt_parts.append("")
            prompt_parts.append("【衔接要求 — 请严格遵循】")
            prompt_parts.append(f"1. 本{unit_label}开头应直接接续「上一{unit_label}结尾处」的场景，从结尾之后开始叙述")
            prompt_parts.append(f"2. **禁止重复**：不要重新描述上一{unit_label}结尾处已经发生过的事件")
            prompt_parts.append(f"3. 保持人物性格、位置、身份与上一{unit_label}结尾处一致")
            prompt_parts.append("4. 延续前文的情感基调和叙事节奏")
            prompt_parts.append(f"5. 如果上一{unit_label}结尾处人物已在某个地点或状态，本{unit_label}直接从该地点/状态推进剧情")
            prompt_parts.append("")

        # 6.5 🆕 累积式情节摘要（覆盖前文所有单元的关键剧情概览）
        if context:
            cumulative_summary = _ext.get("cumulative_summary", "") if hasattr(context, 'extra') and context.extra else ""
            if cumulative_summary:
                prompt_parts.append("【前文情节摘要（累积式，覆盖已发生的所有关键事件）】")
                prompt_parts.append("以下是前文各单元的关键剧情概览，请参考以保持整体情节连贯性：")
                prompt_parts.append(cumulative_summary)
                prompt_parts.append("")

        # 6.6 🆕 全局大纲对齐报告（每5单元更新一次，仅在有偏离时显示）
        if context:
            alignment_report = _ext.get("alignment_report", "") if hasattr(context, 'extra') and context.extra else ""
            if alignment_report and "对齐检查通过" not in alignment_report:
                prompt_parts.append("【全局大纲对齐报告（请优先修正以下偏离）】")
                prompt_parts.append("最近的大纲对齐检查发现以下偏离，请在创作中优先修正：")
                prompt_parts.append(alignment_report)
                prompt_parts.append("")

        # 6.7 🆕 待回收伏笔清单（前文埋设但尚未回收的伏笔）
        if context:
            pending_foreshadowing = _ext.get("pending_foreshadowing", "") if hasattr(context, 'extra') and context.extra else ""
            if pending_foreshadowing:
                prompt_parts.append(pending_foreshadowing)
                prompt_parts.append("")

        # 6.8 🆕 扩展一致性上下文 — 设施状态参考
        if context:
            ext_consistency = _ext.get("extended_consistency", {}) if hasattr(context, 'extra') and context.extra else {}
            # 🔴 防御：extended_consistency 必须是 dict，防止字符串/非dict导致的嵌套 .get() 崩溃
            if not isinstance(ext_consistency, dict):
                ext_consistency = {}
            facilities = ext_consistency.get("facilities", {})
            # 🔴 防御：facilities 必须是 dict（防止字符串被当作 dict 遍历）
            if facilities and isinstance(facilities, dict):
                prompt_parts.append("【设施状态参考 — 请注意设施当前状态】")
                prompt_parts.append("以下是前文已出现的设施及其当前状态，请在创作中保持一致：")
                for fname, finfo in facilities.items():
                    # 🔴 防御：finfo 必须是 dict（防止字符串值导致 .get() 崩溃）
                    if not isinstance(finfo, dict):
                        # 降级嵌入：将非 dict 值格式化为纯文本
                        if isinstance(finfo, str):
                            prompt_parts.append(f"- {fname}：{finfo}")
                        continue
                    status = finfo.get("status", "未知")
                    location = finfo.get("location", "")
                    manager = finfo.get("manager", "")
                    extra_info = ""
                    if location:
                        extra_info += f"，位于{location}"
                    if manager:
                        extra_info += f"，负责人：{manager}"
                    status_mark = ""
                    if status in ["关闭", "损坏", "暂停营业", "已拆除"]:
                        status_mark = " ⚠️ 异常"
                    prompt_parts.append(f"- {fname}：当前状态={status}{status_mark}{extra_info}")
                prompt_parts.append("")

        # 6.9 🆕 扩展一致性上下文 — 未完成事件约束
        if context:
            ext_consistency = _ext.get("extended_consistency", {}) if hasattr(context, 'extra') and context.extra else {}
            # 🔴 防御：extended_consistency 必须是 dict，防止字符串/非dict导致的嵌套 .get() 崩溃
            if not isinstance(ext_consistency, dict):
                ext_consistency = {}
            events = ext_consistency.get("events", [])
            # 🔴 防御：events 必须是 list（防止字符串被当作 list 遍历）
            if events and isinstance(events, list):
                prompt_parts.append("【未完成事件约束 — 请推进或解决以下事件】")
                prompt_parts.append("以下是前文未完成的事件，请在后续创作中有计划地推进：")
                for ev in events:
                    # 🔴 防御：ev 必须是 dict（防止字符串元素导致 .get() 崩溃）
                    if not isinstance(ev, dict):
                        # 降级嵌入：将非 dict 值格式化为纯文本
                        if isinstance(ev, str):
                            prompt_parts.append(f"- {ev}")
                        continue
                    ev_name = ev.get("name", "")
                    ev_status = ev.get("status", "进行中")
                    ev_chars = ev.get("involved_characters", [])
                    ev_loc = ev.get("location", "")
                    ev_first = ev.get("first_chapter", "?")
                    detail = f"- {ev_name}：状态={ev_status}（始于第{ev_first}章）"
                    if ev_chars:
                        detail += f"，涉及人物：{', '.join(ev_chars[:3])}"
                    if ev_loc:
                        detail += f"，发生地点：{ev_loc}"
                    prompt_parts.append(detail)
                prompt_parts.append("")

        # 6.10 🆕 扩展一致性上下文 — 群体动态参考
        if context:
            ext_consistency = _ext.get("extended_consistency", {}) if hasattr(context, 'extra') and context.extra else {}
            # 🔴 防御：extended_consistency 必须是 dict，防止字符串/非dict导致的嵌套 .get() 崩溃
            if not isinstance(ext_consistency, dict):
                ext_consistency = {}
            groups = ext_consistency.get("groups", {})
            # 🔴 防御：groups 必须是 dict（防止字符串被当作 dict 遍历）
            if groups and isinstance(groups, dict):
                prompt_parts.append("【群体组织状态 — 请注意群体当前状态】")
                prompt_parts.append("以下是前文出现的群体组织及其当前状态，请在创作中保持一致：")
                for gname, ginfo in groups.items():
                    # 🔴 防御：ginfo 必须是 dict（防止字符串值导致 .get() 崩溃）
                    if not isinstance(ginfo, dict):
                        # 降级嵌入：将非 dict 值格式化为纯文本
                        if isinstance(ginfo, str):
                            prompt_parts.append(f"- {gname}：{ginfo}")
                        continue
                    status = ginfo.get("status", "活跃")
                    scale = ginfo.get("scale", "")
                    leader = ginfo.get("leader", "")
                    detail = f"- {gname}：状态={status}"
                    if scale:
                        detail += f"，规模={scale}"
                    if leader:
                        detail += f"，领袖={leader}"
                    if status in ["解散", "合并", "消亡"]:
                        detail += " ⚠️ 已解散/消亡"
                    prompt_parts.append(detail)
                prompt_parts.append("")

        # 6.11 🆕 扩展一致性上下文 — 道具归属约束
        if context:
            ext_consistency = _ext.get("extended_consistency", {}) if hasattr(context, 'extra') and context.extra else {}
            # 🔴 防御：extended_consistency 必须是 dict，防止字符串/非dict导致的嵌套 .get() 崩溃
            if not isinstance(ext_consistency, dict):
                ext_consistency = {}
            items = ext_consistency.get("items", {})
            # 🔴 防御：items 必须是 dict（防止字符串被当作 dict 遍历）
            if items and isinstance(items, dict):
                prompt_parts.append("【道具归属与状态 — 请注意道具当前持有者和状态】")
                prompt_parts.append("以下是前文出现的道具及其当前状态，请确保归属和状态一致：")
                for iname, iinfo in items.items():
                    # 🔴 防御：iinfo 必须是 dict（防止字符串值导致 .get() 崩溃）
                    if not isinstance(iinfo, dict):
                        # 降级嵌入：将非 dict 值格式化为纯文本
                        if isinstance(iinfo, str):
                            prompt_parts.append(f"- {iname}：{iinfo}")
                        continue
                    owner = iinfo.get("owner", "未知")
                    status = iinfo.get("status", "完好")
                    itype = iinfo.get("type", "")
                    detail = f"- {iname}"
                    if itype:
                        detail += f"（{itype}）"
                    detail += f"：持有者={owner}，状态={status}"
                    if status in ["丢失", "损坏", "销毁", "已使用"]:
                        detail += " ⚠️ 不可再使用"
                    prompt_parts.append(detail)
                prompt_parts.append("")

        # 6.12 🆕 扩展一致性上下文 — 世界规则约束
        if context:
            ext_consistency = _ext.get("extended_consistency", {}) if hasattr(context, 'extra') and context.extra else {}
            # 🔴 防御：extended_consistency 必须是 dict，防止字符串/非dict导致的嵌套 .get() 崩溃
            if not isinstance(ext_consistency, dict):
                ext_consistency = {}
            rules = ext_consistency.get("rules", [])
            # 🔴 防御：rules 必须是 list（防止字符串被当作 list 遍历）
            if rules and isinstance(rules, list):
                prompt_parts.append("【世界规则约束 — 创作内容不得违反以下规则】")
                prompt_parts.append("以下是故事世界中已确立的规则，请确保内容不违反：")
                for rule in rules:
                    # 🔴 防御：rule 必须是 dict（防止字符串元素导致 .get() 崩溃）
                    if not isinstance(rule, dict):
                        # 降级嵌入：将非 dict 值格式化为纯文本
                        if isinstance(rule, str):
                            prompt_parts.append(f"- {rule}")
                        continue
                    rname = rule.get("name", "")
                    rtype = rule.get("type", "")
                    rdesc = rule.get("description", "")
                    rstatus = rule.get("status", "生效")
                    detail = f"- {rname}"
                    if rtype:
                        detail += f"（{rtype}）"
                    detail += f"：状态={rstatus}"
                    if rdesc:
                        detail += f" — {rdesc}"
                    prompt_parts.append(detail)
                prompt_parts.append("")

        # 6.13 🆕 扩展一致性上下文 — 时间线上下文
        if context:
            ext_consistency = _ext.get("extended_consistency", {}) if hasattr(context, 'extra') and context.extra else {}
            # 🔴 防御：extended_consistency 必须是 dict，防止字符串/非dict导致的嵌套 .get() 崩溃
            if not isinstance(ext_consistency, dict):
                ext_consistency = {}
            time_ctx = ext_consistency.get("time", {})
            # 🔴 防御：time_ctx 必须是 dict（防止字符串导致 .get() 崩溃）
            if time_ctx and isinstance(time_ctx, dict):
                time_nodes = time_ctx.get("time_nodes", [])
                time_elapsed = time_ctx.get("time_elapsed", [])
                if time_nodes or time_elapsed:
                    prompt_parts.append("【时间线上下文 — 请注意时间连续性】")
                    if time_nodes and isinstance(time_nodes, list):
                        prompt_parts.append("已建立的时间节点：")
                        for node in time_nodes:
                            # 🔴 防御：node 必须是 dict（防止字符串元素导致 .get() 崩溃）
                            if not isinstance(node, dict):
                                # 降级嵌入：将非 dict 值格式化为纯文本
                                if isinstance(node, str):
                                    prompt_parts.append(f"  - {node}")
                                continue
                            nname = node.get("name", "")
                            ntype = node.get("type", "")
                            detail = f"  - {nname}"
                            if ntype:
                                detail += f"（{ntype}）"
                            prompt_parts.append(detail)
                    if time_elapsed and isinstance(time_elapsed, list):
                        prompt_parts.append("时间流逝记录：")
                        for flow in time_elapsed:
                            # 🔴 防御：flow 必须是 dict（防止字符串元素导致 .get() 崩溃）
                            if isinstance(flow, dict):
                                prompt_parts.append(f"  - {flow.get('description', '')}")
                            elif isinstance(flow, str):
                                prompt_parts.append(f"  - {flow}")
                    prompt_parts.append("")

        # 6.14 🆕 扩展一致性上下文 — 交叉一致性警告
        if context:
            ext_consistency = _ext.get("extended_consistency", {}) if hasattr(context, 'extra') and context.extra else {}
            # 🔴 防御：extended_consistency 必须是 dict，防止字符串/非dict导致的嵌套 .get() 崩溃
            if not isinstance(ext_consistency, dict):
                ext_consistency = {}
            cross_issues = ext_consistency.get("cross_consistency_issues", [])
            # 🔴 防御：cross_issues 必须是 list（防止字符串被当作 list 遍历）
            if cross_issues and isinstance(cross_issues, list):
                prompt_parts.append("【一致性警告 — 请务必修正以下冲突】")
                prompt_parts.append("系统检测到以下跨实体一致性冲突，请在本次创作中修正：")
                for issue in cross_issues:
                    # 🔴 防御：issue 必须是 dict（防止字符串元素导致 .get() 崩溃）
                    if not isinstance(issue, dict):
                        # 降级嵌入：将非 dict 值格式化为纯文本
                        if isinstance(issue, str):
                            prompt_parts.append(f"⚠️ {issue}")
                        continue
                    issue_type = issue.get("type", "")
                    issue_msg = issue.get("message", "")
                    issue_sev = issue.get("severity", "warning")
                    prefix = "❌ 错误" if issue_sev == "error" else "⚠️ 警告"
                    prompt_parts.append(f"{prefix} [{issue_type}] {issue_msg}")
                prompt_parts.append("")

        # 7. 字数/时长要求（根据内容类型区分）
        if content_type in ("script", "series_script", "movie_script"):
            # 剧本类型使用时长约束
            if context:
                duration_minutes = _cfg.get("duration_minutes")
                if not duration_minutes:
                    # 兜底：从 duration_range / episode_duration_range 计算
                    if content_type == "series_script":
                        er = _cfg.get("episode_duration_range", [30, 45])
                        duration_minutes = int((er[0] + er[1]) / 2) if isinstance(er, (list, tuple)) and len(er) == 2 else 40
                    elif content_type == "movie_script":
                        dr = _cfg.get("duration_range", [10, 15])
                        duration_minutes = int((dr[0] + dr[1]) / 2) if isinstance(dr, (list, tuple)) and len(dr) == 2 else 12
                    else:
                        duration_minutes = 5
            else:
                duration_minutes = 5
            prompt_parts.append(f"【时长要求】")
            prompt_parts.append(
                f"预计时长：约{duration_minutes}分钟（剧本按1分钟≈150-200字估算）")
            prompt_parts.append("")
        else:
            prompt_parts.append(f"【字数要求】")
            prompt_parts.append(f"目标字数：{target_words}字（误差不超过±10%）")
            prompt_parts.append("")

        # 7.5 风格强度控制（小说类型）
        if content_type not in ("script", "series_script", "movie_script") and context:
            style_intensity_for_prompt = _get_style_intensity(context)
            if style_intensity_for_prompt is not None:
                intensity_percent = int(style_intensity_for_prompt * 100)
                from app.utils.style_utils import intensity_to_description
                intensity_desc = intensity_to_description(style_intensity_for_prompt)
                # 强度体现程度: 轻微/明显/显著
                intensity_effect = "轻微" if style_intensity_for_prompt <= 0.4 else ("明显" if style_intensity_for_prompt <= 0.7 else "显著")
                prompt_parts.append(f"当前风格强度为 {intensity_percent}%（{intensity_desc}），请在创作中{intensity_effect}体现所选文风的特征。")
                prompt_parts.append("")

        # 8. 输出格式（按内容类型独立化）
        if content_type == "series_script":
            prompt_parts.append(self._build_series_output_format(context))
        elif content_type == "movie_script":
            prompt_parts.append(self._build_movie_output_format(context))
        elif content_type == "script":
            # 兼容旧的统一script类型
            prompt_parts.append(self._build_legacy_script_output_format(context))
        else:
            prompt_parts.append(self._build_novel_output_format(context, unit_label))

        return "\n".join(prompt_parts)

    # ==================== Task 4: 剧集/电影独立输出格式 ====================

    def _build_legacy_script_output_format(self, context: AgentContext) -> str:
        """兼容旧的统一script类型的输出格式（向后兼容）"""
        return """【创作要求】
1. 使用标准剧本格式输出
2. 对话简洁有力，动作描述清晰，**严格按照上方单元概述的剧情规划展开**
3. 场景转换流畅
4. 在场景结尾设置适当的钩子或过渡
5. 严格控制时长，不要超出或不足太多
6. **核心要求**：
   - 剧情发展以单元概述为最高准则，严禁偏离概述中规划的剧情走向
   - 确保人物位置、身份、关系与状态追踪信息一致
   - 与前文内容紧密衔接，避免剧情跳脱

现在请开始创作剧本内容："""

    def _build_series_output_format(self, context: AgentContext) -> str:
        """Task 4.2: 构建剧集专属输出格式模板

        嵌入剧集风格选择器配置（5维度）和系列参数。
        """
        series_type = context.config.get("series_type", "电视剧") if isinstance(context.config, dict) else "电视剧"
        duration = context.config.get("episode_duration_range", [30, 45]) if isinstance(context.config, dict) else [30, 45]
        style_dims = context.config.get("series_style_dimensions", {}) if isinstance(context.config, dict) else {}
        style_names = context.config.get("series_style_names", []) if isinstance(context.config, dict) else []
        style_intensity = context.config.get("series_style_intensity", 0.7) if isinstance(context.config, dict) else 0.7
        script_mode = context.config.get("script_mode", "real") if isinstance(context.config, dict) else "real"
        scenes_per_episode = context.config.get("scenes_per_episode_range", None) if isinstance(context.config, dict) else None
        # [修复] 明确传递当前集数，防止LLM在巨型上下文中混淆
        episode_number = context.unit_index if context.unit_index else 1
        total_units = context.config.get("total_units", "?") if isinstance(context.config, dict) else "?"

        style_guidance = self._format_series_style_for_prompt(
            style_dims, style_names, style_intensity)

        # 构建 Seedance 2.0 全能参考模式段落（剧集/电影始终包含）
        comprehensive_ref_section = self._build_comprehensive_ref_section("series", context)

        parts = []
        parts.append(f"""# 剧集剧本输出格式要求

## ⚠️ 剧情规划约束（最高优先级）
**必须严格遵循上方「本集创作指南（单元概述）」中规划的剧情内容。** 概述中指定的事件、出场人物、情节发展不得遗漏或擅自变更。

## ⚠️ 语言要求
**本集所有内容（包括正文、分镜设计、场景描述、拍摄指导、运镜设计、光影方案、演出指导、剪辑思路、连续性衔接、AI视觉资源生成等）必须使用中文输出，不得使用英文。**

## 已选剧集风格（强度{int(style_intensity * 100)}%）
{style_guidance}
请在叙事风格、对话特点、场景描述中充分体现上述风格特征。

## 本集信息
- 当前集数：第{episode_number}集（共{total_units}集）
- 剧集类型：{series_type}
- 时长控制：{duration[0]}-{duration[1]}分钟""")

        if scenes_per_episode:
            parts.append(f"- 场景数范围：{scenes_per_episode[0]}-{scenes_per_episode[1]}个场景")

        parts.append(f"""
## 输出结构
### 第{episode_number}集：[标题]
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

### AI视觉资源生成（Seedance 2.0 全能参考模式）
{comprehensive_ref_section}

## 创作要求
1. **集间连续性**：本集开头自然承接上一集结尾状态；本集结尾铺设明确的悬念或过渡
2. **场景密度**：每集场景数量合理，情节密度适中
3. **时长控制**：本集剧本正文（含动作描述与对白）预估银幕时长约{duration[0]}-{duration[1]}分钟。**注意：此约束仅针对剧本正文部分，拍摄脚本参考（运镜设计、光影方案、演出指导、剪辑思路）和AI视觉资源生成内容不在此时长限制内，应完整、详细地输出。**
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
        movie_type = context.config.get("movie_type", "电影") if isinstance(context.config, dict) else "电影"
        duration = context.config.get("duration_range", [10, 15]) if isinstance(context.config, dict) else [10, 15]
        style_dims = context.config.get("movie_style_dimensions", {}) if isinstance(context.config, dict) else {}
        style_names = context.config.get("movie_style_names", []) if isinstance(context.config, dict) else []
        style_intensity = context.config.get("movie_style_intensity", 0.7) if isinstance(context.config, dict) else 0.7
        script_mode = context.config.get("script_mode", "real") if isinstance(context.config, dict) else "real"
        total_scenes = context.config.get("total_scenes", 0) if isinstance(context.config, dict) else 0

        style_guidance = self._format_movie_style_for_prompt(
            style_dims, style_names, style_intensity)

        # 构建 Seedance 2.0 全能参考模式段落（剧集/电影始终包含）
        comprehensive_ref_section = self._build_comprehensive_ref_section("movie", context)

        # [修复] 明确传递当前场次编号
        scene_number = context.unit_index if context.unit_index else 1
        total_units = context.config.get("total_units", "?") if isinstance(context.config, dict) else "?"

        parts = []
        parts.append(f"""# 电影剧本输出格式要求

## ⚠️ 剧情规划约束（最高优先级）
**必须严格遵循上方「本场创作指南（单元概述）」中规划的剧情内容。** 概述中指定的事件、出场人物、情节发展不得遗漏或擅自变更。

## ⚠️ 语言要求
**本场所有内容（包括正文、分镜设计、场景描述、拍摄指导、运镜设计、光影方案、演出指导、剪辑思路、台词风格标注、AI视觉资源生成等）必须使用中文输出，不得使用英文。**

## 已选电影风格（强度{int(style_intensity * 100)}%）
{style_guidance}
请在叙事风格、台词设计、场景描述中充分体现上述风格特征。

## 本场信息
- 当前场次：第{scene_number}场（共{total_units}场）
- 电影类型：{movie_type}
- 时长控制：每场约{duration[0]}-{duration[1]}分钟""")

        if total_scenes > 0:
            parts.append(f"- 总场次数：{total_scenes}场")

        parts.append(f"""
## 场次结构要求（核心）
每场须包含完整的：开场（建立氛围/引入冲突）→ 发展（矛盾升级/角色关系变化）→ 高潮（冲突爆发/关键转折）→ 结局（场景收尾/为下一场铺垫）

## 输出结构
### 第{scene_number}场：[标题]
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

### AI视觉资源生成（Seedance 2.0 全能参考模式）
{comprehensive_ref_section}

## 创作要求
1. **场次起承转合**：每场完整包含 开场→发展→高潮→结局 四个阶段
2. **戏剧张力**：每场有明确的戏剧冲突和情感高潮，避免平铺直叙
3. **视听语言**：每场至少标注3处关键镜头语言（特写/长镜头/蒙太奇/跟拍/俯拍/仰拍）
4. **台词风格**：严格遵循已选台词风格维度，对白体现该风格的语言特征
5. **时长控制**：本场剧本正文（含动作描述与对白）预估银幕时长约{duration[0]}-{duration[1]}分钟。**注意：此约束仅针对剧本正文部分，拍摄脚本参考（运镜设计、光影方案、演出指导、剪辑思路）和AI视觉资源生成内容不在此时长限制内，应完整、详细地输出。**
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

    def _build_comprehensive_ref_section(self, content_type: str, context):
        """构建 Seedance 2.0 全能参考模式段落（剧集/电影始终包含）

        强化版：引导LLM主动提取剧本中的视觉元素并生成可操作的提示词，
        而非使用填空模板。每个提示词都是完整的、可直接用于AI图像/视频生成工具。
        """
        from app.agents.writing.prompts.virtual_mode_prompts import (
            SEEDANCE_COMPREHENSIVE_REFERENCE_INTRO,
        )
        unit_label = "集" if content_type == "series" else "场"
        if content_type == "series":
            style_names = context.config.get("series_style_names", []) if isinstance(context.config, dict) else []
        else:
            style_names = context.config.get("movie_style_names", []) if isinstance(context.config, dict) else []
        style_tags = "、".join(style_names) if style_names else "通用"
        aspect_ratio = context.config.get("aspect_ratio", "16:9") if isinstance(context.config, dict) else "16:9"
        character_names = []
        if context.character_profiles:
            for char in context.character_profiles:
                if isinstance(char, dict) and char.get("name"):
                    character_names.append(char["name"])

        parts = [SEEDANCE_COMPREHENSIVE_REFERENCE_INTRO, ""]
        parts.append("### 一、人物参考图生成提示词")
        if character_names:
            parts.append(f"请为当前{unit_label}出场的以下主要角色，根据剧本中的人物设定和外貌描述，生成角色概念图提示词：")
            parts.append("")
            for char_name in character_names[:8]:
                parts.append(f"- **{char_name}**：请LLM根据人物设定（外貌、服装、气质）生成完整的角色概念图提示词")
            parts.append("")
            parts.append("**每位角色的提示词必须包含以下要素**：")
            parts.append("- 角色外貌特征（年龄、体型、面部特征、发型发色等）")
            parts.append("- 服装风格（时代、款式、颜色、材质、配饰）")
            parts.append("- 姿态动作（站姿/动态、表情、眼神方向）")
            parts.append("- 光影氛围（光源方向、色温、明暗对比）")
            parts.append(f"- 视觉风格标签：{style_tags}")
            parts.append(f"- 画面规格：角色概念图，高质量，人物定妆照，{aspect_ratio}")
            parts.append("")
            parts.append("**输出格式示例**：")
            parts.append("```")
            parts.append(f"{char_name}的角色概念图，[具体外貌特征描述]，[具体服装描述]，")
            parts.append(f"[姿态动作描述]，[光影氛围描述]，{style_tags}风格，人物肖像，高质量，角色设定图，{aspect_ratio}")
            parts.append("```")
        else:
            parts.append(f"请LLM根据当前{unit_label}剧本内容，主动识别出场人物，为每位主要角色生成角色概念图提示词。")
            parts.append("提示词需包含：外貌特征、服装风格、姿态动作、光影氛围、画幅比例。")
        parts.append("")

        parts.append("### 二、场景参考图生成提示词")
        parts.append(f"请为当前{unit_label}的每个关键场景生成场景概念图提示词：")
        parts.append("")
        parts.append("**每个场景提示词必须包含以下要素**：")
        parts.append("- 地点描述（具体场景名、空间特征、建筑风格）")
        parts.append("- 时间/天气（日/夜/晨/昏、晴天/阴天/雨天等）")
        parts.append("- 氛围基调（紧张/宁静/浪漫/恐怖/史诗等）")
        parts.append("- 电影级构图（广角全景/中景/特写、低角度/高角度/平视）")
        parts.append(f"- 视觉风格标签：{style_tags}")
        parts.append(f"- 画面规格：场景概念图，电影级质感，高质量，{aspect_ratio}")
        parts.append("")
        parts.append("**输出格式示例**：")
        parts.append("```")
        parts.append(f"[场景名]的场景概念图，[地点空间描述]，[时间天气描述]，")
        parts.append(f"[氛围基调描述]，[构图方式描述]，{style_tags}风格，电影级质感，高质量，{aspect_ratio}")
        parts.append("```")
        parts.append("")

        parts.append("### 三、物品参考图生成提示词")
        parts.append(f"请为当前{unit_label}中出现的重要道具/物品生成道具概念图提示词：")
        parts.append("")
        parts.append("**每个物品提示词必须包含以下要素**：")
        parts.append("- 物品外观描述（形状、大小、颜色、纹理）")
        parts.append("- 材质质感（金属/木质/布料/玉石/玻璃等）")
        parts.append("- 光影（专业产品布光、高光/阴影处理）")
        parts.append(f"- 视觉风格标签：{style_tags}")
        parts.append(f"- 画面规格：道具概念图，高质量，白底产品图，{aspect_ratio}")
        parts.append("")
        parts.append("**输出格式示例**：")
        parts.append("```")
        parts.append(f"[道具名]的道具概念图，[外观材质描述]，[光影描述]，")
        parts.append(f"{style_tags}风格，高质量，白底产品图，{aspect_ratio}")
        parts.append("```")
        parts.append("")

        parts.append("### 四、基于参考图的视频生成提示词（Seedance 2.0 全能参考模式）")
        parts.append(f"基于上述已生成的人物/场景/物品参考图，为当前{unit_label}的每个关键镜头生成Seedance 2.0视频提示词。")
        parts.append("假设用户已将参考图上传至Seedance 2.0，你需要为每个镜头提供完整的视频生成参数。")
        parts.append("")
        parts.append("**每个视频提示词必须包含以下12个字段**：")
        parts.append("")
        parts.append("| 序号 | 字段名 | 说明 |")
        parts.append("|------|--------|------|")
        parts.append("| 1 | 参考模式 | 固定填写：全能参考 |")
        parts.append("| 2 | 人物参考图 | 引用上方生成的人物参考图名称 |")
        parts.append("| 3 | 场景参考图 | 引用上方生成的场景参考图名称 |")
        parts.append("| 4 | 物品参考图 | 引用上方生成的物品参考图名称（如无则为空） |")
        parts.append("| 5 | 镜头类型 | 景别（特写/近景/中景/全景/远景）+ 运动方式（推/拉/摇/移/跟/升降/固定） |")
        parts.append("| 6 | 主体动作 | 精确描述画面中主体的动作和运动轨迹 |")
        parts.append("| 7 | 环境描述 | 场景环境、天气、时间、氛围 |")
        parts.append("| 8 | 运镜方式 | 摄像机运动的具体描述（如：缓慢推近、横摇跟随等） |")
        parts.append(f"| 9 | 风格要求 | 视觉风格标签：{style_tags} |")
        parts.append("| 10 | 首帧描述 | 视频起始画面的具体描述 |")
        parts.append("| 11 | 尾帧描述 | 视频结束画面的具体描述 |")
        parts.append("| 12 | 负面提示词 | 不希望出现的元素（如：模糊、抖动、变形、水印等） |")
        parts.append("")
        parts.append("**输出格式示例**：")
        parts.append("```")
        parts.append("[参考模式]：全能参考")
        parts.append("[人物参考图]：[人物名]的角色概念图")
        parts.append("[场景参考图]：[场景名]的场景概念图")
        parts.append("[物品参考图]：[道具名]的道具概念图（如适用）")
        parts.append("[镜头类型]：中景，缓慢推近")
        parts.append("[主体动作]：[人物名]从画面左侧走向右侧，转身面对镜头，表情由凝重转为坚定")
        parts.append("[环境描述]：黄昏时分，古城街道，夕阳余晖洒在石板路上，远处有炊烟袅袅")
        parts.append("[运镜方式]：从中景开始，缓慢推近至近景，跟随主体横向移动后定格")
        parts.append(f"[风格要求]：{style_tags}，电影级质感，暖色调，戏剧性光影")
        parts.append("[首帧描述]：黄昏街道全景，[人物名]独自站立在街道中央，背对镜头")
        parts.append("[尾帧描述]：近景特写[人物名]的面部，坚定的眼神望向远方")
        parts.append("[负面提示词]：模糊，抖动，画面变形，低质量，水印，文字")
        parts.append("```")
        parts.append("")
        parts.append(f"> 视觉风格：{style_tags} | 画幅：{aspect_ratio}")
        parts.append("> 以上提示词可直接用于Gemini/DALL-E/豆包生成参考图，以及Seedance 2.0进行视频生成")
        parts.append("")
        parts.append("**⚠️ 重要提示：以上所有参考图生成提示词和视频生成提示词，必须使用中文输出，"
                     "不得使用英文。所有字段描述必须为中文内容。**")
        return "\n".join(parts)

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

        from app.utils.style_utils import intensity_to_description
        # 阈值由 style_utils.intensity_to_description() 统一管理
        intensity_level = intensity_to_description(intensity)
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

        from app.utils.style_utils import intensity_to_description
        # 阈值由 style_utils.intensity_to_description() 统一管理
        intensity_level = intensity_to_description(intensity)
        return f"风格强度：{intensity_level}\n" + "\n".join(lines) if lines else "（未选择特定风格）"

    # ==================== 人物出场识别与OOC防偏机制 ====================

    @staticmethod
    def _identify_characters_in_unit_summary(
        unit_summary: str,
        character_profiles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从单元概述中正则匹配本单元出场人物

        扫描 unit_summary 文本，识别其中提到的人物名称，
        从 character_profiles 中筛选出本单元相关的角色。

        算法：
        1. 从 character_profiles 收集所有已知人物名称
        2. 按名称长度降序排列（优先匹配长名称，避免「叶辰」与「叶」冲突）
        3. 用正则在 unit_summary 中搜索每个名称
        4. 返回匹配成功的角色 profile
        5. 兜底：如果未匹配到任何人，返回主角（前3位）

        Args:
            unit_summary: 单元概述文本
            character_profiles: 完整的人物设定列表

        Returns:
            本单元出场的人物设定列表
        """
        if not unit_summary or not character_profiles:
            return character_profiles or []

        # 1. 收集所有人物名称，按长度降序排列
        name_profile_pairs = []
        for char in character_profiles:
            if not isinstance(char, dict):
                continue
            name = char.get("name", "")
            if name and len(name) >= 2:  # 过滤掉单字名称避免误匹配
                name_profile_pairs.append((name, char))

        # 按名称长度降序：长名称优先匹配（避免"东方月初"被"东方"截胡）
        name_profile_pairs.sort(key=lambda x: len(x[0]), reverse=True)

        # 2. 在 unit_summary 中搜索每个名称
        matched_profiles = []
        matched_names = set()
        summary_text = unit_summary

        for name, profile in name_profile_pairs:
            if name in matched_names:
                continue
            # 使用正则精确匹配：名称前后应为非字母数字字符或边界
            pattern = re.compile(r'(?<!\w)' + re.escape(name) + r'(?!\w)')
            if pattern.search(summary_text):
                matched_profiles.append(profile)
                matched_names.add(name)

        # 3. 也检查单字名称（如"叶"、"萧"），但仅在长名未匹配时尝试
        for char in character_profiles:
            if not isinstance(char, dict):
                continue
            name = char.get("name", "")
            if name and len(name) == 1 and name not in matched_names:
                # 单字匹配要求更严格：前后必须是标点/空格/边界
                pattern = re.compile(r'(?<=[，。！？、\s\)）])' + re.escape(name) + r'(?=[，。！？、\s\(（])')
                if pattern.search(summary_text):
                    matched_profiles.append(char)
                    matched_names.add(name)

        # 4. 兜底：如果完全没有匹配，返回前3个角色（默认主角团）
        if not matched_profiles and character_profiles:
            matched_profiles = character_profiles[:3]

        return matched_profiles

    @staticmethod
    def _build_character_ooc_section(
        relevant_characters: List[Dict[str, Any]]
    ) -> List[str]:
        """为本单元出场人物构建 OOC 防偏约束段

        针对每个出场角色，生成强约束指令，防止AI生成时出现：
        - 性格偏离（如冷静角色突然暴怒无铺垫）
        - 身份错位（如平民突然拥有贵族特权）
        - 关系紊乱（如敌人突然亲密无间）
        - 语言风格不符（如古代人物说现代网络用语）

        Args:
            relevant_characters: 本单元出场的人物设定列表

        Returns:
            OOC约束提示词段落（字符串列表）
        """
        if not relevant_characters:
            return []

        lines = []
        lines.append("【OOC防偏约束 — 必须严格遵循】")
        lines.append("以下针对每个出场角色的行为、语言、性格设定约束，"
                     "请在创作时逐条核对，严禁出现角色崩坏（OOC）：")
        lines.append("")

        for char in relevant_characters:
            if not isinstance(char, dict):
                continue
            name = char.get("name", "")
            if not name:
                continue

            char_lines = [f"### {name} — OOC约束"]

            # 性格约束
            personality = char.get("personality", "")
            if personality:
                char_lines.append(
                    f"- **性格铁律**：此人性格为「{personality}」，"
                    f"所有行为、语言、心理活动必须与此性格一致。"
                    f"如需性格转变，必须有充分的情节铺垫，不可突变。"
                )

            # 身份约束
            identity = char.get("role", char.get("identity", ""))
            if identity:
                char_lines.append(
                    f"- **身份铁律**：此人身份为「{identity}」，"
                    f"其行为权限、社交范围、语言方式必须符合此身份设定。"
                )

            # 年龄/性别约束
            age = char.get("age", "")
            gender = char.get("gender", "")
            if age or gender:
                parts = []
                if gender:
                    parts.append(f"性别为{gender}")
                if age:
                    age_str = str(age)
                    parts.append(f"年龄为{age_str}岁" if age_str.isdigit() else f"年龄为{age_str}")
                char_lines.append(f"- **基础属性铁律**：{'，'.join(parts)}，言行举止必须与其年龄性别相符。")

            # 背景约束
            background = char.get("background", "")
            if background:
                char_lines.append(
                    f"- **背景铁律**：{background}，人物行为决策必须受此背景影响。"
                )

            # 目标/动机约束
            goals = char.get("goals", "")
            if goals:
                char_lines.append(
                    f"- **动机铁律**：此人的核心目标为「{goals}」，"
                    f"其行为驱动力必须与此目标一致。"
                )

            char_lines.append(
                f"- **兜底原则**：如不确定{name}在某情境下应如何反应，"
                f"请回顾以上设定，选择最符合其性格和身份的行为，而非选择戏剧性但OOC的做法。"
            )

            lines.extend(char_lines)
            lines.append("")

        lines.append("**以上OOC约束优先级高于一切创作自由。宁可情节平淡，不可角色崩坏。**")
        lines.append("")

        return lines

    # ==================== Task 4: 小说独立输出格式 ====================

    def _build_novel_output_format(
        self, context: AgentContext, unit_label: str = "章"
    ) -> str:
        """Task 4.1: 构建小说专属输出格式模板

        嵌入文风知识库风格指南和风格强度，确保小说生成也具备风格约束。

        Args:
            context: 执行上下文
            unit_label: 单元标签（如"章"）

        Returns:
            格式化后的输出要求文本
        """
        parts = []
        parts.append(f"""【创作要求】
1. 直接输出正文内容，不要包含{unit_label}节标题等标记
2. 内容要充实，有完整的故事情节，**以上方单元概述为剧情规划参考**
3. 场景描写要生动，对话要自然
4. 注意节奏把控，有张有弛
5. 本{unit_label}末尾设置适当的悬念或收束
6. 严格控制字数，不要超出或不足太多
7. **核心要求**：
   - 剧情发展以单元概述为指导，但**必须优先遵循上方「冲突检测规则」**
   - 当单元概述与人物状态追踪信息冲突时，以人物前文状态为准
   - 确保人物位置、身份、关系与前文状态追踪信息严格一致
   - 与前文内容紧密衔接，避免剧情跳脱和人物瞬移

**【段落与排版格式 — 硬性要求】**
8. **段落之间必须用空行分隔**：每个自然段结束后，必须留一行空行再开始下一段
   - 禁止出现连续大段文字无隔行（即"长段落"或"一堵墙"式排版）
   - 每个自然段控制在 150-300 字以内，超过 400 字的段落必须拆分
9. **对话独立成段**：每个人物的对话（含引号内的对白）独占一个段落
   - 对话段落的前后应有空行分隔
   - 同一人物连续多句对话可合并为一段，但不同人物的对话必须分属不同段落
10. **场景切换必须用空行+分隔标记**：当叙事场景发生切换（如时间跳跃、地点转换、视角变更）时
    - 用两个连续空行（即一整行空白）作为场景分隔
    - 可选：在场景切换处用 `***` 或 `---` 作为分隔符（放在独立一行，前后各空一行）
11. **格式示例**：

```
（第一段）夕阳西下，孙昭龙踏上了通往关楼的最后一段山路。

（第二段，空行分隔）关楼门前，杨朝栋早已等候多时。他抬眼望向来路，嘴角浮起一丝不易察觉的笑意。

（对话独立段落）"你终于来了。"杨朝栋的声音在暮色中显得格外低沉。

（空行后继续叙述）孙昭龙没有答话，只是缓缓握紧了腰间的剑柄。
```

**请严格按照以上格式排版输出，空行是硬性要求，不许省略。**""")

        # 注入风格指南（文风知识库）
        style_section = ""
        if context and context.style_guide and isinstance(context.style_guide, dict):
            style_library_guide = context.style_guide.get("style_library_guide", {})
            if style_library_guide and isinstance(style_library_guide, dict):
                from app.tools.style_library import format_style_for_prompt
                style_section = format_style_for_prompt(style_library_guide)

        if style_section:
            parts.append(f"""
8. **风格要求（必须严格遵循）**：
{style_section}
请在整个创作过程中始终保持上述文风特征，让读者能清晰感受到风格的独特性。""")

        parts.append(f"\n现在请开始创作整{unit_label}内容：")
        return "\n".join(parts)


# ==================== 模块级辅助函数 ====================

def _get_style_intensity(context) -> float:
    """从上下文中提取风格强度参数

    按优先级从多个可能的位置获取风格强度：
    1. context.config["style_intensity"]
    2. context.config["series_style_intensity"] / ["movie_style_intensity"]
    3. context.style_guide["style_intensity"]
    4. 兜底返回 None（表示未设置）

    Args:
        context: AgentContext 或 None

    Returns:
        float 或 None
    """
    if not context:
        return None

    # 🔴 防御：context.config 可能是非dict类型
    if isinstance(context.config, dict):
        intensity = context.config.get("style_intensity")
        if intensity is not None:
            return float(intensity)

    if context.style_guide and isinstance(context.style_guide, dict):
        intensity = context.style_guide.get("style_intensity")
        if intensity is not None:
            return float(intensity)

    return None
