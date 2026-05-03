"""ProjectKnowledgeBase - sync_unit_entities_to_globalMixin"""
from typing import Dict
from typing import Any
import re
import os
import time

from app.tools.novel_graph_rag.impl.generator import NovelKnowledgeGraph


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
        
        ️ [知识图谱优化 v3.2] 此功能已禁用！
        原因：持续同步导致全局图谱无限膨胀（100章可达3550+实体）
        优化：全局图谱仅保留全局大纲实体（~50个），跨章检索通过向量库实现
        
        保留此方法仅为向后兼容，实际执行时会直接返回并记录警告日志。

        Args:
            project_id: 项目ID
            unit_number: 单元号（章节号）
            character_tracker: 人物状态追踪器（可选，用于更智能的同步）

        Returns:
            同步结果摘要（始终返回success=False，表示未执行同步）
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
            "error": "功能已禁用：全局图谱仅保留大纲级实体，单元实体通过向量库检索"
        }
        
        # 🆕 [知识图谱优化 v3.2] 直接返回，不执行同步
        self.logger.warning(
            f"[知识图谱优化 v3.2] sync_unit_entities_to_global已禁用: "
            f"project_id={project_id}, unit_number={unit_number}, "
            f"原因：防止全局图谱无限膨胀，单元实体通过向量库检索"
        )
        
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


