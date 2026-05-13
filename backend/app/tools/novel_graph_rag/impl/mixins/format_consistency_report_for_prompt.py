"""NovelKnowledgeGraph - format_consistency_report_for_promptMixin"""
import re


class FormatConsistencyReportForPromptMixin:
    """format_consistency_report_for_prompt功能域"""

    def format_consistency_report_for_prompt(self, chapter_num: int = None) -> str:
        """
        格式化一致性报告为提示词格式

        将一致性报告格式化为可读的文本，供写作Agent使用。

        Args:
            chapter_num: 章节号（可选）

        Returns:
            格式化的一致性报告文本
        """
        report = self.get_consistency_report(chapter_num)

        lines = ["# 一致性追踪报告", ""]

        # 人物状态
        if report["character_states"]:
            lines.append("## 人物状态")
            for char_name, state in report["character_states"].items():
                lines.append(f"### {char_name}")
                if state.get("latest_identity"):
                    lines.append(f"- 当前身份: {state['latest_identity']}")
                if state.get("latest_location"):
                    lines.append(f"- 当前位置: {state['latest_location']}")
                if state.get("abilities"):
                    lines.append(f"- 能力: {', '.join(state['abilities'][-3:])}")
                if state.get("mental_state"):
                    lines.append(f"- 心理状态: {state['mental_state']}")
            lines.append("")

        # 设施状态
        if report["facility_states"]:
            lines.append("## 设施状态")
            for name, state in report["facility_states"].items():
                status_info = f"{name}: {state.get('status', '未知')}"
                if state.get('manager'):
                    status_info += f" (负责人: {state['manager']})"
                lines.append(f"- {status_info}")
            lines.append("")

        # 未完成事件
        if report["unfinished_events"]:
            lines.append("## 未完成事件")
            for event in report["unfinished_events"]:
                event_status = event.get('status', '进行中')
                first_ch = event.get('first_chapter', '?')
                last_up = event.get('last_update_chapter', '?')
                
                # 🆕 区分可能已完结和真正进行中的事件
                if event_status == "可能已完结":
                    lines.append(f"- ⚠️ [待确认] {event['name']}: {event_status}")
                    lines.append(f"  始于第{first_ch}章, 最后更新第{last_up}章")
                else:
                    lines.append(f"- {event['name']}: {event_status}")
                    lines.append(f"  始于第{first_ch}章")
                
                if event.get('involved_characters'):
                    lines.append(
                        f"  涉及人物: {', '.join(event['involved_characters'])}")
            lines.append("")

        # 群体动态
        if report["group_states"]:
            lines.append("## 群体动态")
            for name, state in report["group_states"].items():
                lines.append(f"- {name}: {state.get('status', '活跃')}")
                if state.get('leader'):
                    lines.append(f"  领导者: {state['leader']}")
                if state.get('scale'):
                    lines.append(f"  规模: {state['scale']}")
            lines.append("")

        # 道具归属
        if report["item_ownership"]:
            lines.append("## 道具归属")
            for name, state in report["item_ownership"].items():
                lines.append(
                    f"- {name}: 持有者={state.get('owner', '未知')}, 状态={state.get('status', '完好')}")
            lines.append("")
        # 待回收伏笔
        if report["pending_foreshadows"]:
            lines.append("## 待回收伏笔")
            for foreshadow in report["pending_foreshadows"]:
                importance = foreshadow.get("importance", "普通")
                lines.append(
                    f"- [{importance}] {foreshadow['name']} (第{foreshadow.get('planted_chapter', '?')}章)")
            lines.append("")

        # 一致性警告
        if report["consistency_warnings"]:
            lines.append("## ⚠️ 一致性警告")
            for warning in report["consistency_warnings"]:
                lines.append(f"- {warning}")
            lines.append("")

        return "\n".join(lines)


