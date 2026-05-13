"""NovelKnowledgeGraph - get_consistency_reportMixin"""
from typing import Dict
from typing import List
from typing import Any
import json
import os
import re
import time


class GetConsistencyReportMixin:
    """get_consistency_report功能域"""

    def _get_project_graph_dir(self) -> str:
        """获取项目图谱数据目录路径
        
        从 self.persist_path 推导项目图谱数据根目录。
        各项目的数据结构为: .../project_X/graphs/
        """
        if getattr(self, 'persist_path', None):
            return os.path.dirname(self.persist_path)
        return ""

    def _load_consistency_state(self) -> Dict[str, Any]:
        """加载统一一致性状态
        
        从 consistency_state.json 读取跨章各维度状态。
        如果文件不存在则返回空字典。
        """
        project_graph_dir = self._get_project_graph_dir()
        if not project_graph_dir:
            return {}
        unified_path = os.path.join(project_graph_dir, "consistency_state.json")
        if not os.path.exists(unified_path):
            # 兼容旧版 event_status_index.json
            old_path = os.path.join(project_graph_dir, "event_status_index.json")
            if os.path.exists(old_path):
                try:
                    with open(old_path, "r", encoding="utf-8") as f:
                        return {"events": json.load(f)}
                except (json.JSONDecodeError, IOError):
                    pass
            return {}
        try:
            with open(unified_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

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
        """获取设施状态摘要
        
        🆕 [统一状态存储 v5.0] 合并 consistency_state.json 中的跨章设施状态
        """
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)
        unified_state = self._load_consistency_state()
        unified_facilities = unified_state.get("facilities", {})

        summary = {}

        # 优先从统一状态构建（跨章追踪的核心数据源）
        for name, uf in unified_facilities.items():
            summary[name] = {
                "type": uf.get("type", ""),
                "location": "",
                "manager": "",
                "status": uf.get("status", "正常运营"),
                "status_changes": [],
                # 元数据
                "first_chapter": uf.get("first_chapter", 0),
                "last_update_chapter": uf.get("last_update_chapter", 0),
            }

        # 补充单元图谱中独有设施
        for facility in extended_entities["facilities"]:
            name = facility.get("text", "")
            if name and name not in summary:
                summary[name] = {
                    "type": facility.get("attributes", {}).get("功能类型", ""),
                    "location": facility.get("attributes", {}).get("位置", ""),
                    "manager": facility.get("attributes", {}).get("负责人", ""),
                    "status": "正常运营",
                    "status_changes": [],
                    "first_chapter": facility.get("chapter", 0),
                    "last_update_chapter": facility.get("chapter", 0),
                }
            elif name:
                # 用单元图谱细节补充统一状态中的设施
                if not summary[name].get("location"):
                    summary[name]["location"] = facility.get("attributes", {}).get("位置", "")
                if not summary[name].get("type"):
                    summary[name]["type"] = facility.get("attributes", {}).get("功能类型", "")

        # 更新设施状态变化记录
        for state in extended_entities["facility_states"]:
            facility_name = state.get("attributes", {}).get("设施名称", "")
            if facility_name and facility_name in summary:
                new_status = state.get("attributes", {}).get("状态类型", state.get("text", ""))
                if new_status:
                    summary[facility_name]["status"] = new_status
                summary[facility_name]["status_changes"].append({
                    "chapter": state.get("chapter"),
                    "change": state.get("text", "")
                })

        return summary


    def _get_unfinished_events(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取未完成事件
        
        增强逻辑（事件生命周期管理 + 统一状态存储）：
        1. 优先从 consistency_state.json 读取跨章事件状态
        2. 其次从单元图谱 "事件状态变化" 实体读取 attributes.当前阶段
        3. 再次从 "事件" 实体本体读取 attributes.状态
        4. 如果事件在较远章节创建且长期未更新，标记为"可能已完结"
        5. 增加事件生命周期元数据：first_chapter, last_update_chapter
        """
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        # 🆕 [统一状态存储 v5.0] 加载跨章统一状态
        unified_state = self._load_consistency_state()
        unified_events = unified_state.get("events", {})

        # 先构建 event_states 状态映射
        event_status_map: Dict[str, str] = {}
        event_last_update_map: Dict[str, int] = {}
        for state in extended_entities["event_states"]:
            event_name = state.get("attributes", {}).get("事件名称", "")
            current_stage = state.get("attributes", {}).get("当前阶段", "")
            state_chapter = state.get("chapter")
            if event_name and current_stage:
                event_status_map[event_name] = current_stage
                if state_chapter is not None:
                    prev = event_last_update_map.get(event_name, 0)
                    try:
                        state_chapter_int = int(state_chapter) if not isinstance(state_chapter, int) else state_chapter
                    except (ValueError, TypeError):
                        state_chapter_int = 0
                    event_last_update_map[event_name] = max(prev, state_chapter_int)

        unfinished = []
        current_chapter = chapter_num or 0
        STALE_EVENT_THRESHOLD = 5
        finished_statuses = {"已完成", "已结束", "已取消"}

        # 优先从统一状态中补充事件（跨章追踪的核心数据源）
        seen_event_names = set()
        for event_name, unified_event in unified_events.items():
            seen_event_names.add(event_name)
            us_status = unified_event.get("status", "")
            us_first_ch = unified_event.get("first_chapter", 0)
            us_last_ch = unified_event.get("last_update_chapter", 0)

            # 统一状态中的已完成事件直接跳过
            if us_status in finished_statuses:
                continue

            # 检查单元图谱是否有更新状态
            if event_name in event_status_map:
                resolved_status = event_status_map[event_name]
            else:
                resolved_status = us_status

            last_update = max(us_last_ch, event_last_update_map.get(event_name, 0))

            # 启发式推断
            if (not resolved_status or resolved_status == "进行中") and current_chapter > 0:
                chapters_since_last_update = current_chapter - last_update
                if chapters_since_last_update >= STALE_EVENT_THRESHOLD:
                    resolved_status = "可能已完结"

            unfinished.append({
                "name": event_name,
                "type": unified_event.get("type", ""),
                "status": resolved_status or "进行中",
                "involved_characters": [],
                "location": "",
                "first_chapter": us_first_ch,
                "last_update_chapter": last_update,
            })

        # 补充单元图谱中独有的事件（统一状态中不存在的）
        for event in extended_entities["events"]:
            event_name = event.get("text", "")
            if not event_name or event_name in seen_event_names:
                continue

            if event_name in event_status_map:
                resolved_status = event_status_map[event_name]
            else:
                resolved_status = event.get("attributes", {}).get("状态", "")

            event_chapter = event.get("chapter")
            try:
                event_chapter_int = int(event_chapter) if not isinstance(event_chapter, int) else event_chapter
            except (ValueError, TypeError):
                event_chapter_int = 0

            last_update = event_last_update_map.get(event_name, event_chapter_int)

            if (not resolved_status or resolved_status == "进行中") and current_chapter > 0:
                chapters_since_last_update = current_chapter - last_update
                if chapters_since_last_update >= STALE_EVENT_THRESHOLD:
                    resolved_status = "可能已完结"

            if resolved_status not in finished_statuses:
                unfinished.append({
                    "name": event_name,
                    "type": event.get("attributes", {}).get("事件类型", ""),
                    "status": resolved_status or "进行中",
                    "involved_characters": event.get("attributes", {}).get("涉及人物", []),
                    "location": event.get("attributes", {}).get("发生地点", ""),
                    "first_chapter": event_chapter_int,
                    "last_update_chapter": last_update,
                })

        return unfinished


    def _get_group_states_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取群体动态摘要
        
        🆕 [统一状态存储 v5.0] 合并 consistency_state.json 中的跨章群体状态
        """
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)
        unified_state = self._load_consistency_state()
        unified_groups = unified_state.get("groups", {})

        summary = {}

        # 优先从统一状态构建
        for name, ug in unified_groups.items():
            summary[name] = {
                "scale": "",
                "nature": ug.get("type", ""),
                "leader": None,
                "status": ug.get("status", "活跃"),
                "members": [],
                "allies": [],
                "enemies": [],
                "first_chapter": ug.get("first_chapter", 0),
                "last_update_chapter": ug.get("last_update_chapter", 0),
            }

        # 补充单元图谱中独有群体
        for group in extended_entities["groups"]:
            name = group.get("text", "")
            if name and name not in summary:
                summary[name] = {
                    "scale": group.get("attributes", {}).get("规模", ""),
                    "nature": group.get("attributes", {}).get("性质", ""),
                    "leader": None,
                    "status": "活跃",
                    "members": [],
                    "allies": [],
                    "enemies": [],
                    "first_chapter": group.get("chapter", 0),
                    "last_update_chapter": group.get("chapter", 0),
                }
            elif name:
                if not summary[name].get("scale"):
                    summary[name]["scale"] = group.get("attributes", {}).get("规模", "")

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
        """获取道具归属摘要
        
        🆕 [统一状态存储 v5.0] 合并 consistency_state.json 中的跨章道具状态
        """
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)
        unified_state = self._load_consistency_state()
        unified_items = unified_state.get("items", {})

        summary = {}

        # 优先从统一状态构建
        for name, ui in unified_items.items():
            summary[name] = {
                "type": ui.get("type", ""),
                "owner": "",
                "status": ui.get("status", "已知"),
                "description": "",
                "first_chapter": ui.get("first_chapter", 0),
                "last_update_chapter": ui.get("last_update_chapter", 0),
            }

        # 补充单元图谱中独有道具
        for item in extended_entities["items"]:
            name = item.get("text", "")
            if name and name not in summary:
                summary[name] = {
                    "type": item.get("attributes", {}).get("物品类型", ""),
                    "owner": item.get("attributes", {}).get("持有者", ""),
                    "status": "已知",
                    "description": item.get("description", ""),
                    "first_chapter": item.get("chapter", 0),
                    "last_update_chapter": item.get("chapter", 0),
                }
            elif name:
                if not summary[name].get("owner"):
                    summary[name]["owner"] = item.get("attributes", {}).get("持有者", "")
                if not summary[name].get("type"):
                    summary[name]["type"] = item.get("attributes", {}).get("物品类型", "")

        # 更新归属变更
        for ownership in extended_entities["item_ownerships"]:
            item_name = ownership.get("attributes", {}).get("物品名称", "")
            if item_name and item_name in summary:
                new_owner = ownership.get("attributes", {}).get("新持有者", "")
                if new_owner:
                    summary[item_name]["owner"] = new_owner

        # 更新状态变化
        for state in extended_entities["item_states"]:
            item_name = state.get("attributes", {}).get("物品名称", state.get("attributes", {}).get("item", ""))
            if item_name and item_name in summary:
                new_status = state.get("attributes", {}).get("状态类型", state.get("text", ""))
                if new_status:
                    summary[item_name]["status"] = new_status

        return summary


    def _get_pending_foreshadows(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取待回收伏笔
        
        🆕 [统一状态存储 v5.0] 合并 consistency_state.json 中的跨章伏笔状态
        """
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)
        unified_state = self._load_consistency_state()
        unified_foreshadows = unified_state.get("foreshadows", {})

        pending = []
        resolved_names = set()

        # 从统一状态中收集已回收伏笔
        for name, uf in unified_foreshadows.items():
            if uf.get("status") == "已回收":
                resolved_names.add(name)

        # 单元图谱中的伏笔回收
        for resolution in extended_entities["foreshadow_resolutions"]:
            foreshadow_name = resolution.get("attributes", {}).get("伏笔名称", resolution.get("attributes", {}).get("foreshadowing", ""))
            if foreshadow_name:
                resolved_names.add(foreshadow_name)

        # 优先从统一状态构建（跨章追踪的核心数据源）
        seen_names = set()
        for name, uf in unified_foreshadows.items():
            seen_names.add(name)
            if name not in resolved_names and uf.get("status") != "已回收":
                pending.append({
                    "name": name,
                    "planted_chapter": uf.get("first_chapter", 0),
                    "importance": uf.get("type", "普通"),
                    "description": "",
                    "last_update_chapter": uf.get("last_update_chapter", 0),
                })

        # 补充单元图谱中独有的伏笔
        for foreshadow in extended_entities["foreshadows"]:
            name = foreshadow.get("text", "")
            if name and name not in seen_names and name not in resolved_names:
                pending.append({
                    "name": name,
                    "planted_chapter": foreshadow.get("chapter"),
                    "importance": foreshadow.get("attributes", {}).get("重要程度", "普通"),
                    "description": foreshadow.get("description", "")
                })

        return pending


    def _get_active_rules(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取规则约束
        
        🆕 [统一状态存储 v5.0] 合并 consistency_state.json 中的跨章规则状态
        """
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)
        unified_state = self._load_consistency_state()
        unified_rules = unified_state.get("world_rules", {})

        rules = []
        seen_names = set()

        # 优先从统一状态构建
        for name, ur in unified_rules.items():
            seen_names.add(name)
            rules.append({
                "name": name,
                "type": ur.get("type", ""),
                "description": "",
                "status": ur.get("status", "生效"),
                "first_chapter": ur.get("first_chapter", 0),
                "last_update_chapter": ur.get("last_update_chapter", 0),
            })

        # 补充单元图谱中独有的规则
        for rule in extended_entities["world_rules"]:
            name = rule.get("text", "")
            if name and name not in seen_names:
                rules.append({
                    "name": name,
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
                event_status = event.get("status", "进行中")
                first_ch = event.get("first_chapter", "?")
                last_up = event.get("last_update_chapter", "?")
                # 🆕 区分"可能已完结"的事件与真正进行中的事件
                if event_status == "可能已完结":
                    warnings.append(
                        f"⚠️ 疑似已完结事件(请确认): {event['name']} "
                        f"(始于第{first_ch}章, 最后更新于第{last_up}章)")
                else:
                    warnings.append(
                        f"未完成事件: {event['name']} - 当前状态: {event_status} "
                        f"(始于第{first_ch}章)")

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


