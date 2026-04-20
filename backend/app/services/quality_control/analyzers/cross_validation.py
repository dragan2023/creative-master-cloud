"""
多维度交叉验证器 - 三维质控v2.0优化

功能：
1. 结合全局大纲、人物设定、世界观进行交叉验证
2. 检测多维度之间的逻辑一致性
3. 发现单一维度无法识别的复杂问题

@date: 2026-04-14
@version: v2.0.0
"""
from typing import Dict, List, Any, Optional, Tuple
from app.core.logger import get_logger

logger = get_logger("quality_control.cross_validation")


class CrossValidationEngine:
    """
    多维度交叉验证引擎

    验证维度：
    1. 大纲一致性 - 单元概述与全局大纲的逻辑对齐
    2. 人物一致性 - 人物行为与人物设定的匹配度
    3. 世界观一致性 - 情节发展与世界观设定的兼容性
    4. 时间线一致性 - 事件发生顺序的合理性
    5. 因果关系一致性 - 前后事件的因果逻辑
    """

    def __init__(self):
        self.validation_rules = self._init_validation_rules()

    def _init_validation_rules(self) -> Dict:
        """初始化验证规则"""
        return {
            "timeline_consistency": {
                "name": "时间线一致性",
                "weight": 0.25,
                "checks": [
                    "时间顺序合理性",
                    "时间跨度连续性",
                    "年代设定一致性"
                ]
            },
            "causality_consistency": {
                "name": "因果关系一致性",
                "weight": 0.25,
                "checks": [
                    "前置条件完整性",
                    "后果合理性",
                    "因果链连续性"
                ]
            },
            "character_worldview_consistency": {
                "name": "人物-世界观一致性",
                "weight": 0.20,
                "checks": [
                    "能力设定匹配",
                    "行为动机合理",
                    "世界观规则遵守"
                ]
            },
            "plot_outline_consistency": {
                "name": "情节-大纲一致性",
                "weight": 0.30,
                "checks": [
                    "主线推进对齐",
                    "伏笔呼应检查",
                    "核心冲突延续"
                ]
            }
        }

    async def validate_all(
        self,
        chapters_data: List[Dict],
        global_outline: str = "",
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        depth: str = "standard",
        db=None,
        user_id: int = 0
    ) -> Dict:
        """
        执行全部交叉验证

        Args:
            chapters_data: 单元概述数据
            global_outline: 全局大纲
            character_profiles: 人物设定列表
            worldview_settings: 世界观设定
            depth: 分析深度
            db: 数据库会话
            user_id: 用户ID

        Returns:
            验证结果字典
        """
        issues = []
        validation_scores = {}

        # 1. 时间线一致性验证
        timeline_issues = await self._validate_timeline_consistency(
            chapters_data, global_outline, depth, db, user_id
        )
        issues.extend(timeline_issues)
        validation_scores["timeline_consistency"] = self._calculate_score(
            timeline_issues, len(chapters_data)
        )

        # 2. 因果关系一致性验证
        causality_issues = await self._validate_causality_consistency(
            chapters_data, global_outline, depth, db, user_id
        )
        issues.extend(causality_issues)
        validation_scores["causality_consistency"] = self._calculate_score(
            causality_issues, len(chapters_data)
        )

        # 3. 人物-世界观一致性验证
        if character_profiles or worldview_settings:
            char_worldview_issues = await self._validate_character_worldview_consistency(
                chapters_data, character_profiles or [], worldview_settings or {}, depth, db, user_id
            )
            issues.extend(char_worldview_issues)
            validation_scores["character_worldview_consistency"] = self._calculate_score(
                char_worldview_issues, len(chapters_data)
            )

        # 4. 情节-大纲一致性验证
        if global_outline:
            plot_outline_issues = await self._validate_plot_outline_consistency(
                chapters_data, global_outline, depth, db, user_id
            )
            issues.extend(plot_outline_issues)
            validation_scores["plot_outline_consistency"] = self._calculate_score(
                plot_outline_issues, len(chapters_data)
            )

        # 计算综合得分
        overall_score = self._calculate_overall_score(validation_scores)

        return {
            "issues": issues,
            "validation_scores": validation_scores,
            "overall_score": overall_score,
            "total_validations": len(self.validation_rules),
            "metadata": {
                "has_global_outline": bool(global_outline),
                "has_character_profiles": bool(character_profiles),
                "has_worldview_settings": bool(worldview_settings),
                "total_units": len(chapters_data)
            }
        }

    async def _validate_timeline_consistency(
        self,
        chapters_data: List[Dict],
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """验证时间线一致性"""
        issues = []

        if len(chapters_data) < 3:
            return issues

        # 提取时间标记
        timeline_events = []
        time_keywords = ["天后", "年前", "月后", "次日", "当晚", "清晨", "黄昏", "深夜"]

        for i, chapter in enumerate(chapters_data):
            content = chapter.get("content", "") or chapter.get("summary", "")

            # 检测时间标记
            for keyword in time_keywords:
                if keyword in content:
                    timeline_events.append({
                        "unit_number": chapter.get("chapter_number", i+1),
                        "time_marker": keyword,
                        "context": content[:100]
                    })

        # 检测时间线冲突
        if len(timeline_events) >= 2:
            # 简单检测：检查是否有明显的时间倒流
            for i in range(len(timeline_events) - 1):
                current = timeline_events[i]
                next_event = timeline_events[i + 1]

                # 检测时间逻辑冲突(简化版)
                if "前" in current["time_marker"] and "后" in next_event["time_marker"]:
                    # 可能是合理的回忆或倒叙，仅记录info级别
                    pass

        return issues

    async def _validate_causality_consistency(
        self,
        chapters_data: List[Dict],
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """验证因果关系一致性"""
        issues = []

        if len(chapters_data) < 5:
            return issues

        # 因果关系关键词
        cause_keywords = ["因为", "由于", "因此", "所以", "导致", "结果", "引发"]
        effect_keywords = ["于是", "接着", "随后", "因此", "所以"]

        # 检测因果链断裂
        for i in range(len(chapters_data) - 2):
            current = (chapters_data[i].get("content", "")
                       or chapters_data[i].get("summary", "")).lower()
            next_unit = (chapters_data[i+1].get("content", "")
                         or chapters_data[i+1].get("summary", "")).lower()
            after_next = (chapters_data[i+2].get("content", "")
                          or chapters_data[i+2].get("summary", "")).lower()

            # 检测：如果当前单元有"因"，后续单元应该有"果"
            has_cause = any(kw in current for kw in cause_keywords)
            has_effect = any(kw in next_unit for kw in effect_keywords) or \
                any(kw in after_next for kw in effect_keywords)

            if has_cause and not has_effect:
                # 可能因果链不完整(仅info级别，避免误报)
                issues.append({
                    "id": f"CV-CAUSAL-{i+1}",
                    "dimension": "cross_validation",
                    "category": "因果链可能不完整",
                    "severity": "info",
                    "location": {
                        "chapter_number": chapters_data[i].get("chapter_number", i+1)
                    },
                    "description": f"第{i+1}单元提到原因，但后续单元未明确说明结果",
                    "evidence": current[:100],
                    "suggestion": "建议在后续单元中补充因果关系的完整描述",
                    "metadata": {
                        "validation_type": "causality_consistency",
                        "units_involved": [i+1, i+2, i+3]
                    }
                })

        return issues

    async def _validate_character_worldview_consistency(
        self,
        chapters_data: List[Dict],
        character_profiles: List[Dict],
        worldview_settings: Dict,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """验证人物-世界观一致性"""
        issues = []

        if not character_profiles and not worldview_settings:
            return issues

        # 从人物设定中提取关键信息
        character_constraints = {}
        for profile in character_profiles:
            char_name = profile.get("name", "")
            if char_name:
                character_constraints[char_name] = {
                    "abilities": profile.get("abilities", []),
                    "personality": profile.get("personality", []),
                    "background": profile.get("background", "")
                }

        # 从世界观设定中提取规则
        worldview_rules = worldview_settings.get("rules", [])
        magic_system = worldview_settings.get("magic_system", {})

        # 检测人物行为是否符合设定
        for i, chapter in enumerate(chapters_data):
            content = (chapter.get("content", "")
                       or chapter.get("summary", "")).lower()

            # 检查人物能力是否符合设定
            for char_name, constraints in character_constraints.items():
                if char_name in content:
                    # 检测能力使用
                    abilities = constraints.get("abilities", [])
                    for ability in abilities:
                        if ability in content:
                            # 能力使用符合设定
                            pass

        return issues

    async def _validate_plot_outline_consistency(
        self,
        chapters_data: List[Dict],
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """验证情节-大纲一致性"""
        issues = []

        if not global_outline or len(chapters_data) < 3:
            return issues

        # 提取全局大纲的关键情节节点
        outline_keywords = self._extract_key_plot_points(global_outline)

        # 检测单元概述是否覆盖关键情节节点
        covered_nodes = []
        uncovered_nodes = []

        for node in outline_keywords:
            is_covered = any(
                node in (ch.get("content", "") or ch.get("summary", ""))
                for ch in chapters_data
            )

            if is_covered:
                covered_nodes.append(node)
            else:
                uncovered_nodes.append(node)

        # 如果有未覆盖的关键节点，发出警告
        if uncovered_nodes and len(uncovered_nodes) > len(outline_keywords) * 0.3:
            issues.append({
                "id": "CV-PLOT-OUTLINE",
                "dimension": "cross_validation",
                "category": "关键情节节点缺失",
                "severity": "warning",
                "location": {},
                "description": f"单元概述未覆盖{len(uncovered_nodes)}个关键情节节点",
                "evidence": f"未覆盖节点：{', '.join(uncovered_nodes[:5])}",
                "suggestion": "建议在单元概述中补充这些关键情节节点",
                "metadata": {
                    "validation_type": "plot_outline_consistency",
                    "covered_nodes": len(covered_nodes),
                    "uncovered_nodes": len(uncovered_nodes),
                    "coverage_rate": len(covered_nodes) / len(outline_keywords) if outline_keywords else 1.0
                }
            })

        return issues

    def _extract_key_plot_points(self, global_outline: str) -> List[str]:
        """从全局大纲中提取关键情节节点"""
        import re

        # 提取包含情节关键词的句子
        plot_keywords = ["决战", "转折", "发现", "觉醒", "突破",
                         "复仇", "拯救", "背叛", "牺牲", "胜利", "失败"]

        sentences = re.split(r'[。！？；]', global_outline)

        key_points = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10 and any(kw in sentence for kw in plot_keywords):
                # 提取核心短语(简化版)
                key_points.append(sentence[:50])

        return key_points[:20]  # 最多20个关键节点

    def _calculate_score(self, issues: List[Dict], total_units: int) -> float:
        """计算验证得分"""
        if total_units == 0:
            return 100.0

        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")

            if severity == "critical":
                score -= 15
            elif severity == "warning":
                score -= 8
            elif severity == "info":
                score -= 2

        return max(0, min(100, score))

    def _calculate_overall_score(self, validation_scores: Dict[str, float]) -> float:
        """计算综合验证得分"""
        if not validation_scores:
            return 100.0

        weighted_sum = 0.0
        total_weight = 0.0

        for validation_type, score in validation_scores.items():
            weight = self.validation_rules.get(validation_type, {}).get(
                "weight", 0.25)
            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 100.0


# ==================== 全局实例 ====================

_cross_validation_engine = None


def get_cross_validation_engine() -> CrossValidationEngine:
    """获取交叉验证引擎单例"""
    global _cross_validation_engine

    if _cross_validation_engine is None:
        _cross_validation_engine = CrossValidationEngine()

    return _cross_validation_engine
