"""CharacterStateTracker - export_to_knowledge_graphMixin"""
from __future__ import annotations
import re


class ExportToKnowledgeGraphMixin:
    """export_to_knowledge_graph功能域"""

    def export_to_knowledge_graph(self, knowledge_graph, chapter_num: int = None, only_appeared: bool = True) -> None:
        """导出人物状态到知识图谱

        将追踪器中的人物状态变化导出到知识图谱中作为实体存储。
        通常在章节生成完成后调用。

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            chapter_num: 章节号
            only_appeared: 是否只导出本章节登场的人物（默认True）
                - True: 只导出 last_appearance == chapter_num 的人物（用于单元图谱）
                - False: 导出所有人物（用于全局图谱）
        """
        try:
            entity_count = 0
            relation_count = 0
            appeared_count = 0  # 统计实际登场人物数

            for char_name, state in self._character_states.items():
                # 【关键修复】单元图谱只导出本章节实际登场的人物
                # 判断标准：last_appearance == chapter_num 表示本章节登场
                if only_appeared and chapter_num is not None:
                    if state.last_appearance != chapter_num:
                        # 该人物本章节未登场，跳过
                        self.logger.debug(
                            f"跳过未登场人物: {char_name}, last_appearance={state.last_appearance}, current_chapter={chapter_num}")
                        continue
                    appeared_count += 1

                # 导出人物实体（始终导出，确保图谱有基础节点）
                knowledge_graph.add_entity({
                    "text": char_name,
                    "type": "人物",
                    "level": "macro",
                    "description": f"身份: {state.identity or '未知'}，位置: {state.location or '未知'}"
                }, doc_id=f"chapter_{chapter_num}")
                entity_count += 1

                # 导出身份变化（有变化时才记录）
                if state.status_change and state.identity:
                    knowledge_graph.add_entity({
                        "text": state.identity,
                        "type": "身份变化",
                        "level": "micro",
                        "character": char_name,
                        "chapter": chapter_num or state.last_appearance,
                        "description": state.status_change
                    }, doc_id=f"chapter_{chapter_num}")
                    entity_count += 1

                    # 添加身份变化关系
                    knowledge_graph.add_relation({
                        "source": char_name,
                        "target": state.identity,
                        "relation": "身份转变为",
                        "context": state.status_change
                    }, doc_id=f"chapter_{chapter_num}")
                    relation_count += 1

                # 导出位置变化
                if state.location:
                    knowledge_graph.add_entity({
                        "text": state.location,
                        "type": "位置变化",
                        "level": "micro",
                        "character": char_name,
                        "chapter": chapter_num or state.last_appearance,
                        "description": f"当前位置: {state.location}"
                    }, doc_id=f"chapter_{chapter_num}")
                    entity_count += 1

                    # 添加位置关系
                    knowledge_graph.add_relation({
                        "source": char_name,
                        "target": state.location,
                        "relation": "位于",
                        "context": f"第{chapter_num or state.last_appearance}章位置"
                    }, doc_id=f"chapter_{chapter_num}")
                    relation_count += 1

                # 导出关系变化
                for related_char, relation in state.relationships.items():
                    knowledge_graph.add_entity({
                        "text": f"{char_name}与{related_char}",
                        "type": "关系变化",
                        "level": "micro",
                        "character": char_name,
                        "chapter": chapter_num or state.last_appearance,
                        "description": relation
                    }, doc_id=f"chapter_{chapter_num}")
                    entity_count += 1

                    # 添加关系边
                    knowledge_graph.add_relation({
                        "source": char_name,
                        "target": related_char,
                        "relation": "关联人物",
                        "context": relation
                    }, doc_id=f"chapter_{chapter_num}")
                    relation_count += 1

                # 导出性格发展、能力成长、心理状态、行为模式（存储在attributes中）
                attr_type_mapping = {
                    "性格发展": "性格发展",
                    "心理状态": "心理状态",
                    "能力成长": "能力成长",
                    "行为模式": "行为模式"
                }
                for attr_key, entity_type in attr_type_mapping.items():
                    attr_value = state.attributes.get(
                        attr_key, "") or state.attributes.get(attr_key.lower(), "")
                    if attr_value:
                        knowledge_graph.add_entity({
                            "text": attr_value if len(attr_value) <= 20 else attr_value[:20],
                            "type": entity_type,
                            "level": "micro",
                            "character": char_name,
                            "chapter": chapter_num or state.last_appearance,
                            "description": attr_value
                        }, doc_id=f"chapter_{chapter_num}")
                        entity_count += 1

            # 构建日志信息
            if only_appeared and chapter_num is not None:
                self.logger.info(
                    f"导出人物状态到单元图谱完成: 章节{chapter_num}, "
                    f"本章节登场人物={appeared_count}个, "
                    f"总实体={entity_count}个, 关系={relation_count}条 "
                    f"(已过滤{len(self._character_states) - appeared_count}个未登场人物)")
            else:
                self.logger.info(
                    f"导出人物状态到知识图谱完成: 章节{chapter_num}, "
                    f"{len(self._character_states)}个人物, "
                    f"{entity_count}个实体, {relation_count}个关系")

        except Exception as e:
            self.logger.error(f"导出人物状态到知识图谱失败: {e}")


