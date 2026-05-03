"""
风格润色Agent - 提示词构建 Mixin

包含 style_editor_agent.py 中的提示词构建相关方法。

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Any, Dict, List, Tuple


class StyleEditorPromptsMixin:
    """提示词构建 Mixin"""

    def _build_style_library_polish_prompt(
        self,
        content: str,
        style_library_guide: Dict,
        logic_issues: List[Dict],
        character_profiles: List[Dict]
    ) -> Tuple[str, str]:
        """构建基于文风知识库的风格润色提示词"""
        from app.tools.style_library import format_style_for_prompt

        system_prompt = """你是一位资深的文学编辑和文风专家，擅长根据指定的文学风格进行精准润色。

## 核心职责

1. **风格对齐**：确保文本严格符合指定的文风特征
2. **语言润色**：提升文字表现力，保持风格一致性
3. **逻辑修正**：修复逻辑问题，保持情节连贯
4. **对话优化**：使对话符合角色身份和文风要求
5. **描写增强**：增强场景描写的画面感和风格特征

## 润色原则

- **风格优先**：所有修改必须服务于目标文风
- **保留原意**：不改变核心情节和人物关系
- **精准调整**：针对性调整词汇、句式、叙事节奏
- **自然流畅**：润色后的文本必须自然，不生硬"""

        style_section = format_style_for_prompt(style_library_guide)

        user_prompt = f"""请根据以下文风要求对内容进行精准润色。

## 目标文风（**必须严格遵循**）

{style_section}

## 待润色内容

{content}

## 逻辑问题修正（如有）

{self._format_logic_issues(logic_issues)}

## 角色设定（用于优化对话）

{self._format_character_profiles(character_profiles)}

## 润色要求

1. **词汇层面**
   - 根据文风特征调整用词偏好
   - 使用标志性词汇和特色表达
   - 避免文风要求中明确禁止的词汇

2. **句式层面**
   - 调整句子长度比例（如极简主义用短句，浪漫主义用长句）
   - 使用偏好句式结构
   - 控制标点使用风格

3. **叙事层面**
   - 确保叙事视角符合文风要求
   - 调整叙事节奏（快速/缓慢/跳跃/平稳）
   - 优化时空处理方式

4. **描写层面**
   - 强化文风指定的描写重点
   - 调整感官描写的比例和方式
   - 运用文风偏好的修辞手法

5. **对话层面**
   - 使对话符合文风的整体特征
   - 调整对话密度和功能性
   - 增强角色语言的个性化

## 输出格式

```json
{{
    "polished_content": "润色后的完整内容",
    "changes_summary": "修改摘要，重点说明风格对齐的改动",
    "word_count": 1200,
    "style_alignment_score": 90,
    "style_adjustments": [
        {{
            "dimension": "词汇|句式|叙事|描写|对话",
            "original": "原文特征",
            "adjusted": "调整后特征",
            "reason": "调整原因"
        }}
    ]
}}
```

请直接输出JSON格式的润色结果。"""

        return system_prompt, user_prompt

    def _format_style_guide(self, style_guide: Dict, style_document_features: str = "") -> str:
        """格式化风格指南"""
        lines = []

        if style_guide:
            if "genre" in style_guide:
                lines.append(f"体裁: {style_guide['genre']}")
            if "tone" in style_guide:
                lines.append(f"基调: {style_guide['tone']}")
            if "narrative_style" in style_guide:
                lines.append(f"叙事风格: {style_guide['narrative_style']}")
            if "language_style" in style_guide:
                lines.append(f"语言风格: {style_guide['language_style']}")
            if "style_reference" in style_guide and style_guide["style_reference"]:
                lines.append(
                    f"风格参考: {style_guide['style_reference'][:500]}...")
            if "special_requirements" in style_guide:
                reqs = style_guide["special_requirements"]
                if isinstance(reqs, list):
                    lines.append(f"特殊要求: {'; '.join(reqs)}")
                else:
                    lines.append(f"特殊要求: {reqs}")

        if style_document_features:
            lines.append(f"\n【文风文档特征】\n{style_document_features}")

        return "\n".join(lines) if lines else "无特定风格要求，保持原文风格即可"

    def _format_logic_issues(self, issues: List[Dict]) -> str:
        """格式化逻辑问题"""
        if not issues:
            return "无逻辑问题需要修正"

        formatted = []
        for i, issue in enumerate(issues, 1):
            issue_type = issue.get("type", "未知类型")
            severity = issue.get("severity", "medium")
            description = issue.get("description", "")
            suggestion = issue.get("suggestion", "")

            lines = [f"{i}. [{severity.upper()}] {issue_type}"]
            if description:
                lines.append(f"   问题: {description}")
            if suggestion:
                lines.append(f"   建议: {suggestion}")

            formatted.append("\n".join(lines))

        return "\n\n".join(formatted)

    def _format_character_profiles(self, profiles: List[Dict]) -> str:
        """格式化角色档案"""
        if not profiles:
            return "无角色设定"

        formatted = []
        for profile in profiles:
            name = profile.get("name", "未知")
            voice = profile.get("voice", "")
            personality = profile.get("personality", "")

            lines = [f"【{name}】"]
            if voice:
                lines.append(f"  语言特点: {voice}")
            if personality:
                lines.append(f"  性格: {personality}")

            formatted.append("\n".join(lines))

        return "\n\n".join(formatted)
