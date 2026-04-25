"""NovelKnowledgeGraph - get_consistency_reportMixin"""
from typing import Dict
from typing import List
from typing import Any
import re
import time


class GetConsistencyReportMixin:
    """get_consistency_report功能域"""

    def get_consistency_report(self, chapter_num: int = None) -> Dict[str, Any]:
        """
        获取一致性报告，供写作Agent参考

        返回所有需要保持一致性的实体状态摘要，包括：
        - 人物状态摘要
        - 设施状态摘要
        - 未完成事件
        - 群体动态
        - 道具归属
        - 待回收伏笔
        - 规则约束

        Args:
            chapter_num: 章节号（可选，只显示到该章节为止的状态）

        Returns:
            一致性报告字典
        """
        report = {
            "chapter": chapter_num,
            "character_states": {},
            "facility_states": {},
            "unfinished_events": [],
            "group_states": {},
            "item_ownership": {},
            "pending_foreshadows": [],
            "active_rules": [],
            "time_context": {},
            "consistency_warnings": []
        }

        # 1. 获取人物状态摘要
        report["character_states"] = self._get_character_states_summary(
            chapter_num)

        # 2. 获取设施状态摘要
        report["facility_states"] = self._get_facility_states_summary(
            chapter_num)

        # 3. 获取未完成事件
        report["unfinished_events"] = self._get_unfinished_events(chapter_num)

        # 4. 获取群体动态
        report["group_states"] = self._get_group_states_summary(chapter_num)

        # 5. 获取道具归属
        report["item_ownership"] = self._get_item_ownership_summary(
            chapter_num)

        # 6. 获取待回收伏笔
        report["pending_foreshadows"] = self._get_pending_foreshadows(
            chapter_num)

        # 7. 获取规则约束
        report["active_rules"] = self._get_active_rules(chapter_num)

        # 8. 获取时间上下文
        report["time_context"] = self._get_time_context(chapter_num)

        # 9. 生成一致性警告
        report["consistency_warnings"] = self._generate_consistency_warnings(
            report)

        return report


    def _get_character_states_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取人物状态摘要"""
        state_entities = self.get_character_state_entities(
            chapter_num=chapter_num)

        summary = {}
        # 按人物整理状态
        all_entities = (
            state_entities["identity_changes"] +
            state_entities["location_changes"] +
            state_entities["relationship_changes"] +
            state_entities["ability_growth"] +
            state_entities["mental_states"] +
            state_entities["character_development"] +
            state_entities["behavior_patterns"]
        )

        for entity in all_entities:
            char_name = entity.get("character", "")
            if not char_name:
                continue

            if char_name not in summary:
                summary[char_name] = {
                    "latest_identity": None,
                    "latest_location": None,
                    "key_relationships": [],
                    "abilities": [],
                    "mental_state": None,
                    "character_development": [],
                    "behavior_patterns": []
                }

            entity_type = entity.get("type", "")
            if entity_type == "身份变化":
                summary[char_name]["latest_identity"] = entity.get("text", "")
            elif entity_type == "位置变化":
                summary[char_name]["latest_location"] = entity.get("text", "")
            elif entity_type == "关系变化":
                summary[char_name]["key_relationships"].append(
                    entity.get("text", ""))
            elif entity_type == "能力成长":
                summary[char_name]["abilities"].append(entity.get("text", ""))
            elif entity_type == "心理状态":
                summary[char_name]["mental_state"] = entity.get("text", "")
            elif entity_type == "性格发展":
                summary[char_name]["character_development"].append(
                    entity.get("text", ""))
            elif entity_type == "行为模式":
                summary[char_name]["behavior_patterns"].append(
                    entity.get("text", ""))

        return summary


    def _get_facility_states_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取设施状态摘要"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        summary = {}

        # 处理设施实体
        for facility in extended_entities["facilities"]:
            name = facility.get("text", "")
            if name:
                summary[name] = {
                    "type": facility.get("attributes", {}).get("功能类型", ""),
                    "location": facility.get("attributes", {}).get("位置", ""),
                    "manager": facility.get("attributes", {}).get("负责人", ""),
                    "status": "正常运营",  # 默认状态
                    "status_changes": []
                }

        # 更新设施状态变化
        for state in extended_entities["facility_states"]:
            facility_name = state.get("attributes", {}).get("设施名称", "")
            if facility_name and facility_name in summary:
                summary[facility_name]["status"] = state.get("text", "")
                summary[facility_name]["status_changes"].append({
                    "chapter": state.get("chapter"),
                    "change": state.get("text", "")
                })

        return summary


    def _get_unfinished_events(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取未完成事件"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        unfinished = []

        # 处理事件实体
        for event in extended_entities["events"]:
            event_info = {
                "name": event.get("text", ""),
                "type": event.get("attributes", {}).get("事件类型", ""),
                "status": "进行中",  # 默认状态
                "involved_characters": event.get("attributes", {}).get("涉及人物", []),
                "location": event.get("attributes", {}).get("发生地点", "")
            }
            unfinished.append(event_info)

        # 更新事件状态
        for state in extended_entities["event_states"]:
            event_name = state.get("attributes", {}).get("事件名称", "")
            for event in unfinished:
                if event["name"] == event_name:
                    event["status"] = state.get(
                        "attributes", {}).get("当前阶段", "")
                    break

        # 只返回未完成的事件
        unfinished = [e for e in unfinished if e["status"]
                      not in ["已完成", "已结束", "已取消"]]

        return unfinished


    def _get_group_states_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取群体动态摘要"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        summary = {}

        # 处理群体组织
        for group in extended_entities["groups"]:
            name = group.get("text", "")
            if name:
                summary[name] = {
                    "scale": group.get("attributes", {}).get("规模", ""),
                    "nature": group.get("attributes", {}).get("性质", ""),
                    "leader": None,
                    "status": "活跃",
                    "members": [],
                    "allies": [],
                    "enemies": []
                }

        # 更新成员变动
        for member in extended_entities["group_members"]:
            group_name = member.get("attributes", {}).get("群体名称", "")
            if group_name and group_name in summary:
                member_name = member.get("attributes", {}).get("成员名称", "")
                变动类型 = member.get("attributes", {}).get("变动类型", "")
                if 变动类型 in ["加入", "晋升"]:
                    summary[group_name]["members"].append(member_name)
                elif 变动类型 == "领导":
                    summary[group_name]["leader"] = member_name

        return summary


    def _get_item_ownership_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取道具归属摘要"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        summary = {}

        # 处理道具物品
        for item in extended_entities["items"]:
            name = item.get("text", "")
            if name:
                summary[name] = {
                    "type": item.get("attributes", {}).get("物品类型", ""),
                    "owner": item.get("attributes", {}).get("持有者", ""),
                    "status": "完好",
                    "description": item.get("description", "")
                }

        # 更新归属变更
        for ownership in extended_entities["item_ownerships"]:
            item_name = ownership.get("attributes", {}).get("物品名称", "")
            if item_name and item_name in summary:
                new_owner = ownership.get("attributes", {}).get("新持有者", "")
                if new_owner:
                    summary[item_name]["owner"] = new_owner

        # 更新状态变化
        for state in extended_entities["item_states"]:
            item_name = state.get("attributes", {}).get("物品名称", "")
            if item_name and item_name in summary:
                summary[item_name]["status"] = state.get("text", "")

        return summary


    def _get_pending_foreshadows(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取待回收伏笔"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        pending = []
        resolved = set()

        # 先收集已回收的伏笔
        for resolution in extended_entities["foreshadow_resolutions"]:
            foreshadow_name = resolution.get("attributes", {}).get("伏笔名称", "")
            if foreshadow_name:
                resolved.add(foreshadow_name)

        # 再收集未回收的伏笔
        for foreshadow in extended_entities["foreshadows"]:
            name = foreshadow.get("text", "")
            if name and name not in resolved:
                pending.append({
                    "name": name,
                    "planted_chapter": foreshadow.get("chapter"),
                    "importance": foreshadow.get("attributes", {}).get("重要程度", "普通"),
                    "description": foreshadow.get("description", "")
                })

        return pending


    def _get_active_rules(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取规则约束"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        rules = []

        for rule in extended_entities["world_rules"]:
            rules.append({
                "name": rule.get("text", ""),
                "type": rule.get("attributes", {}).get("规则类型", ""),
                "description": rule.get("description", "")
            })

        return rules


    def _get_time_context(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取时间上下文"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        context = {
            "current_time": None,
            "time_nodes": [],
            "time_elapsed": []
        }

        for node in extended_entities["time_nodes"]:
            context["time_nodes"].append({
                "name": node.get("text", ""),
                "type": node.get("attributes", {}).get("时间类型", "")
            })

        for flow in extended_entities["time_flows"]:
            context["time_elapsed"].append({
                "description": flow.get("text", ""),
                "chapter": flow.get("chapter")
            })

        return context


    def _generate_consistency_warnings(self, report: Dict[str, Any]) -> List[str]:
        """生成一致性警告"""
        warnings = []

        # 检查未完成事件
        if report["unfinished_events"]:
            for event in report["unfinished_events"]:
                warnings.append(
                    f"未完成事件: {event['name']} - 当前状态: {event['status']}")

        # 检查待回收伏笔
        if report["pending_foreshadows"]:
            for foreshadow in report["pending_foreshadows"]:
                importance = foreshadow.get("importance", "普通")
                if importance == "重要":
                    warnings.append(
                        f"重要伏笔待回收: {foreshadow['name']} (埋设于第{foreshadow.get('planted_chapter', '?')}章)")

        # 检查设施状态
        for name, state in report["facility_states"].items():
            if state.get("status") in ["关闭", "暂停营业", "损坏"]:
                warnings.append(f"设施状态异常: {name} - {state.get('status')}")

        return warnings


