"""ProjectKnowledgeBase - sync_unit_entities_to_globalMixin"""
from typing import Dict
from typing import Any
import re
import os
import time


class SyncUnitEntitiesToGlobalMixin:
    """sync_unit_entities_to_global功能域"""

    async def sync_unit_entities_to_global(
        self,
        project_id: int,
        unit_number: int,
        character_tracker=None
    ) -> Dict[str, Any]:
        """
        将单元图谱的实体增量同步到全局知识图谱

        在章节生成后自动调用，确保新出现的实体和关系及时同步到全局图谱。
        实现"正文优先"原则：以正文内容为准更新全局知识。

        Args:
            project_id: 项目ID
            unit_number: 单元号（章节号）
            character_tracker: 人物状态追踪器（可选，用于更智能的同步）

        Returns:
            同步结果摘要
        """
        result = {
            "success": False,
            "project_id": project_id,
            "unit_number": unit_number,
            "entities_synced": 0,
            "relations_synced": 0,
            "new_entities": [],
            "extended_entities": {
                "facilities": 0,
                "events": 0,
                "groups": 0,
                "items": 0,
                "foreshadows": 0,
                "world_rules": 0,
                "time_nodes": 0
            },
            "error": None
        }

        try:
            # 1. 加载全局图谱
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if not os.path.exists(global_graph_path):
                self.logger.warning(f"全局图谱不存在: {global_graph_path}")
                result["error"] = "全局图谱不存在"
                return result

            global_graph = NovelKnowledgeGraph(persist_path=global_graph_path)
            if not global_graph.load():
                result["error"] = "加载全局图谱失败"
                return result

            # 2. 加载单元图谱
            unit_graph_path = self.get_graph_path(project_id, unit_number)
            if not os.path.exists(unit_graph_path):
                self.logger.info(f"单元图谱不存在，跳过同步: {unit_graph_path}")
                result["error"] = "单元图谱不存在"
                return result

            unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
            if not unit_graph.load():
                result["error"] = "加载单元图谱失败"
                return result

            # 3. 使用CharacterStateTracker进行智能同步
            if character_tracker:
                sync_result = character_tracker.sync_unit_to_global_graph(
                    global_graph=global_graph,
                    unit_graph=unit_graph,
                    chapter_num=unit_number,
                    sync_extended_entities=True
                )
                result["entities_synced"] = sync_result.get(
                    "entities_synced", 0)
                result["relations_synced"] = sync_result.get(
                    "relations_synced", 0)
                result["new_entities"] = sync_result.get("new_entities", [])
                result["extended_entities"] = sync_result.get(
                    "extended_entities_synced", {})
            else:
                # 简单同步逻辑（无追踪器时）
                result = self._simple_sync_entities(
                    global_graph, unit_graph, unit_number, result)

            result["success"] = True

            self.logger.info(
                f"单元图谱增量同步完成: project={project_id}, unit={unit_number}, "
                f"实体={result['entities_synced']}, 关系={result['relations_synced']}, "
                f"新实体={len(result['new_entities'])}")

        except Exception as e:
            self.logger.error(
                f"增量同步失败: project={project_id}, unit={unit_number}, error={str(e)}")
            result["error"] = str(e)

        return result


    def _simple_sync_entities(
        self,
        global_graph,
        unit_graph,
        unit_number: int,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        简单实体同步逻辑（无追踪器时使用）

        Args:
            global_graph: 全局知识图谱
            unit_graph: 单元知识图谱
            unit_number: 单元号
            result: 结果字典

        Returns:
            更新后的结果字典
        """
        try:
            # 遍历单元图谱中的所有实体
            for node_id, node_data in unit_graph.graph.nodes(data=True):
                entity_text = node_data.get("text", "")
                entity_type = node_data.get("type", "")

                # 检查是否为新实体
                is_new = entity_text not in global_graph.entity_index

                # 同步到全局图谱
                entity_data = {
                    "text": entity_text,
                    "type": entity_type,
                    "level": node_data.get("level", "micro"),
                    "description": node_data.get("description", ""),
                    "attributes": node_data.get("attributes", {}),
                    "chapter": node_data.get("chapter", unit_number)
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{unit_number}")
                result["entities_synced"] += 1

                if is_new:
                    result["new_entities"].append({
                        "text": entity_text,
                        "type": entity_type,
                        "chapter": unit_number
                    })

                # 统计扩展实体
                self._count_extended_entity_type(result, entity_type)

            # 遍历单元图谱中的所有关系
            for source, target, edge_data in unit_graph.graph.edges(data=True):
                source_data = unit_graph.graph.nodes.get(source, {})
                target_data = unit_graph.graph.nodes.get(target, {})

                relation_data = {
                    "source": source_data.get("text", source),
                    "target": target_data.get("text", target),
                    "relation": edge_data.get("relation", "关联"),
                    "context": edge_data.get("context", "")
                }
                global_graph.add_relation(
                    relation_data, doc_id=f"chapter_{unit_number}")
                result["relations_synced"] += 1

            # 保存全局图谱
            global_graph.save()

        except Exception as e:
            self.logger.error(f"简单同步失败: {e}")

        return result


    def _count_extended_entity_type(self, result: Dict[str, Any], entity_type: str) -> None:
        """统计扩展实体类型"""
        extended = result["extended_entities"]

        type_mapping = {
            # 设施
            ("设施", "设施状态变化", "设施归属变更", "设施物理状态"): "facilities",
            # 事件
            ("事件", "事件状态变化", "事件影响", "事件因果链", "详细事件"): "events",
            # 群体
            ("群体组织", "群体状态变化", "群体成员变动", "群体关系变化"): "groups",
            # 道具
            ("道具物品", "道具状态变化", "道具归属变更", "道具功能使用"): "items",
            # 伏笔
            ("伏笔", "伏笔回收"): "foreshadows",
            # 世界规则
            ("世界规则", "规则引用", "规则例外", "世界观规则"): "world_rules",
            # 时间节点
            ("时间节点", "时间流逝"): "time_nodes"
        }

        for types, key in type_mapping.items():
            if entity_type in types:
                extended[key] += 1
                break


