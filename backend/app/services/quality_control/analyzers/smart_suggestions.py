"""
智能修正建议引擎 - 三维质控v2.0优化

功能：
1. 为每个检测到的问题提供具体、可操作的修改建议
2. 生成自动修正方案(需要用户确认)
3. 基于问题类型和上下文生成个性化建议

@date: 2026-04-14
@version: v2.0.0
"""
from typing import Dict, List, Any, Optional
from app.core.logger import get_logger

logger = get_logger("quality_control.smart_suggestions")


class SmartSuggestionEngine:
    """
    智能修正建议引擎

    提供：
    1. 具体修改建议(人工修正)
    2. 自动修正方案(一键修正)
    3. 修改前后对比
    """

    def __init__(self):
        self.suggestion_templates = self._init_templates()

    def _init_templates(self) -> Dict:
        """初始化建议模板"""
        return {
            "单元过短": {
                "manual_suggestion": "建议补充以下要素：\n1. 核心冲突或转折点\n2. 人物行动或决策\n3. 情节推进的关键信息\n4. 与前后单元的衔接",
                "auto_fix_available": False,
                "priority": "high"
            },
            "单元衔接": {
                "manual_suggestion": "建议在单元末尾或开头添加过渡句，例如：\n- \"与此同时...\"\n- \"随后...\"\n- \"然而，事情并没有这么简单...\"\n- \"就在所有人都以为...\"",
                "auto_fix_available": True,
                "priority": "medium"
            },
            "节奏平淡": {
                "manual_suggestion": "建议在该区域增加以下元素之一：\n1. 突发的冲突或危机\n2. 重要信息的揭露\n3. 人物关系的转折\n4. 意外的事件或反转",
                "auto_fix_available": False,
                "priority": "high"
            },
            "状态矛盾": {
                "manual_suggestion": "请检查人物状态描述，建议：\n1. 明确状态转换的时间点\n2. 添加状态转换的铺垫或说明\n3. 使用转折词连接矛盾状态\n4. 修正其中一个矛盾描述",
                "auto_fix_available": True,
                "priority": "critical"
            },
            "大纲偏离": {
                "manual_suggestion": "请对比全局大纲，检查：\n1. 该单元的核心情节是否符合大纲设定\n2. 人物行为是否偏离大纲规划\n3. 是否遗漏了大纲中的关键事件\n4. 世界观设定是否与大纲一致",
                "auto_fix_available": False,
                "priority": "high"
            },
            "核心要素缺失": {
                "manual_suggestion": "建议在单元概述中补充以下要素：\n1. 主角的目标或动机\n2. 当前的核心冲突\n3. 情节的转折点\n4. 人物的成长或变化",
                "auto_fix_available": False,
                "priority": "medium"
            }
        }

    def generate_suggestions(
        self,
        issues: List[Dict],
        chapters_data: List[Dict],
        context: Dict = None
    ) -> List[Dict]:
        """
        为问题生成智能修正建议

        Args:
            issues: 问题列表
            chapters_data: 单元概述数据
            context: 上下文信息(可选)

        Returns:
            带建议的问题列表
        """
        enhanced_issues = []

        for issue in issues:
            category = issue.get("category", "")
            dimension = issue.get("dimension", "")

            # 获取模板建议
            template = self.suggestion_templates.get(category, {})

            # 生成具体建议
            specific_suggestion = self._generate_specific_suggestion(
                issue, chapters_data, context
            )

            # 生成自动修正方案
            auto_fix = None
            if template.get("auto_fix_available", False):
                auto_fix = self._generate_auto_fix(
                    issue, chapters_data, context
                )

            # 增强问题信息
            enhanced_issue = issue.copy()
            enhanced_issue["suggestion"] = specific_suggestion or template.get(
                "manual_suggestion", issue.get("suggestion", "")
            )
            enhanced_issue["auto_fix"] = auto_fix
            enhanced_issue["priority"] = template.get("priority", "medium")
            enhanced_issue["fix_difficulty"] = self._estimate_fix_difficulty(
                issue
            )

            enhanced_issues.append(enhanced_issue)

        return enhanced_issues

    def _generate_specific_suggestion(
        self,
        issue: Dict,
        chapters_data: List[Dict],
        context: Dict = None
    ) -> str:
        """生成具体的修改建议"""
        category = issue.get("category", "")
        location = issue.get("location", {})
        chapter_number = location.get("chapter_number", 0)

        # 获取相关单元内容
        related_content = ""
        if chapter_number > 0 and chapter_number <= len(chapters_data):
            chapter = chapters_data[chapter_number - 1]
            related_content = chapter.get(
                "content", "") or chapter.get("summary", "")

        # 根据问题类型生成建议
        if category == "单元过短":
            return self._suggest_for_short_unit(related_content, issue)
        elif category == "单元衔接":
            return self._suggest_for_transition(related_content, issue, chapters_data, chapter_number)
        elif category == "节奏平淡":
            return self._suggest_for_pacing(related_content, issue, chapters_data, chapter_number)
        elif category == "状态矛盾":
            return self._suggest_for_state_contradiction(related_content, issue)
        elif category == "大纲偏离":
            return self._suggest_for_outline_deviation(related_content, issue, context)
        else:
            return ""

    def _suggest_for_short_unit(self, content: str, issue: Dict) -> str:
        """为单元过短生成建议"""
        current_length = len(content)
        target_length = 150  # 目标长度

        suggestions = [
            f"当前单元仅{current_length}字，建议扩展到{target_length}字左右。",
            "",
            "建议补充以下内容：",
            "1. **核心冲突**：描述本单元的主要矛盾或挑战",
            "2. **人物行动**：主角或关键人物的具体行动和决策",
            "3. **情节推进**：推动故事发展的关键事件",
            "4. **情感描写**：人物的内心活动或情感变化",
            "",
            "示例扩写方向：",
            "- 如果是战斗场景：补充战斗细节、招式描写、心理活动",
            "- 如果是对话场景：增加对话内容、表情动作、氛围描写",
            "- 如果是过渡场景：铺垫后续情节、埋下伏笔"
        ]

        return "\n".join(suggestions)

    def _suggest_for_transition(
        self,
        content: str,
        issue: Dict,
        chapters_data: List[Dict],
        chapter_number: int
    ) -> str:
        """为单元衔接问题生成建议"""
        suggestions = [
            "建议添加过渡句以增强单元之间的连贯性。",
            "",
            "可选过渡方式：",
            "",
            "1. **时间过渡**：",
            "   - \"三天后...\"",
            "   - \"次日清晨...\"",
            "   - \"就在当天夜里...\"",
            "",
            "2. **因果过渡**：",
            "   - \"正是因为这个决定，导致了...\"",
            "   - \"由于之前的疏忽，现在...\"",
            "",
            "3. **转折过渡**：",
            "   - \"然而，事情并没有想象中那么简单...\"",
            "   - \"就在所有人都以为结束时，意外发生了...\"",
            "",
            "4. **并行过渡**：",
            "   - \"与此同时，在另一个地方...\"",
            "   - \"而另一边，主角并不知道...\""
        ]

        # 如果有前后单元，给出更具体的建议
        if chapter_number > 0 and chapter_number <= len(chapters_data):
            prev_chapter = chapters_data[chapter_number -
                                         2] if chapter_number > 1 else None
            next_chapter = chapters_data[chapter_number] if chapter_number < len(
                chapters_data) else None

            if prev_chapter and next_chapter:
                prev_content = prev_chapter.get(
                    "content", "") or prev_chapter.get("summary", "")
                next_content = next_chapter.get(
                    "content", "") or next_chapter.get("summary", "")

                suggestions.append("")
                suggestions.append("具体建议：")
                suggestions.append(
                    f"- 当前单元结尾可以呼应：{prev_content[:50]}...")
                suggestions.append(
                    f"- 下一单元开头可以衔接：{next_content[:50]}...")

        return "\n".join(suggestions)

    def _suggest_for_pacing(
        self,
        content: str,
        issue: Dict,
        chapters_data: List[Dict],
        chapter_number: int
    ) -> str:
        """为节奏平淡生成建议"""
        suggestions = [
            "该区域情节节奏较为平淡，建议增加以下元素之一：",
            "",
            "1. **突发冲突**：",
            "   - 敌人突袭",
            "   - 意外发现",
            "   - 内部矛盾爆发",
            "",
            "2. **信息揭露**：",
            "   - 重要秘密曝光",
            "   - 真相浮出水面",
            "   - 身份被揭穿",
            "",
            "3. **人物转折**：",
            "   - 盟友背叛",
            "   - 敌人倒戈",
            "   - 感情突破",
            "",
            "4. **环境变化**：",
            "   - 自然灾害",
            "   - 政治局势变化",
            "   - 世界观规则改变"
        ]

        return "\n".join(suggestions)

    def _suggest_for_state_contradiction(self, content: str, issue: Dict) -> str:
        """为状态矛盾生成建议"""
        metadata = issue.get("metadata", {})
        contradictory_states = metadata.get("contradictory_states", [])

        suggestions = [
            "检测到人物状态描述存在矛盾，请按以下方式修正：",
            "",
            "1. **明确状态转换**：",
            "   - 添加状态转换的明确时间点",
            "   - 说明转换的原因或过程",
            "",
            "2. **使用转折词**：",
            "   - \"原本是...但是后来...\"",
            "   - \"虽然...然而...\"",
            "",
            "3. **修正矛盾描述**：",
            f"   - 检查\"{contradictory_states[0] if contradictory_states else '?'}\"和\"",
            f"{contradictory_states[1] if len(contradictory_states) > 1 else '?'}\"",
            "   - 保留正确的描述，删除或修改错误的描述",
            "",
            "4. **添加铺垫**：",
            "   - 在状态转换前增加铺垫描写",
            "   - 让状态变化更加自然合理"
        ]

        return "\n".join(suggestions)

    def _suggest_for_outline_deviation(
        self,
        content: str,
        issue: Dict,
        context: Dict = None
    ) -> str:
        """为大纲偏离生成建议"""
        metadata = issue.get("metadata", {})
        match_rate = metadata.get("match_rate", 0)

        suggestions = [
            f"该单元与全局大纲的匹配度较低({match_rate:.0%})，建议：",
            "",
            "1. **对比大纲**：",
            "   - 重新阅读全局大纲中对应部分",
            "   - 确认该单元应该包含的关键情节",
            "",
            "2. **补充关键要素**：",
            "   - 添加大纲中规划的核心事件",
            "   - 确保人物行为符合大纲设定",
            "   - 检查世界观设定是否一致",
            "",
            "3. **调整情节走向**：",
            "   - 如果当前情节是合理的创新，需要在大纲中补充说明",
            "   - 如果是偏离，需要修正回大纲规划的轨道",
            "",
            "4. **增强关联性**：",
            "   - 明确该单元与主线的关联",
            "   - 呼应前文埋下的伏笔",
            "   - 为后续情节做铺垫"
        ]

        return "\n".join(suggestions)

    def _generate_auto_fix(
        self,
        issue: Dict,
        chapters_data: List[Dict],
        context: Dict = None
    ) -> Optional[Dict]:
        """
        生成自动修正方案

        Returns:
            自动修正方案字典，包含：
            - type: 修正类型
            - description: 修正说明
            - original: 原始内容
            - fixed: 修正后内容
            - confidence: 置信度(0-1)
        """
        category = issue.get("category", "")
        location = issue.get("location", {})
        chapter_number = location.get("chapter_number", 0)

        if chapter_number <= 0 or chapter_number > len(chapters_data):
            return None

        chapter = chapters_data[chapter_number - 1]
        original_content = chapter.get(
            "content", "") or chapter.get("summary", "")

        # 根据问题类型生成修正方案
        if category == "单元衔接":
            return self._auto_fix_transition(original_content, issue, chapters_data, chapter_number)
        elif category == "状态矛盾":
            return self._auto_fix_state_contradiction(original_content, issue)
        else:
            return None

    def _auto_fix_transition(
        self,
        content: str,
        issue: Dict,
        chapters_data: List[Dict],
        chapter_number: int
    ) -> Dict:
        """自动修正单元衔接问题"""
        # 在单元末尾添加过渡句
        transition_sentences = [
            "与此同时，故事的另一条线索正在悄然展开...",
            "然而，这仅仅是开始，更大的挑战还在后面...",
            "随后发生的事情，超出了所有人的预料...",
            "正是这个决定，改变了整个故事的走向..."
        ]

        # 选择合适的过渡句
        transition = transition_sentences[chapter_number % len(
            transition_sentences)]

        fixed_content = content.rstrip() + f"\n\n{transition}"

        return {
            "type": "add_transition",
            "description": f"在单元末尾添加过渡句：{transition}",
            "original": content,
            "fixed": fixed_content,
            "confidence": 0.7,
            "requires_review": True
        }

    def _auto_fix_state_contradiction(
        self,
        content: str,
        issue: Dict
    ) -> Dict:
        """自动修正状态矛盾"""
        metadata = issue.get("metadata", {})
        contradictory_states = metadata.get("contradictory_states", [])

        if len(contradictory_states) < 2:
            return None

        state1, state2 = contradictory_states[0], contradictory_states[1]

        # 尝试添加转折词来合理化矛盾
        transition_phrases = [
            f"原本是{state1}的状态，但是后来发生了转变，变成了{state2}",
            f"虽然经历了{state1}，然而在关键时刻却呈现{state2}的状态",
            f"从{state1}到{state2}的转变，源于一个意外的发现"
        ]

        # 选择最合适的过渡短语
        transition = transition_phrases[0]

        # 简单替换(实际应该更智能)
        fixed_content = content.replace(
            state1, transition, 1) if state1 in content else content

        return {
            "type": "resolve_contradiction",
            "description": f"添加状态转换说明，合理化'{state1}'和'{state2}'的矛盾",
            "original": content,
            "fixed": fixed_content,
            "confidence": 0.6,
            "requires_review": True
        }

    def _estimate_fix_difficulty(self, issue: Dict) -> str:
        """估算修正难度"""
        category = issue.get("category", "")
        severity = issue.get("severity", "info")

        # 简单估算逻辑
        if severity == "critical":
            return "hard"
        elif category in ["状态矛盾", "大纲偏离"]:
            return "medium"
        elif category in ["单元衔接", "单元过短"]:
            return "easy"
        else:
            return "medium"


# ==================== 全局实例 ====================

_smart_suggestion_engine = None


def get_smart_suggestion_engine() -> SmartSuggestionEngine:
    """获取智能修正建议引擎单例"""
    global _smart_suggestion_engine

    if _smart_suggestion_engine is None:
        _smart_suggestion_engine = SmartSuggestionEngine()

    return _smart_suggestion_engine
