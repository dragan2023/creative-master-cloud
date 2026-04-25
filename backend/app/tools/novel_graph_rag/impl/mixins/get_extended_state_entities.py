"""NovelKnowledgeGraph - get_extended_state_entitiesMixin"""
from typing import Dict
from typing import List
from typing import Any
import re
import time


class GetExtendedStateEntitiesMixin:
    """get_extended_state_entities功能域"""

    def get_extended_state_entities(
        self,
        entity_type: str = None,
        chapter_num: int = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取扩展状态追踪实体（设施、事件、群体、道具等）

        从知识图谱中提取扩展状态相关的实体，支持全面的一致性追踪。

        Args:
            entity_type: 实体类型（可选，筛选特定类型的实体）
            chapter_num: 章节号（可选，筛选特定章节的实体）

        Returns:
            按类型分组的扩展状态实体字典
        """
        # 扩展状态相关的实体类型
        extended_entity_types = {
            # 设施相关
            "设施", "设施状态变化", "设施归属变更", "设施物理状态",
            # 事件相关
            "事件", "事件状态变化", "事件影响", "事件因果链",
            # 群体相关
            "群体组织", "群体状态变化", "群体成员变动", "群体关系变化",
            # 道具相关
            "道具物品", "道具状态变化", "道具归属变更", "道具功能使用",
            # 世界规则
            "世界规则", "规则引用", "规则例外",
            # 时间线
            "时间节点", "时间流逝",
            # 伏笔
            "伏笔", "伏笔回收"
        }

        result = {
            "facilities": [],          # 设施实体
            "facility_states": [],     # 设施状态变化
            "events": [],              # 事件实体
            "event_states": [],        # 事件状态变化
            "event_effects": [],       # 事件影响
            "groups": [],              # 群体组织
            "group_states": [],        # 群体状态变化
            "group_members": [],       # 群体成员变动
            "items": [],               # 道具物品
            "item_states": [],         # 道具状态变化
            "item_ownerships": [],     # 道具归属变更
            "world_rules": [],         # 世界规则
            "rule_references": [],     # 规则引用
            "time_nodes": [],          # 时间节点
            "time_flows": [],          # 时间流逝
            "foreshadows": [],         # 伏笔
            "foreshadow_resolutions": []  # 伏笔回收
        }

        # 类型映射
        type_mapping = {
            "设施": "facilities",
            "设施状态变化": "facility_states",
            "设施归属变更": "facility_states",
            "设施物理状态": "facility_states",
            "事件": "events",
            "事件状态变化": "event_states",
            "事件影响": "event_effects",
            "事件因果链": "event_effects",
            "群体组织": "groups",
            "群体状态变化": "group_states",
            "群体成员变动": "group_members",
            "群体关系变化": "group_states",
            "道具物品": "items",
            "道具状态变化": "item_states",
            "道具归属变更": "item_ownerships",
            "道具功能使用": "item_states",
            "世界规则": "world_rules",
            "规则引用": "rule_references",
            "规则例外": "rule_references",
            "时间节点": "time_nodes",
            "时间流逝": "time_flows",
            "伏笔": "foreshadows",
            "伏笔回收": "foreshadow_resolutions"
        }

        for node_id, data in self.graph.nodes(data=True):
            entity_type_val = data.get("type", "")

            # 筛选扩展类型
            if entity_type_val not in extended_entity_types:
                continue

            # 筛选特定类型
            if entity_type and entity_type_val != entity_type:
                continue

            # 筛选特定章节
            if chapter_num is not None:
                entity_chapter = data.get("chapter")
                if entity_chapter is not None and entity_chapter != chapter_num:
                    continue

            # 添加到对应的分类
            result_key = type_mapping.get(entity_type_val)
            if result_key:
                result[result_key].append({
                    "id": node_id,
                    "text": data.get("text", ""),
                    "type": entity_type_val,
                    "chapter": data.get("chapter"),
                    "description": data.get("description", ""),
                    "attributes": data.get("attributes", {}),
                    "level": data.get("level", "")
                })

        return result


