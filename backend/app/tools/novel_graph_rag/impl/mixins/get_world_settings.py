"""NovelKnowledgeGraph - get_world_settingsMixin"""
from typing import Dict
from typing import Any
import re
import time


class GetWorldSettingsMixin:
    """get_world_settings功能域"""

    def get_world_settings(self) -> Dict[str, Any]:
        """获取世界观设定

        从知识图谱中提取"世界观规则"和"地点"类型的实体，
        构建世界观设定字典。

        Returns:
            世界观设定字典
        """
        settings = {
            "rules": [],
            "locations": [],
            "time_period": "",
            "social_background": ""
        }

        for node_id, data in self.graph.nodes(data=True):
            entity_type = data.get("type", "")
            attrs = data.get("attributes", {})

            if entity_type == "世界观规则":
                settings["rules"].append({
                    "name": data.get("text", ""),
                    "description": data.get("description", "")
                })
            elif entity_type == "地点":
                settings["locations"].append({
                    "name": data.get("text", ""),
                    "description": data.get("description", "")
                })
            elif entity_type == "主题":
                settings["theme"] = data.get("text", "")
                settings["theme_description"] = data.get("description", "")

        return settings


