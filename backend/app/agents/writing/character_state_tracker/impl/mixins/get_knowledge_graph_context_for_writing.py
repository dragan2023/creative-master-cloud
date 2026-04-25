"""CharacterStateTracker - get_knowledge_graph_context_for_writingMixin"""
from __future__ import annotations
import re


class GetKnowledgeGraphContextForWritingMixin:
    """get_knowledge_graph_context_for_writing功能域"""

    def get_knowledge_graph_context_for_writing(
        self,
        chapter_num: int = None,
        max_entities: int = 30
    ) -> str:
        """获取前文知识图谱参考信息用于写作（架构优化新增）

        将追踪器中积累的人物状态、关系变化、位置变化等信息
        格式化为知识图谱参考文本，供写作Agent参考。

        Args:
            chapter_num: 当前章节号
            max_entities: 最大实体数量

        Returns:
            格式化的知识图谱参考文本
        """
        lines = ["# 前文知识图谱参考（架构优化版）", ""]
        lines.append("以下是从前文中提取的核心信息，请在创作时保持一致性：")
        lines.append("")

        # 1. 人物状态汇总
        lines.append("## 人物状态汇总")
        lines.append("")

        entity_count = 0
        for char_name, state in self._character_states.items():
            if entity_count >= max_entities:
                break

            # 只显示最近5章内出场的人物
            if state.last_appearance:
                if chapter_num and (chapter_num - state.last_appearance) > 5:
                    continue

            lines.append(f"### {char_name}")

            if state.identity:
                lines.append(f"- 当前身份: {state.identity}")
                entity_count += 1
            if state.location:
                lines.append(f"- 当前位置: {state.location}")
                entity_count += 1
            if state.status_change:
                lines.append(f"- 最近变化: {state.status_change}")
                entity_count += 1

            lines.append("")

        # 2. 人物关系网络
        if self._relationship_history:
            lines.append("## 人物关系网络")
            lines.append("")

            for rel_change in self._relationship_history[-10:]:  # 最近10条关系变化
                lines.append(
                    f"- {rel_change.character1} ↔ {rel_change.character2}: "
                    f"{rel_change.new_state or rel_change.relationship_type}"
                )
                entity_count += 1
                if entity_count >= max_entities:
                    break
            lines.append("")

        # 3. 已知地点
        if self._known_locations:
            lines.append("## 已知地点")
            lines.append(", ".join(list(self._known_locations)[:20]))
            lines.append("")

        # 4. 章节快照历史
        if self._chapter_snapshots:
            recent_snapshots = sorted(
                self._chapter_snapshots.items(),
                key=lambda x: x[0],
                reverse=True
            )[:3]  # 最近3章

            if recent_snapshots:
                lines.append("## 近期章节人物状态")
                lines.append("")

                for snap_chapter, snapshot in recent_snapshots:
                    if chapter_num and snap_chapter >= chapter_num:
                        continue
                    chars = list(snapshot.characters.keys())[:5]  # 最多显示5个人物
                    if chars:
                        lines.append(
                            f"- 第{snap_chapter}章出场: {', '.join(chars)}")

        return "\n".join(lines)


