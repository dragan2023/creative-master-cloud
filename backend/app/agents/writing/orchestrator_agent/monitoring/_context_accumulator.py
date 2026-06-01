"""
monitoring/_context_accumulator.py - 扩展上下文累积器

包含 ExtendedContextAccumulator 类，增量维护已知实体信息。

@date: 2026-04-24
@version: v3.0.0
"""
from typing import Any, Dict, List, Set

from app.core.logger import get_logger


class ExtendedContextAccumulator:
    """扩展上下文累积器

    增量维护已知实体信息，避免每次重新遍历所有前文章节。
    章节完成后增量更新，获取时直接返回累积结果。
    """

    def __init__(self):
        """初始化累积器"""
        self.known_facilities: Set[str] = set()
        self.known_groups: Set[str] = set()
        self.known_items: Set[str] = set()
        self.known_rules: Set[str] = set()
        self.known_time_nodes: Set[str] = set()
        self.unfinished_events: Set[str] = set()
        self.pending_foreshadows: Set[str] = set()
        # 🆕 [统一状态存储 v5.0] 全维度状态追踪
        self.item_status: Dict[str, str] = {}       # 道具名 → 状态
        self.facility_status: Dict[str, str] = {}   # 设施名 → 状态
        self.group_status: Dict[str, str] = {}      # 群体名 → 状态
        self.foreshadow_status: Dict[str, str] = {} # 伏笔名 → 状态
        self.rule_status: Dict[str, str] = {}       # 规则名 → 状态
        self._processed_chapters: Set[int] = set()
        self._logger = get_logger("context_accumulator")

    def update_from_graph(self, graph: "NovelKnowledgeGraph", chapter_num: int) -> None:
        """从图谱增量更新累积器"""
        if chapter_num in self._processed_chapters:
            self._logger.debug(f"章节{chapter_num}已处理，跳过更新")
            return

        try:
            extended_entities = graph.get_extended_state_entities()

            for facility in extended_entities.get("facilities", []):
                name = facility.get("text", "")
                if name:
                    self.known_facilities.add(name)
                    status = facility.get("attributes", {}).get("状态") or facility.get("attributes", {}).get("当前状态", "正常运营")
                    self.facility_status[name] = status
            for state in extended_entities.get("facility_states", []):
                fname = state.get("attributes", {}).get("设施名称", "")
                new_status = state.get("attributes", {}).get("状态类型", state.get("text", ""))
                if fname and new_status:
                    self.facility_status[fname] = new_status

            for group in extended_entities.get("groups", []):
                name = group.get("text", "")
                if name:
                    self.known_groups.add(name)
                    status = group.get("attributes", {}).get("状态") or group.get("attributes", {}).get("当前状态", "活跃")
                    self.group_status[name] = status
            for state in extended_entities.get("group_states", []):
                gname = state.get("attributes", {}).get("群体名称", "")
                new_status = state.get("attributes", {}).get("变化类型", state.get("text", ""))
                if gname and new_status:
                    self.group_status[gname] = new_status

            for item in extended_entities.get("items", []):
                name = item.get("text", "")
                if name:
                    self.known_items.add(name)
                    status = item.get("attributes", {}).get("状态") or item.get("attributes", {}).get("当前状态", "已知")
                    self.item_status[name] = status
            for state in extended_entities.get("item_states", []):
                iname = state.get("attributes", {}).get("物品名称", state.get("attributes", {}).get("item", ""))
                new_status = state.get("attributes", {}).get("状态类型", state.get("text", ""))
                if iname and new_status:
                    self.item_status[iname] = new_status
            for ownership in extended_entities.get("item_ownerships", []):
                iname = ownership.get("attributes", {}).get("物品名称", "")
                if iname and iname not in self.item_status:
                    self.item_status[iname] = "易主"
                elif iname:
                    self.item_status[iname] = "易主"

            # 🆕 [事件生命周期] 先构建 event_states 状态映射
            # "事件状态变化" 实体通过 attributes.当前阶段 标记事件完成状态
            event_status_map: Dict[str, str] = {}
            for state_entity in extended_entities.get("event_states", []):
                event_name = state_entity.get("attributes", {}).get("事件名称", "")
                current_stage = state_entity.get("attributes", {}).get("当前阶段", "")
                if event_name and current_stage:
                    event_status_map[event_name] = current_stage

            for event in extended_entities.get("events", []):
                name = event.get("text", "")
                if not name:
                    continue
                # 多层回退读取状态：
                # 1) "事件状态变化" 实体中的 attributes.当前阶段 (最优先)
                # 2) "事件" 实体本身的 attributes.状态
                if name in event_status_map:
                    status = event_status_map[name]
                else:
                    status = event.get("attributes", {}).get("状态", "")
                if status in ["已完成", "已结束", "已取消"]:
                    self.unfinished_events.discard(name)
                else:
                    self.unfinished_events.add(name)

            for foreshadow in extended_entities.get("foreshadows", []):
                name = foreshadow.get("text", "")
                if name:
                    self.pending_foreshadows.add(name)

            # 伏笔状态追踪（从 update_from_graph 中补充）
            for f in extended_entities.get("foreshadows", []):
                name = f.get("text", "")
                if name and name not in self.foreshadow_status:
                    status = f.get("attributes", {}).get("状态", "已埋下")
                    self.foreshadow_status[name] = status
            for resolution in extended_entities.get("foreshadow_resolutions", []):
                fname = resolution.get("attributes", {}).get("伏笔名称", "")
                if fname:
                    self.foreshadow_status[fname] = "已回收"

            # 🆕 世界规则追踪
            for rule in extended_entities.get("world_rules", []):
                name = rule.get("text", "")
                if name:
                    self.known_rules.add(name)
                    status = rule.get("attributes", {}).get("状态", rule.get("attributes", {}).get("当前状态", "生效"))
                    self.rule_status[name] = status
            for rule_ref in extended_entities.get("rule_references", []):
                rname = rule_ref.get("attributes", {}).get("规则名称", "")
                if rname and rname not in self.rule_status:
                    self.rule_status[rname] = "被引用"

            # 🆕 时间线追踪
            for time_node in extended_entities.get("time_nodes", []):
                name = time_node.get("text", "")
                if name:
                    self.known_time_nodes.add(name)
            for time_flow in extended_entities.get("time_flows", []):
                name = time_flow.get("text", "")
                if name:
                    self.known_time_nodes.add(name)

            self._processed_chapters.add(chapter_num)
            # 统计各维度离场/异常数量
            item_removed = sum(1 for s in self.item_status.values() if s in ["已使用", "已销毁", "已遗失", "已回收", "已损坏"])
            facility_abnormal = sum(1 for s in self.facility_status.values() if s in ["关闭", "损坏", "暂停营业", "已拆除"])
            group_inactive = sum(1 for s in self.group_status.values() if s in ["解散", "合并", "消亡"])
            foreshadow_resolved = sum(1 for s in self.foreshadow_status.values() if s == "已回收")
            rule_count = len(self.known_rules)
            time_node_count = len(self.known_time_nodes)
            self._logger.debug(
                f"累积器更新完成: 章节{chapter_num}, "
                f"设施={len(self.known_facilities)}(异常{facility_abnormal}), "
                f"群体={len(self.known_groups)}(解散{group_inactive}), "
                f"道具={len(self.known_items)}(离场{item_removed}), "
                f"伏笔={len(self.foreshadow_status)}(已回收{foreshadow_resolved}), "
                f"规则={rule_count}, 时间线={time_node_count}"
            )
        except Exception as e:
            self._logger.warning(f"累积器更新失败: 章节{chapter_num}, 错误={e}")

    def sync_from_global_graph(self, graph: "NovelKnowledgeGraph") -> None:
        """从全局图谱同步所有已知实体"""
        try:
            extended_entities = graph.get_extended_state_entities()

            self.known_facilities = set()
            self.facility_status = {}
            for f in extended_entities.get("facilities", []):
                name = f.get("text", "")
                if name:
                    self.known_facilities.add(name)
                    self.facility_status[name] = f.get("attributes", {}).get("状态") or f.get("attributes", {}).get("当前状态", "正常运营")
            for state in extended_entities.get("facility_states", []):
                fname = state.get("attributes", {}).get("设施名称", "")
                new_status = state.get("attributes", {}).get("状态类型", state.get("text", ""))
                if fname and new_status:
                    self.facility_status[fname] = new_status

            self.known_groups = set()
            self.group_status = {}
            for g in extended_entities.get("groups", []):
                name = g.get("text", "")
                if name:
                    self.known_groups.add(name)
                    self.group_status[name] = g.get("attributes", {}).get("状态") or g.get("attributes", {}).get("当前状态", "活跃")
            for state in extended_entities.get("group_states", []):
                gname = state.get("attributes", {}).get("群体名称", "")
                new_status = state.get("attributes", {}).get("变化类型", state.get("text", ""))
                if gname and new_status:
                    self.group_status[gname] = new_status

            self.known_items = set()
            self.item_status = {}
            for i in extended_entities.get("items", []):
                name = i.get("text", "")
                if name:
                    self.known_items.add(name)
                    self.item_status[name] = i.get("attributes", {}).get("状态") or i.get("attributes", {}).get("当前状态", "已知")
            for state in extended_entities.get("item_states", []):
                iname = state.get("attributes", {}).get("物品名称", state.get("attributes", {}).get("item", ""))
                new_status = state.get("attributes", {}).get("状态类型", state.get("text", ""))
                if iname and new_status:
                    self.item_status[iname] = new_status
            for ownership in extended_entities.get("item_ownerships", []):
                iname = ownership.get("attributes", {}).get("物品名称", "")
                if iname:
                    self.item_status[iname] = "易主"

            self.unfinished_events = set()
            # 🆕 [事件生命周期] 先构建 event_states 状态映射
            event_status_map: Dict[str, str] = {}
            for state_entity in extended_entities.get("event_states", []):
                event_name = state_entity.get("attributes", {}).get("事件名称", "")
                current_stage = state_entity.get("attributes", {}).get("当前阶段", "")
                if event_name and current_stage:
                    event_status_map[event_name] = current_stage

            for event in extended_entities.get("events", []):
                name = event.get("text", "")
                if not name:
                    continue
                # 多层回退：优先 event_states 中的 当前阶段，其次 event 本体中的 状态
                if name in event_status_map:
                    status = event_status_map[name]
                else:
                    status = event.get("attributes", {}).get("状态", "")
                if status not in ["已完成", "已结束", "已取消"]:
                    self.unfinished_events.add(name)

            self.pending_foreshadows = set()
            for f in extended_entities.get("foreshadows", []):
                name = f.get("text", "")
                if name:
                    status = f.get("attributes", {}).get("状态", "已埋下")
                    self.foreshadow_status[name] = status
                    if status != "已回收":
                        self.pending_foreshadows.add(name)
            for resolution in extended_entities.get("foreshadow_resolutions", []):
                fname = resolution.get("attributes", {}).get("伏笔名称", "")
                if fname:
                    self.foreshadow_status[fname] = "已回收"
                    self.pending_foreshadows.discard(fname)

            # 🆕 世界规则同步
            self.known_rules = set()
            self.rule_status = {}
            for rule in extended_entities.get("world_rules", []):
                name = rule.get("text", "")
                if name:
                    self.known_rules.add(name)
                    self.rule_status[name] = rule.get("attributes", {}).get("状态", rule.get("attributes", {}).get("当前状态", "生效"))
            for rule_ref in extended_entities.get("rule_references", []):
                rname = rule_ref.get("attributes", {}).get("规则名称", "")
                if rname and rname not in self.rule_status:
                    self.rule_status[rname] = "被引用"

            # 🆕 时间线同步
            self.known_time_nodes = set()
            for time_node in extended_entities.get("time_nodes", []):
                name = time_node.get("text", "")
                if name:
                    self.known_time_nodes.add(name)
            for time_flow in extended_entities.get("time_flows", []):
                name = time_flow.get("text", "")
                if name:
                    self.known_time_nodes.add(name)

            foreshadow_resolved = sum(1 for s in self.foreshadow_status.values() if s == "已回收")
            self._logger.info(
                f"从全局图谱同步完成: 设施={len(self.known_facilities)}, "
                f"群体={len(self.known_groups)}, "
                f"道具={len(self.known_items)}, "
                f"事件={len(self.unfinished_events)}, "
                f"伏笔={len(self.pending_foreshadows)}(已回收{foreshadow_resolved}), "
                f"规则={len(self.known_rules)}, 时间线={len(self.known_time_nodes)}"
            )
        except Exception as e:
            self._logger.warning(f"从全局图谱同步失败: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        🆕 [统一状态存储 v5.0] 返回全维度状态信息，
        仅包含活跃/未离场的实体供 LLM 上下文使用。
        """
        active_items = [
            k for k in self.known_items
            if self.item_status.get(k, "") not in ["已使用", "已销毁", "已遗失", "已回收", "已损坏"]
        ]
        active_facilities = [
            k for k in self.known_facilities
            if self.facility_status.get(k, "") not in ["关闭", "损坏", "已拆除"]
        ]
        active_groups = [
            k for k in self.known_groups
            if self.group_status.get(k, "") not in ["解散", "合并", "消亡"]
        ]
        return {
            "known_facilities": active_facilities,
            "known_groups": active_groups,
            "known_items": active_items,
            "unfinished_events": list(self.unfinished_events),
            "pending_foreshadows": list(self.pending_foreshadows),
            # 🆕 附加完整状态映射供高级消费方使用
            "item_status": dict(self.item_status),
            "facility_status": dict(self.facility_status),
            "group_status": dict(self.group_status),
            "foreshadow_status": dict(self.foreshadow_status),
            # 🆕 世界规则和时间线
            "known_rules": list(self.known_rules),
            "rule_status": dict(self.rule_status),
            "known_time_nodes": list(self.known_time_nodes),
        }

    def reset(self) -> None:
        """重置累积器状态"""
        self.known_facilities.clear()
        self.known_groups.clear()
        self.known_items.clear()
        self.known_rules.clear()
        self.known_time_nodes.clear()
        self.unfinished_events.clear()
        self.pending_foreshadows.clear()
        self.item_status.clear()
        self.facility_status.clear()
        self.group_status.clear()
        self.foreshadow_status.clear()
        self.rule_status.clear()
        self._processed_chapters.clear()
        self._logger.debug("累积器已重置")
