"""单元概述质量分析器 - TimelineConsistencyAnalyzer"""
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


class TimelineConsistencyAnalyzer:
    """时间线一致性检测器 - 检测故事情节的时间线是否连贯，事件发生的先后顺序是否合理"""

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
        worldview_settings: Dict = None,
        **kwargs
    ) -> Dict:
        """执行时间线一致性分析"""
        issues = []

        # 构建完整时间线记录（最多前30章）
        timeline_records = []
        for ch in chapters_data[:30]:
            content = ch.get("content", "") or ch.get("summary", "")
            timeline_records.append(
                f"第{ch.get('chapter_number', 0)}单元：{content}"
            )

        # 提取全局大纲中的时间线信息
        outline_timeline = global_outline[:
                                          2000] if global_outline else "无全局大纲时间线"

        # 分批检测（每批10章）
        batch_size = 10
        for batch_start in range(0, len(chapters_data), batch_size):
            batch_end = min(batch_start + batch_size, len(chapters_data))
            batch_chapters = chapters_data[batch_start:batch_end]

            # 构建批次内容
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
                    logger.warning("[时间线一致性检测] 无法获取LLM提供者，跳过批次检测")
                    break

                timeline_text = "\n".join(timeline_records)

                prompt = f"""你是专业的时间线一致性审核专家。

请检测以下单元内容的时间线是否连贯，事件发生的先后顺序是否合理：

【当前单元批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【完整时间线记录】（前30章）
{timeline_text}

【全局大纲时间线】
{outline_timeline}

【检测要求】
1. 时间顺序：事件发生的先后顺序是否合理？是否有时间倒流？
2. 时间跨度：两个事件之间的时间间隔是否合理？
3. 季节/天气：季节变化、天气描述是否连贯？
4. 年龄/成长：人物年龄增长、技能提升的时间是否合理？
5. 事件持续时间：长期事件（战争、旅行、修炼）的时间跨度是否一致？
6. 时间标记：明确的时间标记（如"三天后"、"次年春天"）是否前后矛盾？
7. 并行事件：同时发生的不同事件线是否有时间冲突？
8. 历史事件：回忆、flashback中的时间线是否与主线一致？

【输出格式】
```json
{{
  "timeline_issues": [
    {{
      "issue_type": "时间顺序|时间跨度|季节天气|年龄成长|事件持续|时间标记|并行事件|历史事件",
      "chapter_number": 单元号,
      "time_reference": "时间引用",
      "conflict_description": "冲突描述",
      "previous_timeline": "之前的时间线",
      "current_timeline": "当前的时间线",
      "severity": "critical|warning|info",
      "suggestion": "修正建议"
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
                    for issue in result.get("timeline_issues", []):
                        issues.append({
                            "id": f"TL-{len(issues)+1}",
                            "dimension": "timeline_consistency",
                            "category": issue.get("issue_type", "时间线矛盾"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": issue.get("chapter_number", batch_end),
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("chapter_number", batch_end))
                            },
                            "description": issue.get("conflict_description", ""),
                            "evidence": f"{issue.get('time_reference', '?')}：{issue.get('previous_timeline', '?')} → {issue.get('current_timeline', '?')}",
                            "suggestion": issue.get("suggestion", "建议修正时间线使其保持连贯"),
                            "metadata": {
                                "issue_type": issue.get("issue_type"),
                                "time_reference": issue.get("time_reference"),
                                "previous_timeline": issue.get("previous_timeline"),
                                "current_timeline": issue.get("current_timeline"),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[时间线一致性检测] 批次{batch_start}检测异常: {str(e)}")
                continue

        # 计算得分
        score = self._calculate_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    def _calculate_score(self, issues: List[Dict]) -> float:
        """计算时间线一致性得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 18
            elif severity == "warning":
                score -= 9
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))
