"""CharacterStateTracker - merge_new_entities_to_globalMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
import re


class MergeNewEntitiesToGlobalMixin:
    """merge_new_entities_to_global功能域"""

    def merge_new_entities_to_global(
        self,
        global_graph,
        new_entities: Dict[str, List[str]],
        chapter_num: int
    ) -> Dict[str, int]:
        """
        将检测到的新实体合并到全局知识图谱

        Args:
            global_graph: 全局知识图谱实例
            new_entities: 新实体字典
            chapter_num: 章节号

        Returns:
            合并结果统计
        """
        result = {
            "characters_added": 0,
            "locations_added": 0,
            "organizations_added": 0,
            "items_added": 0,
            "total_added": 0
        }

        try:
            # 添加新人物
            for char_name in new_entities.get("characters", []):
                entity_data = {
                    "text": char_name,
                    "type": "人物",
                    "level": "micro",
                    "description": f"第{chapter_num}章首次出现",
                    "first_appearance_chapter": chapter_num
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{chapter_num}")
                result["characters_added"] += 1

            # 添加新地点
            for loc_name in new_entities.get("locations", []):
                entity_data = {
                    "text": loc_name,
                    "type": "地点",
                    "level": "macro",
                    "description": f"第{chapter_num}章首次提及",
                    "first_appearance_chapter": chapter_num
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{chapter_num}")
                result["locations_added"] += 1

            # 添加新组织
            for org_name in new_entities.get("organizations", []):
                entity_data = {
                    "text": org_name,
                    "type": "群体组织",
                    "level": "macro",
                    "description": f"第{chapter_num}章首次提及",
                    "first_appearance_chapter": chapter_num
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{chapter_num}")
                result["organizations_added"] += 1

            # 添加新物品
            for item_name in new_entities.get("items", []):
                entity_data = {
                    "text": item_name,
                    "type": "道具物品",
                    "level": "micro",
                    "description": f"第{chapter_num}章首次出现",
                    "first_appearance_chapter": chapter_num
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{chapter_num}")
                result["items_added"] += 1

            result["total_added"] = sum([
                result["characters_added"],
                result["locations_added"],
                result["organizations_added"],
                result["items_added"]
            ])

            if result["total_added"] > 0:
                global_graph.save()
                self.logger.info(
                    f"新实体已合并到全局图谱: 章节{chapter_num}, "
                    f"人物={result['characters_added']}, 地点={result['locations_added']}, "
                    f"组织={result['organizations_added']}, 物品={result['items_added']}")

        except Exception as e:
            self.logger.error(f"合并新实体到全局图谱失败: {e}")

        return result


