"""CharacterStateTracker - check_extended_consistencyMixin

跨实体类型一致性检查：设施-人物、道具-人物、事件-设施、
事件-时间、群体-人物、规则-内容等交叉验证。

@date: 2026-05-22
@version: v1.0.0
"""
from __future__ import annotations
from typing import Dict, List, Any


class CheckExtendedConsistencyMixin:
    """扩展实体交叉一致性检查

    提供跨实体类型的一致性验证，检测：
    - 设施-人物：人物出现在已关闭/损坏设施中
    - 道具-人物：道具持有者与人物位置不匹配
    - 事件-设施：事件发生在已关闭设施
    - 事件-时间：事件时序矛盾
    - 群体-人物：人物属于已解散群体
    - 规则-内容：内容违反世界规则
    """

    def check_extended_consistency(
        self,
        chapter_num: int,
        content: str,
        consistency_state: Dict[str, Any] = None,
        context_accumulator: Any = None
    ) -> Dict[str, Any]:
        """执行扩展实体交叉一致性检查

        Args:
            chapter_num: 当前章节号
            content: 本章生成内容
            consistency_state: 统一一致性状态（consistency_state.json内容）
            context_accumulator: 上下文累积器（可选）

        Returns:
            {
                "issues": [{type, severity, message}],
                "warnings": [{type, severity, message}],
                "passed": bool
            }
        """
        result = {
            "issues": [],
            "warnings": [],
            "passed": True
        }

        if not consistency_state:
            consistency_state = {}

        if not content:
            return result

        # ---- 检查1: 设施-人物交叉 ----
        self._check_facility_character_cross(result, content, consistency_state)

        # ---- 检查2: 道具-人物交叉 ----
        self._check_item_character_cross(result, content, consistency_state)

        # ---- 检查3: 事件-设施交叉 ----
        self._check_event_facility_cross(result, content, consistency_state)

        # ---- 检查4: 群体-人物交叉 ----
        self._check_group_character_cross(result, content, consistency_state)

        # ---- 检查5: 规则-内容交叉 ----
        self._check_rule_content_cross(result, content, consistency_state)

        # ---- 检查6: 事件-时间交叉 ----
        self._check_event_time_cross(result, content, consistency_state, chapter_num)

        if result["issues"]:
            result["passed"] = False

        return result

    # ========== 各维度交叉检查方法 ==========

    def _check_facility_character_cross(
        self, result: Dict, content: str, state: Dict
    ) -> None:
        """检查：人物出现在已关闭/损坏的设施中"""
        facilities = state.get("facilities", {})
        facility_abnormal_statuses = {"关闭", "损坏", "暂停营业", "已拆除"}

        for fname, finfo in facilities.items():
            fstatus = finfo.get("status", "")
            if fstatus not in facility_abnormal_statuses:
                continue
            if fname in content:
                result["warnings"].append({
                    "type": "facility_character_cross",
                    "severity": "warning",
                    "message": (
                        f"设施'{fname}'状态为'{fstatus}'，"
                        f"但本章内容中提到了该设施，请确认人物是否应出现在此"
                    )
                })

    def _check_item_character_cross(
        self, result: Dict, content: str, state: Dict
    ) -> None:
        """检查：道具持有者一致性，已离场道具不应再使用"""
        items = state.get("items", {})
        item_gone_statuses = {"已使用", "已销毁", "已遗失", "已回收", "已损坏", "丢失"}

        for iname, iinfo in items.items():
            istatus = iinfo.get("status", "")
            if istatus not in item_gone_statuses:
                continue
            if iname in content:
                result["issues"].append({
                    "type": "item_character_cross",
                    "severity": "error",
                    "message": (
                        f"道具'{iname}'状态为'{istatus}'（已离场/不可用），"
                        f"但本章内容中出现了该道具，存在逻辑冲突"
                    )
                })

    def _check_event_facility_cross(
        self, result: Dict, content: str, state: Dict
    ) -> None:
        """检查：事件发生在已关闭的设施中"""
        facilities = state.get("facilities", {})
        events = state.get("events", {})
        facility_abnormal = {"关闭", "损坏", "暂停营业", "已拆除"}

        abnormal_facilities_in_content = []
        for fname, finfo in facilities.items():
            if finfo.get("status", "") in facility_abnormal and fname in content:
                abnormal_facilities_in_content.append(fname)

        if not abnormal_facilities_in_content:
            return

        for ename, einfo in events.items():
            if ename not in content:
                continue
            # 事件可能在任意设施发生，提醒作者注意
            result["warnings"].append({
                "type": "event_facility_cross",
                "severity": "warning",
                "message": (
                    f"事件'{ename}'在内容中继续推进，"
                    f"但以下设施存在异常状态: {', '.join(abnormal_facilities_in_content[:3])}，"
                    f"请确认事件发生地点是否合理"
                )
            })
            break  # 只报告一次

    def _check_group_character_cross(
        self, result: Dict, content: str, state: Dict
    ) -> None:
        """检查：人物属于已解散/消亡的群体"""
        groups = state.get("groups", {})
        group_inactive_statuses = {"解散", "合并", "消亡"}

        for gname, ginfo in groups.items():
            gstatus = ginfo.get("status", "")
            if gstatus not in group_inactive_statuses:
                continue
            if gname in content:
                result["issues"].append({
                    "type": "group_character_cross",
                    "severity": "error",
                    "message": (
                        f"群体'{gname}'已{gstatus}，"
                        f"但本章内容中仍然引用了该群体，请确认一致性"
                    )
                })

    def _check_rule_content_cross(
        self, result: Dict, content: str, state: Dict
    ) -> None:
        """检查：内容是否可能违反世界规则

        由于无法精确判断内容是否违法规则，此处做启发式提醒：
        如果规则被明确提及，提醒作者注意规则约束。
        """
        rules = state.get("world_rules", {})
        for rname, rinfo in rules.items():
            rstatus = rinfo.get("status", "生效")
            if rstatus != "生效":
                continue
            if rname in content:
                result["warnings"].append({
                    "type": "rule_content_cross",
                    "severity": "warning",
                    "message": (
                        f"世界规则'{rname}'在本章内容中被引用，"
                        f"请确保内容不违反该规则的约束"
                    )
                })

    def _check_event_time_cross(
        self, result: Dict, content: str, state: Dict, chapter_num: int
    ) -> None:
        """检查：事件时序一致性

        检测已完成事件是否被重新激活、事件章节顺序是否合理。
        """
        events = state.get("events", {})
        finished_statuses = {"已完成", "已结束", "已取消"}
        time_ctx = state.get("time_context", {})

        for ename, einfo in events.items():
            if ename not in content:
                continue
            estatus = einfo.get("status", "")
            # 已完成事件不应再活跃出现
            if estatus in finished_statuses:
                result["issues"].append({
                    "type": "event_time_cross",
                    "severity": "error",
                    "message": (
                        f"事件'{ename}'已标记为'{estatus}'，"
                        f"但本章(第{chapter_num}章)内容中再次出现，存在时序矛盾"
                    )
                })

        # 检查时间节点是否有内容引用但时间已经过很久
        for tname, tinfo in time_ctx.items():
            if tname in content:
                t_chapter = tinfo.get("first_chapter", 0)
                if chapter_num > 0 and t_chapter > 0:
                    gap = chapter_num - t_chapter
                    if gap >= 10:
                        result["warnings"].append({
                            "type": "time_node_old_reference",
                            "severity": "warning",
                            "message": (
                                f"时间节点'{tname}'首次出现在第{t_chapter}章，"
                                f"距当前第{chapter_num}章已间隔{gap}章，请确认时间流逝是否合理"
                            )
                        })
