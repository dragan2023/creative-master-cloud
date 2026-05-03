"""
全局大纲质控 - 人物与世界观分析器 (GlobalCharacterWorldviewAnalyzer)

检测人物设定、世界观规则一致性

@date: 2026-04-24
@version: v1.1.0
"""
from typing import Dict, List, Any

from app.core.logger import get_logger
from ._common import call_llm_with_retry, parse_llm_json_response

logger = get_logger("quality_control.analyzers.global_quality")


class GlobalCharacterWorldviewAnalyzer:
    """人物与世界观分析器 - 检测人物设定和世界观规则一致性"""

    async def analyze(
        self,
        global_outline: str,
        project: Any,
        rule_results: Dict = None,
        depth: str = "standard",
        db=None,
        user_id: int = 0,
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        **kwargs
    ) -> Dict:
        """执行人物与世界观分析(v1.0防错版)"""
        issues = []

        # 1. 人物状态矛盾检测
        contradiction_issues = self._analyze_character_contradictions(
            global_outline)
        issues.extend(contradiction_issues)

        # 2. 人物设定完整性检测
        if character_profiles:
            completeness_issues = self._analyze_character_completeness(
                global_outline, character_profiles
            )
            issues.extend(completeness_issues)

        # 3. 世界观规则一致性检测
        if worldview_settings:
            worldview_issues = self._analyze_worldview_consistency(
                global_outline, worldview_settings
            )
            issues.extend(worldview_issues)

        # 4. LLM深度分析人物关系合理性
        if depth in ["standard", "deep"]:
            llm_issues = await self._analyze_character_relations_with_llm(
                global_outline, depth, db, user_id
            )
            if isinstance(llm_issues, list):
                issues.extend(llm_issues)

        # 5. 应用用户反馈学习的阈值调整
        issues = self._apply_feedback_thresholds(user_id, issues)

        # 计算得分
        score = self._calculate_character_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "character_count": len(character_profiles) if character_profiles else 0,
                "analysis_depth": depth
            }
        }

    def _analyze_character_contradictions(self, global_outline: str) -> List[Dict]:
        """分析人物状态矛盾(复用单元概述的矛盾词对检测)"""
        issues = []
        content = global_outline.lower()

        contradictory_states = [
            ("生", "死"),
            ("活着", "死亡"),
            ("存活", "死去"),
            ("胜利", "失败"),
            ("成功", "失败"),
            ("安全", "危险")
        ]

        exclude_phrases = [
            "生死关头", "生死存亡", "生死搏", "生死战", "决一死战",
            "胜利失败", "成败", "成败得失",
            "安全危险", "安危",
            "复活", "重生", "重生后", "复活后"
        ]

        for state1, state2 in contradictory_states:
            if state1 in content and state2 in content:
                is_false_positive = any(
                    phrase in content for phrase in exclude_phrases
                )

                if is_false_positive:
                    continue

                has_transition = any(
                    word in content
                    for word in ["但是", "然而", "却", "没想到", "意外",
                                 "复活", "重生", "醒来", "恢复", "转变"]
                )

                if not has_transition:
                    issues.append({
                        "id": f"GC-CONTRADICTION-{len(issues)+1}",
                        "dimension": "global_character_worldview",
                        "category": "状态矛盾",
                        "severity": "warning",
                        "location": {},
                        "description": f"全局大纲中同时出现'{state1}'和'{state2}'的状态描述,可能存在逻辑矛盾",
                        "evidence": f"矛盾词对: {state1}/{state2}",
                        "suggestion": "请检查是否存在状态转换的合理铺垫,或修正矛盾描述",
                        "metadata": {"contradictory_states": [state1, state2]}
                    })

        return issues

    def _analyze_character_completeness(
        self,
        global_outline: str,
        character_profiles: List[Dict]
    ) -> List[Dict]:
        """分析人物设定完整性"""
        issues = []

        for char in character_profiles[:10]:  # 最多检测10个主要人物
            char_name = char.get("name", "")
            if not char_name:
                continue

            # 检查人物是否在大网中有详细描述
            char_mentions = global_outline.count(char_name)

            if char_mentions == 0:
                issues.append({
                    "id": f"GC-MISSING-{char_name}",
                    "dimension": "global_character_worldview",
                    "category": "人物缺失",
                    "severity": "warning",
                    "location": {},
                    "description": f"主要人物'{char_name}'在全局大纲中未被提及",
                    "evidence": f"人物设定中存在,但大纲中未出现",
                    "suggestion": "建议在大网中补充该人物的背景、目标和作用",
                    "metadata": {"character_name": char_name}
                })

        return issues

    def _analyze_worldview_consistency(
        self,
        global_outline: str,
        worldview_settings: Dict
    ) -> List[Dict]:
        """分析世界观规则一致性"""
        issues = []

        # 简单检测: 检查世界观中的关键规则是否在大网中被遵循
        rules = worldview_settings.get("rules", [])
        for rule in rules[:5]:  # 最多检测5条规则
            rule_text = rule.get("description", "")
            if not rule_text:
                continue

            # 检查是否有明显的规则冲突(简化版)
            if "禁止" in rule_text or "不允许" in rule_text:
                # 检测大纲中是否有违反描述
                pass  # 需要更复杂的NLP分析,暂时跳过

        return issues

    async def _analyze_character_relations_with_llm(
        self,
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM深度分析人物关系合理性(防错版: 超时1200秒)"""
        issues = []

        try:
            logger.info("[人物与世界观分析] 开始LLM人物关系分析...")
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[人物与世界观分析] 无法获取LLM提供者,跳过深度分析")
                return issues

            logger.info("[人物与世界观分析] 成功获取LLM提供者，开始调用...")

            outline_sample = global_outline  # 不再截断大纲，完整上下文有助于LLM准确分析

            prompt = f"""你是专业的人物关系分析师。

    请分析以下全局大纲中的人物设定和关系:

    【全局大纲内容】(前15000字)
    {outline_sample}

    【分析要求】
    1. 检测主要人物是否有明确的动机和目标
    2. 评估人物关系是否合理(是否存在突兀的转变)
    3. 检测人物性格是否前后一致
    4. 评估世界观规则是否自洽

    【输出格式】
    ```json
    {{
      "issues": [
        {{
          "type": "问题类型",
          "severity": "warning|critical|info",
          "description": "详细描述",
          "character": "涉及的人物名称"
        }}
      ]
    }}
    ```

    如果没有问题,返回空数组。
    """

            # ✅ 使用带重试机制的LLM调用
            response = await call_llm_with_retry(
                llm_provider,
                prompt=prompt,
                temperature=0.3,
                timeout=1200,
                context="人物与世界观分析"
            )

            response_text = response.content if hasattr(
                response, 'content') else str(response)

            # ✅ 使用统一的JSON解析函数（带三级修复机制）
            result = parse_llm_json_response(response_text, logger, "人物与世界观分析")

            for issue in result.get("issues", []):
                issues.append({
                    "id": f"GC-REL-{len(issues)+1}",
                    "dimension": "global_character_worldview",
                    "category": issue.get("type", "人物关系问题"),
                    "severity": issue.get("severity", "warning"),
                    "location": {},
                    "description": issue.get("description", ""),
                    "evidence": f"涉及人物: {issue.get('character', '未知')}",
                    "suggestion": "建议修正人物设定或关系描述",
                    "metadata": {
                        "analysis_method": "llm",
                        "character": issue.get("character")
                    }
                })

        except Exception as e:
            logger.warning(f"[人物与世界观分析] LLM分析异常: {str(e)}")

        return issues

    def _calculate_character_score(self, issues: List[Dict]) -> float:
        """计算人物与世界观得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 20
            elif severity == "warning":
                score -= 10
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))

    def _apply_feedback_thresholds(self, user_id: int, issues: List[Dict]) -> List[Dict]:
        """应用用户反馈学习的阈值调整(同GlobalStructureAnalyzer)"""
        try:
            from ..feedback_learning import get_feedback_manager
            feedback_manager = get_feedback_manager()

            filtered_issues = []
            for issue in issues:
                dimension = issue.get("dimension", "")
                category = issue.get("category", "")
                fp_rate = feedback_manager.get_false_positive_rate(
                    user_id, dimension, category
                )

                if fp_rate > 0.5:
                    severity = issue.get("severity", "info")
                    if severity == "warning":
                        issue["severity"] = "info"
                        issue["metadata"]["adjusted_by_feedback"] = True
                    elif severity == "critical":
                        issue["severity"] = "warning"
                        issue["metadata"]["adjusted_by_feedback"] = True
                    if fp_rate > 0.8:
                        continue

                filtered_issues.append(issue)

            return filtered_issues

        except Exception as e:
            logger.warning(f"[人物与世界观分析] 应用反馈阈值失败: {str(e)}")
            return issues
