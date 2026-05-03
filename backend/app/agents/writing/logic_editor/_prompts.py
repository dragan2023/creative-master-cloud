"""
逻辑编辑Agent - 提示词格式化 Mixin

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Any, Dict, List


class LogicPromptsMixin:
    """提示词格式化 Mixin"""

    def _format_detected_issues(self, issues: List[Dict]) -> str:
        """格式化检测到的问题列表"""
        if not issues:
            return "未检测到逻辑问题"
        formatted = []
        for i, issue in enumerate(issues, 1):
            issue_type = issue.get("type", "未知类型")
            severity = issue.get("severity", "未知")
            location = issue.get("location", "未知位置")
            description = issue.get("description", "无描述")
            conflict_with = issue.get("conflict_with", "无")
            impact = issue.get("impact", "无")
            formatted.append(
                f"【问题{i}】\n"
                f"类型: {issue_type}\n"
                f"严重程度: {severity}\n"
                f"位置: {location}\n"
                f"描述: {description}\n"
                f"冲突对象: {conflict_with}\n"
                f"影响: {impact}"
            )
        return "\n\n".join(formatted)

    def _format_global_outline(self, outline: Dict) -> str:
        """格式化全局大纲"""
        if not outline:
            return "无全局大纲"
        title = outline.get("title", "")
        summary = outline.get("summary", "")
        world_setting = outline.get("world_setting", "")
        lines = []
        if title:
            lines.append(f"标题: {title}")
        if summary:
            lines.append(f"概要: {summary}")
        if world_setting:
            lines.append(f"世界观: {world_setting}")
        return "\n".join(lines) if lines else "无全局大纲"

    def _format_character_profiles(self, profiles: List[Dict]) -> str:
        """格式化角色档案"""
        if not profiles:
            return "无角色设定"
        formatted = []
        for profile in profiles:
            name = profile.get("name", "未知")
            personality = profile.get("personality", "")
            background = profile.get("background", "")
            traits = profile.get("traits", [])
            lines = [f"【{name}】"]
            if personality:
                lines.append(f"  性格: {personality}")
            if background:
                lines.append(f"  背景: {background}")
            if traits:
                lines.append(f"  特征: {', '.join(traits)}")
            formatted.append("\n".join(lines))
        return "\n\n".join(formatted)

    def _format_previous_scenes(self, scenes: List[Dict]) -> str:
        """格式化前文场景"""
        if not scenes:
            return "无前文场景"
        formatted = []
        for i, scene in enumerate(scenes, 1):
            title = scene.get("title", f"场景{i}")
            summary = scene.get("summary", "")
            key_events = scene.get("key_events", [])
            lines = [f"{i}. {title}"]
            if summary:
                lines.append(f"   摘要: {summary}")
            if key_events:
                lines.append(f"   关键事件: {', '.join(key_events)}")
            formatted.append("\n".join(lines))
        return "\n\n".join(formatted)

    def _format_outline(self, outline: Dict) -> str:
        """格式化大纲"""
        if not outline:
            return "无大纲信息"
        title = outline.get("title", "")
        summary = outline.get("summary", "")
        lines = []
        if title:
            lines.append(f"标题: {title}")
        if summary:
            lines.append(f"概要: {summary}")
        return "\n".join(lines) if lines else "无大纲信息"
