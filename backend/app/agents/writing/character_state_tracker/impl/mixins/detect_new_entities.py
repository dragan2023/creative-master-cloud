"""CharacterStateTracker - detect_new_entitiesMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
import re


class DetectNewEntitiesMixin:
    """detect_new_entities功能域"""

    def detect_new_entities(
        self,
        content: str,
        known_entities: Dict[str, Set[str]] = None
    ) -> Dict[str, List[str]]:
        """
        从内容中检测各类新实体（通用方法）

        这是一个扩展方法，不仅检测新人物，还检测：n        - 新地点
        - 新组织/群体
        - 新物品/道具
        - 新概念/术语

        Args:
            content: 章节内容
            known_entities: 已知实体字典 {"characters": set(), "locations": set(), ...}

        Returns:
            检测到的新实体字典
        """
        if known_entities is None:
            known_entities = {
                "characters": self._character_names,
                "locations": self._known_locations,
                "organizations": set(),
                "items": set(),
                "concepts": set()
            }

        new_entities = {
            "characters": [],
            "locations": [],
            "organizations": [],
            "items": [],
            "concepts": []
        }

        try:
            # 1. 检测新人物（使用现有方法）
            new_characters = self.detect_new_characters(content)
            new_entities["characters"] = [
                c for c in new_characters
                if c not in known_entities.get("characters", set())
            ]

            # 2. 检测新地点
            new_entities["locations"] = self._detect_new_locations(
                content, known_entities.get("locations", set()))

            # 3. 检测新组织
            new_entities["organizations"] = self._detect_new_organizations(
                content, known_entities.get("organizations", set()))

            # 4. 检测新物品
            new_entities["items"] = self._detect_new_items(
                content, known_entities.get("items", set()))

            # 汇总日志
            total_new = sum(len(v) for v in new_entities.values())
            if total_new > 0:
                self.logger.info(
                    f"检测到新实体: 人物={len(new_entities['characters'])}, "
                    f"地点={len(new_entities['locations'])}, "
                    f"组织={len(new_entities['organizations'])}, "
                    f"物品={len(new_entities['items'])}")

        except Exception as e:
            self.logger.error(f"检测新实体失败: {e}")

        return new_entities


    def _detect_new_locations(
        self,
        content: str,
        known_locations: Set[str]
    ) -> List[str]:
        """检测新地点"""
        new_locations = []

        # 地点模式
        location_patterns = [
            r'([一-龥]{2,6})(府|宫|殿|阁|楼|院|堂|斋|轩|亭|园)',  # 建筑名
            r'([一-龥]{2,6})(城|镇|村|山|谷|岭|峰|洞|海|江|河|湖)',  # 地名
            r'来到([一-龥]{2,6})(府|宫|城|镇|村|山)',  # 来到某地
            r'位于([一-龥]{2,6})(之|的)(东|西|南|北)',  # 位于某方位
            r'在([一-龥]{2,6})(之中|之内|之外)',  # 在某范围内
        ]

        for pattern in location_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    location = match[0]
                else:
                    location = match

                if location not in known_locations and len(location) >= 2:
                    new_locations.append(location)

        return list(set(new_locations))


    def _detect_new_organizations(
        self,
        content: str,
        known_orgs: Set[str]
    ) -> List[str]:
        """检测新组织/群体"""
        new_orgs = []

        # 组织模式
        org_patterns = [
            r'([一-龥]{2,6})(门|派|帮|会|盟|教|宗|族|家|院)',  # 门派帮会
            r'([一-龥]{2,6})军',  # 军队
            r'([一-龥]{2,6})卫',  # 卫所
            r'([一-龥]{2,6})营',  # 营地
            r'([一-龥]{2,6})(阁|楼|坊)',  # 组织名
        ]

        for pattern in org_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    org = match[0] + match[1] if len(match) > 1 else match[0]
                else:
                    org = match

                if org not in known_orgs and len(org) >= 2:
                    new_orgs.append(org)

        return list(set(new_orgs))


    def _detect_new_items(
        self,
        content: str,
        known_items: Set[str]
    ) -> List[str]:
        """检测新物品/道具"""
        new_items = []

        # 物品模式
        item_patterns = [
            r'([一-龥]{2,6})(剑|刀|枪|棍|鞭|盾|甲|盔)',  # 武器
            r'([一-龥]{2,6})(丹|药|丸|散)',  # 药物
            r'([一-龥]{2,6})(玉|佩|符|印|令)',  # 信物
            r'([一-龥]{2,6})经',  # 经书
            r'([一-龥]{2,6})谱',  # 谱籍
        ]

        for pattern in item_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    item = match[0] + match[1] if len(match) > 1 else match[0]
                else:
                    item = match

                if item not in known_items and len(item) >= 2:
                    new_items.append(item)

        return list(set(new_items))


