"""
多Agent协作文学作品生成系统 - 写手Agent 工具模块

从 writer_agent.py 拆分，包含内容清理和摘要生成方法。

@date: 2026-04-24
@version: v2.0.0
"""

import re


class WriterUtilsMixin:
    """写手Agent工具方法 Mixin

    提供内容清理和摘要生成等辅助功能。
    """

    def _clean_content(self, content: str) -> str:
        """清理生成的内容

        移除可能的markdown格式和其他多余标记，清理人物状态追踪信息。

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        # 移除markdown代码块标记
        if content.startswith("```"):
            # 找到第一个换行
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1:]

        if content.endswith("```"):
            content = content[:-3]

        # 移除可能的人物状态追踪信息（这些信息不应该出现在正文中）
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
        # 返回完整场景内容
        return f"【{scene_title}】{content}"
