"""CharacterStateTracker - sync_unit_to_global_graphMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
import re
import time


class SyncUnitToGlobalGraphMixin:
    """sync_unit_to_global_graph功能域"""

    def sync_unit_to_global_graph(
        self,
        global_graph,
        unit_graph,
        chapter_num: int,
        sync_extended_entities: bool = True
    ) -> Dict[str, Any]:
        """将单元图谱的实体同步到全局知识图谱

        将章节级别的人物状态变化合并到全局图谱，确保全局图谱反映最新故事状态。
        实现正文优先原则：以正文内容为准更新知识图谱。

        增强功能：
        1. 支持扩展实体同步（设施、事件、群体、道具、伏笔等）
        2. 新实体自动检测与合并
        3. 实体信息增量更新
        4. 关系网络同步

        Args:
            global_graph: 全局知识图谱实例
            unit_graph: 单元知识图谱实例
            chapter_num: 章节号
            sync_extended_entities: 是否同步扩展实体（默认True）

        Returns:
            同步结果摘要，包含更新数量和冲突信息
        """
        result = {
            "chapter": chapter_num,
            "entities_synced": 0,
            "relations_synced": 0,
            "profiles_updated": 0,
            "new_entities": [],
            "extended_entities_synced": {
                "facilities": 0,
                "events": 0,
                "groups": 0,
                "items": 0,
                "foreshadows": 0,
                "world_rules": 0,
                "time_nodes": 0
            },
            "conflicts": []
        }

        try:
            # 1. 获取单元图谱中的所有实体
            unit_entities = self._get_all_entities_from_graph(unit_graph)
            unit_relations = self._get_all_relations_from_graph(unit_graph)

            # 2. 将实体同步到全局图谱
            for entity in unit_entities:
                entity_type = entity.get("type", "")
                entity_text = entity.get("text", "")

                # 检查是否为新实体（全局图谱中不存在）
                is_new_entity = not self._entity_exists_in_graph(
                    global_graph, entity_text)

                # 跳过人物设定实体（这些会被动态更新）
                if entity_type == "人物设定":
                    continue

                # 同步实体
                global_graph.add_entity(
                    entity, doc_id=f"chapter_{chapter_num}")
                result["entities_synced"] += 1

                # 记录新实体
                if is_new_entity:
                    result["new_entities"].append({
                        "text": entity_text,
                        "type": entity_type,
                        "chapter": chapter_num
                    })

                # 统计扩展实体
                if sync_extended_entities:
                    self._count_extended_entity(result, entity_type)

            # 3. 将关系同步到全局图谱
            for relation in unit_relations:
                global_graph.add_relation(
                    relation, doc_id=f"chapter_{chapter_num}")
                result["relations_synced"] += 1

            # 4. 检测冲突并更新人物设定
            conflicts = self._detect_and_resolve_conflicts(
                global_graph, unit_entities, chapter_num)
            result["conflicts"] = conflicts
            result["profiles_updated"] = len(
                [c for c in conflicts if c.get("resolved")])

            # 5. 同步扩展实体的关系网络
            if sync_extended_entities:
                self._sync_extended_relations(
                    global_graph, unit_graph, chapter_num, result)

            # 6. 保存全局图谱
            global_graph.save()

            # 7. 记录同步日志
            new_entity_count = len(result["new_entities"])
            self.logger.info(
                f"单元图谱同步到全局图谱完成: 章节{chapter_num}, "
                f"实体={result['entities_synced']}, 关系={result['relations_synced']}, "
                f"新实体={new_entity_count}, 设定更新={result['profiles_updated']}, 冲突={len(result['conflicts'])}")

            # 如果有新实体，记录详细信息
            if result["new_entities"]:
                self.logger.info(
                    f"检测到新实体: {[e['text'] for e in result['new_entities'][:10]]}")

        except Exception as e:
            self.logger.error(f"同步单元图谱到全局图谱失败: {e}")

        return result


    def _get_all_entities_from_graph(self, knowledge_graph) -> List[Dict[str, Any]]:
        """从知识图谱中获取所有实体

        Args:
            knowledge_graph: NovelKnowledgeGraph实例

        Returns:
            实体列表
        """
        entities = []
        try:
            # 遍历图谱中的所有节点
            import networkx as nx
            graph = knowledge_graph.graph

            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("type") in ["人物", "身份变化", "位置变化", "关系变化",
                                             "性格发展", "能力成长", "心理状态", "行为模式",
                                             "设施", "事件", "群体组织", "道具物品",
                                             "伏笔", "世界规则", "时间节点"]:
                    entity = {
                        "text": node_data.get("text", node_id),
                        "type": node_data.get("type", ""),
                        "level": node_data.get("level", "micro"),
                        "chapter": node_data.get("chapter"),
                        "description": node_data.get("description", ""),
                        "attributes": node_data.get("attributes", {})
                    }
                    if node_data.get("character"):
                        entity["character"] = node_data.get("character")
                    entities.append(entity)

        except Exception as e:
            self.logger.error(f"获取图谱实体失败: {e}")

        return entities


    def _get_all_relations_from_graph(self, knowledge_graph) -> List[Dict[str, Any]]:
        """从知识图谱中获取所有关系

        Args:
            knowledge_graph: NovelKnowledgeGraph实例

        Returns:
            关系列表
        """
        relations = []
        try:
            graph = knowledge_graph.graph

            for source, target, edge_data in graph.edges(data=True):
                relation = {
                    "source": source,
                    "target": target,
                    "relation": edge_data.get("relation", "关联"),
                    "context": edge_data.get("context", ""),
                    "chapter": edge_data.get("chapter")
                }
                relations.append(relation)

        except Exception as e:
            self.logger.error(f"获取图谱关系失败: {e}")

        return relations


    def _entity_exists_in_graph(self, knowledge_graph, entity_text: str) -> bool:
        """检查实体是否存在于知识图谱中

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            entity_text: 实体文本

        Returns:
            是否存在
        """
        try:
            # 使用实体索引快速查找
            if hasattr(knowledge_graph, 'entity_index'):
                return entity_text in knowledge_graph.entity_index

            # 回退到遍历查找
            graph = knowledge_graph.graph
            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("text") == entity_text:
                    return True
            return False

        except Exception as e:
            self.logger.error(f"检查实体存在失败: {entity_text}, {e}")
            return False


    def _count_extended_entity(self, result: Dict[str, Any], entity_type: str) -> None:
        """统计扩展实体类型

        Args:
            result: 结果字典
            entity_type: 实体类型
        """
        extended_counts = result["extended_entities_synced"]

        # 设施相关
        if entity_type in ["设施", "设施状态变化", "设施归属变更", "设施物理状态"]:
            extended_counts["facilities"] += 1
        # 事件相关
        elif entity_type in ["事件", "事件状态变化", "事件影响", "事件因果链", "详细事件"]:
            extended_counts["events"] += 1
        # 群体相关
        elif entity_type in ["群体组织", "群体状态变化", "群体成员变动", "群体关系变化"]:
            extended_counts["groups"] += 1
        # 道具相关
        elif entity_type in ["道具物品", "道具状态变化", "道具归属变更", "道具功能使用"]:
            extended_counts["items"] += 1
        # 伏笔相关
        elif entity_type in ["伏笔", "伏笔回收"]:
            extended_counts["foreshadows"] += 1
        # 世界规则相关
        elif entity_type in ["世界规则", "规则引用", "规则例外", "世界观规则"]:
            extended_counts["world_rules"] += 1
        # 时间节点相关
        elif entity_type in ["时间节点", "时间流逝"]:
            extended_counts["time_nodes"] += 1


    def _sync_extended_relations(
        self,
        global_graph,
        unit_graph,
        chapter_num: int,
        result: Dict[str, Any]
    ) -> None:
        """同步扩展实体的关系网络

        确保扩展实体之间的关系也被同步到全局图谱。
        包括：
        - 人物与设施的归属关系
        - 事件与人物的参与关系
        - 群体与人物的关系
        - 道具与人物的持有关系
        - 伏笔与事件的关联关系

        Args:
            global_graph: 全局知识图谱
            unit_graph: 单元知识图谱
            chapter_num: 章节号
            result: 结果字典
        """
        try:
            # 定义需要特别处理的关系类型
            extended_relation_types = {
                "属于", "拥有", "持有", "使用", "参与", "引发",
                "导致", "关联", "关联人物", "发生于", "触发于"
            }

            graph = unit_graph.graph
            synced_count = 0

            for source, target, edge_data in graph.edges(data=True):
                relation_type = edge_data.get("relation", "")

                # 只处理扩展关系类型
                if relation_type not in extended_relation_types:
                    continue

                # 检查源节点和目标节点类型
                source_data = graph.nodes.get(source, {})
                target_data = graph.nodes.get(target, {})

                source_type = source_data.get("type", "")
                target_type = target_data.get("type", "")

                # 扩展实体相关的关系
                extended_types = {
                    "设施", "事件", "群体组织", "道具物品", "伏笔",
                    "世界规则", "时间节点", "详细事件"
                }

                if source_type in extended_types or target_type in extended_types:
                    # 构建关系数据
                    relation_data = {
                        "source": source_data.get("text", source),
                        "target": target_data.get("text", target),
                        "relation": relation_type,
                        "context": edge_data.get("context", ""),
                        "chapter": chapter_num
                    }

                    # 同步到全局图谱
                    global_graph.add_relation(
                        relation_data, doc_id=f"chapter_{chapter_num}")
                    synced_count += 1

            if synced_count > 0:
                self.logger.info(f"同步扩展关系: {synced_count}条")

        except Exception as e:
            self.logger.error(f"同步扩展关系失败: {e}")


    def _detect_and_resolve_conflicts(
        self,
        global_graph,
        unit_entities: List[Dict[str, Any]],
        chapter_num: int
    ) -> List[Dict[str, Any]]:
        """检测并解决正文内容与初始设定的冲突

        实现正文优先原则：
        1. 检测正文中的状态变化与初始设定是否冲突
        2. 以正文为准更新全局图谱中的人物设定
        3. 记录冲突信息用于报告

        Args:
            global_graph: 全局知识图谱
            unit_entities: 单元图谱中的实体列表
            chapter_num: 章节号

        Returns:
            检测到的冲突列表
        """
        conflicts = []

        try:
            # 按人物分组实体
            character_entities = {}
            for entity in unit_entities:
                char_name = entity.get("character", "")
                if char_name:
                    if char_name not in character_entities:
                        character_entities[char_name] = []
                    character_entities[char_name].append(entity)

            # 检测每个有变化的人物的冲突
            for char_name, entities in character_entities.items():
                # 获取初始设定
                initial_profile = self._get_character_profile_from_graph(
                    global_graph, char_name)

                if not initial_profile:
                    continue

                # 检测各类冲突
                for entity in entities:
                    entity_type = entity.get("type", "")
                    entity_text = entity.get("text", "")

                    conflict = None

                    # 身份变化冲突检测
                    if entity_type == "身份变化":
                        initial_identity = initial_profile.get(
                            "attributes", {}).get("身份", "")
                        if initial_identity and initial_identity != entity_text:
                            conflict = {
                                "character": char_name,
                                "type": "身份变化",
                                "initial_value": initial_identity,
                                "new_value": entity_text,
                                "chapter": chapter_num,
                                "description": f"{char_name}的身份从'{initial_identity}'变为'{entity_text}'",
                                "resolved": True
                            }
                            # 更新人物设定
                            self._update_character_profile_in_graph(
                                global_graph, char_name,
                                {"身份": entity_text}, chapter_num)

                    # 位置变化冲突检测
                    elif entity_type == "位置变化":
                        initial_location = initial_profile.get(
                            "attributes", {}).get("初始位置", "")
                        if initial_location and initial_location != entity_text:
                            conflict = {
                                "character": char_name,
                                "type": "位置变化",
                                "initial_value": initial_location,
                                "new_value": entity_text,
                                "chapter": chapter_num,
                                "description": f"{char_name}的位置从'{initial_location}'变为'{entity_text}'",
                                "resolved": True
                            }
                            # 更新人物设定
                            self._update_character_profile_in_graph(
                                global_graph, char_name,
                                {"当前位置": entity_text}, chapter_num)

                    # 性格发展冲突检测
                    elif entity_type == "性格发展":
                        initial_personality = initial_profile.get(
                            "attributes", {}).get("性格特点", "")
                        if initial_personality:
                            conflict = {
                                "character": char_name,
                                "type": "性格发展",
                                "initial_value": initial_personality,
                                "new_value": entity.get("description", entity_text),
                                "chapter": chapter_num,
                                "description": f"{char_name}的性格有所发展",
                                "resolved": True
                            }
                            # 追加性格发展记录
                            self._append_character_attribute_in_graph(
                                global_graph, char_name, "性格发展记录",
                                f"第{chapter_num}章: {entity.get('description', entity_text)}")

                    if conflict:
                        conflicts.append(conflict)

            if conflicts:
                self.logger.info(
                    f"检测到 {len(conflicts)} 个设定冲突，已按正文内容更新全局图谱")

        except Exception as e:
            self.logger.error(f"检测冲突失败: {e}")

        return conflicts


    def _get_character_profile_from_graph(
        self,
        knowledge_graph,
        char_name: str
    ) -> Optional[Dict[str, Any]]:
        """从知识图谱中获取人物设定

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            char_name: 人物名称

        Returns:
            人物设定字典，如果不存在返回None
        """
        try:
            graph = knowledge_graph.graph

            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("type") == "人物设定" and node_data.get("text") == char_name:
                    return {
                        "text": node_id,
                        "type": node_data.get("type"),
                        "description": node_data.get("description", ""),
                        "attributes": node_data.get("attributes", {})
                    }
        except Exception as e:
            self.logger.error(f"获取人物设定失败: {char_name}, {e}")

        return None


