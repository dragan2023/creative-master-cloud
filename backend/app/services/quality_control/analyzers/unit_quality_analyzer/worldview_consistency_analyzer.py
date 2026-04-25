"""单元概述质量分析器 - WorldviewConsistencyAnalyzer"""
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


class WorldviewConsistencyAnalyzer:
    """世界观一致性检测器 - 检测正文内容与设定的世界观、规则、背景等是否保持一致"""

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
        """执行世界观一致性分析"""
        issues = []

        if not worldview_settings:
            worldview_settings = {}

        # 分批检测（每批8章）
        batch_size = 8
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
                    logger.warning("[世界观一致性检测] 无法获取LLM提供者，跳过批次检测")
                    break

                # 格式化世界观设定
                worldview_text = ""
                if isinstance(worldview_settings, dict):
                    for key, value in worldview_settings.items():
                        if isinstance(value, str):
                            worldview_text += f"- {key}: {value}\n"
                        elif isinstance(value, (list, dict)):
                            worldview_text += f"- {key}: {json.dumps(value, ensure_ascii=False, indent=2)}\n"
                elif isinstance(worldview_settings, str):
                    worldview_text = worldview_settings

                if not worldview_text:
                    worldview_text = "无详细世界观设定"

                prompt = f"""你是专业的世界观一致性审核专家。

请检测以下单元内容是否与设定的世界观、规则、背景保持一致：

【当前单元批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【世界观设定】
{worldview_text}

【检测要求】
1. 物理法则：是否符合世界观中的物理规则？（如魔法系统、科技水平）
2. 社会制度：是否符合设定的社会结构、阶级、法律？
3. 文化习俗：是否符合设定的文化传统、礼仪、禁忌？
4. 经济体系：货币、交易、资源分配是否合理？
5. 力量体系：修炼等级、能力限制、代价是否一致？
6. 历史背景：是否与既定的历史事件、时间线冲突？
7. 地理环境：地形、气候、距离是否合理？
8. 生物设定：种族特性、寿命、能力是否符合设定？

【输出格式】
```json
{{
  "consistency_issues": [
    {{
      "rule_category": "物理法则|社会制度|文化习俗|经济体系|力量体系|历史背景|地理环境|生物设定",
      "rule_description": "违反的规则描述",
      "text_evidence": "原文引用",
      "conflict_description": "冲突说明",
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
                    for issue in result.get("consistency_issues", []):
                        issues.append({
                            "id": f"WV-{len(issues)+1}",
                            "dimension": "worldview_consistency",
                            "category": issue.get("rule_category", "世界观冲突"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": batch_end,
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, batch_end)
                            },
                            "description": issue.get("conflict_description", ""),
                            "evidence": issue.get("text_evidence", ""),
                            "suggestion": issue.get("suggestion", "建议修正内容使其符合世界观设定"),
                            "metadata": {
                                "rule_category": issue.get("rule_category"),
                                "rule_description": issue.get("rule_description"),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[世界观一致性检测] 批次{batch_start}检测异常: {str(e)}")
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
        """计算世界观一致性得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 20
            elif severity == "warning":
                score -= 10
            elif severity == "info":
                score -= 4

        return max(0, min(100, score))
