"""单元概述质量分析器 - UnitCharacterAnalyzer"""
"""
单元概述专用质量管控分析器 v3.0

专门针对单元概述的特点设计，与正文六维度质控模块完全独立。

单元概述特点：
- 长度短（每单元50-300字）
- 概要性质（不是详细正文）
- 强调结构连贯性、人物发展逻辑、与全局大纲一致性

五维度检测机制（v3.0全面深度检测）：
1. unit_structure（单元结构层）- 使用LLM深度检测单元长度、衔接、节奏
2. unit_character（人物发展层）- 使用LLM深度检测人物状态、关系、成长
3. unit_consistency（一致性层）- 使用LLM深度检测与全局大纲的偏离度
4. unit_timeline_space（时间线与空间逻辑层）- 新增，检测位置、时间线、因果、状态连续性
5. unit_ooc（人物OOC层）- 新增，检测人物是否违背人设

v3.0 核心改动：
- 取消所有轻量检测，一律使用LLM深度检测
- 新增时间线空间分析器（人物位置、出场时间线、事件因果、状态连续性）
- 新增人物OOC分析器（性格违背、动机矛盾、说话方式、能力超纲）

@date: 2026-04-19
@version: v3.0.0
@author: 周金磊
"""
from typing import Dict, List, Any, Optional
from app.core.logger import get_logger
from app.services.quality_control.llm_retry_helper import llm_call_with_retry
from .unit_structure_analyzer import UnitStructureAnalyzer

logger = get_logger(__name__)


class UnitCharacterAnalyzer:
    """人物发展分析器 - 使用LLM深度检测人物状态变化和成长逻辑"""

    async def analyze(
        self,
        chapters_data: List[Dict],
        project: Any,
        rule_results: Dict = None,
        depth: str = "deep",
        db=None,
        user_id: int = 0,
        global_outline: str = "",
        character_profiles: List[Dict] = None,
        **kwargs
    ) -> Dict:
        """执行人物发展分析（全面深度检测模式）"""
        issues = []

        # 1. LLM深度检测：人物状态变化合理性
        state_issues = await self._analyze_state_changes_with_llm(chapters_data, db, user_id)
        issues.extend(state_issues)

        # 2. LLM深度检测：人物关系发展逻辑
        relationship_issues = await self._analyze_relationships_with_llm(chapters_data, db, user_id)
        issues.extend(relationship_issues)

        # 计算得分
        score = self._calculate_character_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    # ===== 已废弃的轻量检测方法 =====

    def _analyze_character_state_changes(self, chapters_data: List[Dict]) -> List[Dict]:
        """分析人物状态变化（已废弃，使用LLM深度检测替代）"""
        return []

    def _analyze_character_relationships(self, chapters_data: List[Dict]) -> List[Dict]:
        """分析人物关系变化（已废弃，使用LLM深度检测替代）"""
        return []

    # ===== LLM深度检测方法 =====

    async def _analyze_state_changes_with_llm(self, chapters_data: List[Dict], db, user_id: int) -> List[Dict]:
        """使用LLM深度检测人物状态变化合理性"""
        issues = []

        if not chapters_data:
            return issues

        batch_size = 15
        for batch_start in range(0, len(chapters_data), batch_size):
            batch_end = min(batch_start + batch_size, len(chapters_data))
            batch_chapters = chapters_data[batch_start:batch_end]

            batch_content = []
            for ch in batch_chapters:
                content = ch.get("content", "") or ch.get("summary", "")
                batch_content.append(
                    f"第{ch.get('chapter_number', 0)}单元：{content}"
                )

            try:
                from app.agents.llm_manager import get_llm_manager
                llm_manager = get_llm_manager()
                llm_provider = await llm_manager.get_provider_from_db(db, user_id)

                if not llm_provider:
                    logger.warning("[人物发展分析] 无法获取LLM提供者，跳过状态检测")
                    break

                prompt = f"""你是专业的人物发展审核专家。

请分析以下单元概述中人物状态变化的合理性，检测是否存在矛盾或不合理之处：

【单元概述批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【检测要求】
1. 人物生死状态是否矛盾？（如某章死亡，后续章节却活着且无复活描写）
2. 人物受伤/康复状态是否合理？
3. 人物胜利/失败状态是否连续？
4. 人物安全/危险状态转换是否有铺垫？

【输出格式】
```json
{{
  "state_issues": [
    {{
      "unit_number": 单元号,
      "character": "人物名（如有）",
      "issue_type": "生死矛盾|受伤矛盾|状态突变",
      "description": "详细描述问题",
      "severity": "critical|warning"
    }}
  ]
}}
```

如果没有问题，返回空数组。
"""

                response = await llm_call_with_retry(llm_provider, prompt=prompt, temperature=0.2, context="单元质控分析")
                response_text = response.content if hasattr(
                    response, 'content') else str(response)

                import re
                import json
                json_match = re.search(
                    r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    result = json.loads(json_match.group(1))
                    for issue in result.get("state_issues", []):
                        issues.append({
                            "id": f"UC-LLM-{len(issues)+1}",
                            "dimension": "unit_character",
                            "category": issue.get("issue_type", "状态矛盾"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": issue.get("unit_number", 0),
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                            },
                            "description": issue.get("description", ""),
                            "evidence": f"第{issue.get('unit_number', '?')}单元",
                            "suggestion": "请检查是否存在状态转换的合理铺垫，或修正矛盾描述",
                            "metadata": {
                                "unit_number": issue.get("unit_number"),
                                "character": issue.get("character", ""),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[人物发展分析] LLM状态检测异常: {str(e)}")
                break

        return issues

    async def _analyze_relationships_with_llm(self, chapters_data: List[Dict], db, user_id: int) -> List[Dict]:
        """使用LLM深度检测人物关系发展逻辑"""
        issues = []

        if len(chapters_data) < 3:
            return issues

        batch_size = 15
        for batch_start in range(0, len(chapters_data), batch_size):
            batch_end = min(batch_start + batch_size, len(chapters_data))
            batch_chapters = chapters_data[batch_start:batch_end]

            batch_content = []
            for ch in batch_chapters:
                content = ch.get("content", "") or ch.get("summary", "")
                batch_content.append(
                    f"第{ch.get('chapter_number', 0)}单元：{content}"
                )

            try:
                from app.agents.llm_manager import get_llm_manager
                llm_manager = get_llm_manager()
                llm_provider = await llm_manager.get_provider_from_db(db, user_id)

                if not llm_provider:
                    logger.warning("[人物发展分析] 无法获取LLM提供者，跳过关系检测")
                    break

                prompt = f"""你是专业的人物关系审核专家。

请分析以下单元概述中人物关系发展的逻辑性，检测是否存在突然转变或不合理之处：

【单元概述批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【检测要求】
1. 人物关系转变是否合理？（如从敌人突然变成盟友且无铺垫）
2. 情感变化是否符合逻辑？（如从深爱突然变成仇恨）
3. 信任/背叛转变是否有充分动机？

【输出格式】
```json
{{
  "relationship_issues": [
    {{
      "unit_number": 单元号,
      "characters": ["人物A", "人物B"],
      "issue_type": "关系突变|情感矛盾|信任转变缺乏铺垫",
      "description": "详细描述问题",
      "severity": "warning|info"
    }}
  ]
}}
```

如果没有问题，返回空数组。
"""

                response = await llm_call_with_retry(llm_provider, prompt=prompt, temperature=0.2, context="单元质控分析")
                response_text = response.content if hasattr(
                    response, 'content') else str(response)

                import re
                import json
                json_match = re.search(
                    r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    result = json.loads(json_match.group(1))
                    for issue in result.get("relationship_issues", []):
                        issues.append({
                            "id": f"UR-LLM-{len(issues)+1}",
                            "dimension": "unit_character",
                            "category": issue.get("issue_type", "关系问题"),
                            "severity": issue.get("severity", "info"),
                            "location": {
                                "chapter_number": issue.get("unit_number", 0),
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                            },
                            "description": issue.get("description", ""),
                            "evidence": f"第{issue.get('unit_number', '?')}单元",
                            "suggestion": "建议增加人物关系转变的铺垫和动机描写",
                            "metadata": {
                                "unit_number": issue.get("unit_number"),
                                "characters": issue.get("characters", []),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[人物发展分析] LLM关系检测异常: {str(e)}")
                break

        return issues

    def _calculate_character_score(self, issues: List[Dict]) -> float:
        """计算人物发展得分"""
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
        """应用用户反馈学习的阈值调整"""
        try:
            from .feedback_learning import get_feedback_manager
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
            logger.warning(f"[人物发展分析] 应用反馈阈值失败: {str(e)}")
            return issues
