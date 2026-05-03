"""
多Agent协作文学作品生成系统 - 结构师Agent 提示词模块

从 structural_agent.py 拆分，包含系统提示词和用户提示词模板。

@date: 2026-04-24
@version: v2.0.0
"""

from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import AgentContext


class StructuralPromptsMixin:
    """结构师Agent提示词构建 Mixin"""

    # 系统提示词模板
    SYSTEM_PROMPT_TEMPLATE = """# 角色定义

你是【结构师Agent】，一位专业的叙事结构设计师。你的职责是将文学作品的一个单元（章节或剧集）拆解为多个连贯的场景。

## 核心职责

1. **场景拆解**：将一个单元的内容合理拆分为3-6个场景
2. **结构设计**：为每个场景设计清晰的叙事目标和功能定位
3. **节奏把控**：确保场景间的张弛有度，叙事节奏流畅
4. **逻辑衔接**：保证场景之间的因果逻辑和时空连贯性

## 场景设计原则

1. **单一性原则**：每个场景应聚焦于一个核心事件或冲突
2. **递进性原则**：场景之间要有明确的因果推进关系
3. **多样性原则**：场景类型应多样化（对话、动作、内心独白等）
4. **平衡性原则**：场景长度应相对均衡，避免过长或过短

## 输出格式要求

你必须输出严格的JSON格式，包含以下字段：

```json
{
    "scenes": [
        {
            "scene_index": 1,
            "scene_title": "场景标题（简洁有力）",
            "location": "具体地点描述",
            "characters": ["出场角色1", "出场角色2"],
            "event": "核心事件描述（50字以内）",
            "mood": "情绪基调（如：紧张、温馨、悬疑、悲伤等）",
            "word_target": 800,
            "hook": "场景结束时的钩子或悬念"
        }
    ]
}
```

## 场景类型参考

- **开篇场景**：建立情境，引入冲突
- **发展场景**：推进情节，展现人物关系
- **高潮场景**：冲突爆发，情绪顶点
- **转折场景**：意外发生，方向改变
- **收束场景**：问题解决，铺垫下文

## 注意事项

1. 场景数量建议在3-6个之间，根据单元内容复杂度调整
2. 每个场景的字数目标建议500-1500字，总字数符合单元要求
3. 场景标题要简洁有力，能概括场景核心
4. 钩子设计要自然，能有效引导读者继续阅读
5. 角色出场要合理，避免不必要的角色堆砌
"""

    # 用户提示词模板
    USER_PROMPT_TEMPLATE = """# 单元结构分析任务

## 单元信息

- **单元序号**：第{unit_index}章/集
- **单元标题**：{unit_title}
- **单元概述**：{unit_summary}

## 全局上下文

### 作品背景
{global_context}

### 人物档案
{character_profiles}

### 世界观设定
{world_settings}

### 前文内容摘要
{previous_content}

## 人物状态追踪（重要：场景设计时请参考）

### 人物状态快照
{character_state_snapshot}

### 人物关系链
{relationship_summary}

### 人物当前位置
{character_location_info}

### 人物身份/官职
{character_identity_info}

### 活跃人物列表
{active_characters_info}

## 任务要求

请将上述单元拆解为多个场景，要求：

1. **场景数量**：3-6个场景，根据内容复杂度决定
2. **场景设计**：每个场景包含标题、地点、角色、事件、情绪、字数目标、钩子
3. **逻辑连贯**：场景之间要有清晰的因果推进关系
4. **节奏把控**：合理安排紧张场景和舒缓场景的顺序
5. **角色调度**：合理分配角色出场，避免场景过于拥挤或空旷
6. **字数分配**：总字数目标约 {total_word_target} 字，合理分配到各场景
7. **人物状态一致性**：场景中人物的出场位置、身份必须与上述状态追踪信息一致

## 输出要求

请直接输出JSON格式的场景列表，不要包含任何其他说明文字。
"""

    def _build_prompt(self, context: AgentContext) -> List[Dict[str, str]]:
        """构建提示词

        Args:
            context: Agent执行上下文

        Returns:
            List[Dict]: 消息列表
        """
        # 提取单元信息 - 从多个来源获取
        unit_title = context.extra.get("unit_title", f"第{context.unit_index}章")
        unit_summary = context.extra.get("unit_summary", "")

        self.logger.info(f"[StructuralAgent] 单元 {context.unit_index} 初始数据: extra.unit_title={unit_title}, extra.unit_summary_len={len(unit_summary)}")

        # 如果 unit_summary 为空，尝试从其他来源获取
        if not unit_summary:
            # 尝试从 context.config.unit_summaries 获取
            unit_summaries = context.config.get("unit_summaries", {})
            self.logger.info(f"[StructuralAgent] 单元 {context.unit_index}: 尝试从 config.unit_summaries 获取，可用单元数: {len(unit_summaries)}")
            if unit_summaries and isinstance(unit_summaries, dict):
                unit_data = unit_summaries.get(str(context.unit_index)) or unit_summaries.get(context.unit_index)
                if unit_data:
                    if not unit_title or unit_title == f"第{context.unit_index}章":
                        unit_title = unit_data.get("title", unit_title)
                    unit_summary = unit_data.get("summary", "")
                    self.logger.info(f"[StructuralAgent] 从 unit_summaries 获取单元 {context.unit_index}: title={unit_title}, summary_len={len(unit_summary)}")
                else:
                    self.logger.warning(f"[StructuralAgent] 单元 {context.unit_index} 在 unit_summaries 中未找到")

            # 如果仍然为空，尝试从 context.outline.chapters 获取
            if not unit_summary and context.outline:
                chapters = context.outline.get("chapters", [])
                self.logger.info(f"[StructuralAgent] 尝试从 outline.chapters 获取，章节数: {len(chapters)}")
                if 0 <= context.unit_index - 1 < len(chapters):
                    chapter = chapters[context.unit_index - 1]
                    if not unit_title or unit_title == f"第{context.unit_index}章":
                        unit_title = chapter.get("title", unit_title)
                    unit_summary = chapter.get("summary", "")
                    self.logger.info(f"[StructuralAgent] 从 outline.chapters 获取单元 {context.unit_index}: title={unit_title}")

        self.logger.info(f"[StructuralAgent] 单元 {context.unit_index} 最终数据: title={unit_title}, summary_len={len(unit_summary)}")

        # 格式化角色档案
        character_profiles_str = self._format_character_profiles(context.character_profiles)

        # 格式化世界观设定
        world_settings_str = self._format_world_settings(context.world_settings)

        # 格式化前文内容（限制长度）
        previous_content = context.previous_content
        if len(previous_content) > 3000:
            previous_content = previous_content[-3000:] + "\n...[前文省略]"

        # 计算字数目标
        total_word_target = context.extra.get("target_words") or context.config.get("words_per_unit") or context.config.get("word_target_per_unit", 3000)

        character_state_snapshot = context.character_state_snapshot or "（暂无人物状态快照）"
        relationship_summary = context.relationship_summary or "（暂无人物关系记录）"

        character_location_info = "（暂无位置信息）"
        if context.character_location_map:
            location_lines = [f"- {name}: {loc}" for name, loc in context.character_location_map.items() if loc]
            if location_lines:
                character_location_info = "\n".join(location_lines)

        character_identity_info = "（暂无身份信息）"
        if context.character_identity_map:
            identity_lines = [f"- {name}: {identity}" for name, identity in context.character_identity_map.items() if identity]
            if identity_lines:
                character_identity_info = "\n".join(identity_lines)

        active_characters_info = "（暂无活跃人物）"
        if context.active_characters:
            active_characters_info = "、".join(context.active_characters)

        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            unit_index=context.unit_index,
            unit_title=unit_title,
            unit_summary=unit_summary or "（无详细概述）",
            global_context=context.global_context or "（无特殊背景设定）",
            character_profiles=character_profiles_str,
            world_settings=world_settings_str or "（无特殊世界观设定）",
            previous_content=previous_content or "（无前文）",
            total_word_target=total_word_target,
            character_state_snapshot=character_state_snapshot,
            relationship_summary=relationship_summary,
            character_location_info=character_location_info,
            character_identity_info=character_identity_info,
            active_characters_info=active_characters_info
        )

        return [
            {"role": "system", "content": self.SYSTEM_PROMPT_TEMPLATE},
            {"role": "user", "content": user_prompt}
        ]

    def _format_character_profiles(self, profiles: List[Dict[str, Any]]) -> str:
        """格式化角色档案

        Args:
            profiles: 角色档案列表

        Returns:
            str: 格式化后的字符串
        """
        if not profiles:
            return "（无详细角色设定）"

        lines = []
        for i, profile in enumerate(profiles, 1):
            name = profile.get("name", f"角色{i}")
            role = profile.get("role", "")
            personality = profile.get("personality", "")
            background = profile.get("background", "")

            lines.append(f"### {name}")
            if role:
                lines.append(f"- **身份**：{role}")
            if personality:
                lines.append(f"- **性格**：{personality}")
            if background:
                lines.append(f"- **背景**：{background}")
            lines.append("")

        return "\n".join(lines)

    def _format_world_settings(self, settings: Dict[str, Any]) -> str:
        """格式化世界观设定

        Args:
            settings: 世界观设定字典

        Returns:
            str: 格式化后的字符串
        """
        if not settings:
            return ""

        lines = []

        if "era" in settings:
            lines.append(f"- **时代背景**：{settings['era']}")
        if "geography" in settings:
            lines.append(f"- **地理环境**：{settings['geography']}")
        if "society" in settings:
            lines.append(f"- **社会结构**：{settings['society']}")
        if "rules" in settings:
            lines.append(f"- **特殊规则**：{settings['rules']}")

        for key, value in settings.items():
            if key not in ["era", "geography", "society", "rules"]:
                lines.append(f"- **{key}**：{value}")

        return "\n".join(lines) if lines else ""
