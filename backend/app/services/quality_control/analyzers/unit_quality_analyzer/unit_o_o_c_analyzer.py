"""单元概述质量分析器 - UnitOOCAnalyzer"""
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


class UnitOOCAnalyzer:
    """人物OOC分析器 - 使用LLM深度检测人物是否违背人设"""

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
        """执行人物OOC分析（全部使用LLM深度检测）"""
        issues = []

        # 1. LLM深度检测：人物行为OOC
        behavior_issues = await self._check_character_behavior_ooc(
            chapters_data, character_profiles, db, user_id
        )
        issues.extend(behavior_issues)

        # 2. LLM深度检测：人物关系OOC
        relation_issues = await self._check_character_relationship_ooc(
            chapters_data, character_profiles, db, user_id
        )
        issues.extend(relation_issues)

        # 计算得分
        score = self._calculate_ooc_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    async def _check_character_behavior_ooc(
        self,
        chapters_data: List[Dict],
        character_profiles: List[Dict],
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM深度检测人物行为是否违背人设"""
        issues = []

        if not chapters_data:
            return issues

        # 构建人物设定信息
        profile_info = ""
        if character_profiles:
            profile_parts = []
            for char in character_profiles:
                if isinstance(char, dict):
                    name = char.get("name", char.get("character_name", "未知"))
                    personality = char.get(
                        "personality", char.get("character_traits", ""))
                    background = char.get(
                        "background", char.get("backstory", ""))
                    motivation = char.get("motivation", char.get("goal", ""))
                    abilities = char.get("abilities", char.get("skills", ""))
                    profile_parts.append(
                        f"- {name}：性格({personality})，背景({background})，动机({motivation})，能力({abilities})"
                    )
            profile_info = "\n【人物设定】\n" + \
                "\n".join(profile_parts) if profile_parts else ""

        # 构建单元概述内容
        all_content = "\n".join([
            f"第{ch.get('chapter_number', 0)}单元：{(ch.get('content', '') or ch.get('summary', ''))}"
            for ch in chapters_data[:50]
        ])

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[人物OOC分析] 无法获取LLM提供者，跳过行为OOC检测")
                return issues

            prompt = f"""你是专业的人物设定审核专家，专门检测人物行为是否违背其人设（OOC，Out of Character）。

请分析以下单元概述中人物的行为是否符合其设定：

【单元概述列表】（共{len(chapters_data)}个单元）
{all_content}{profile_info}

【检测要求】
1. **性格违背**：如懦弱的角色突然变得勇敢且无合理铺垫
2. **动机矛盾**：如追求权力的角色突然放弃一切且无解释
3. **说话方式不符**：如文盲角色突然引用诗词
4. **能力超纲**：如不会武功的角色突然施展绝世武功
5. **转变缺乏铺垫**：人物性格转变但缺少触发事件

注意区分：
- 有合理铺垫的性格成长是允许的（如经历了重大事件后性格转变）
- OOC是指无铺垫、无解释的突然违背人设的行为

【输出格式】
```json
{{
  "ooc_issues": [
    {{
      "character": "人物名",
      "unit_number": 单元号,
      "issue_type": "性格违背|动机矛盾|说话方式不符|能力超纲|转变缺乏铺垫",
      "description": "详细描述OOC问题",
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
                for issue in result.get("ooc_issues", []):
                    issues.append({
                        "id": f"OOC-BEH-{len(issues)+1}",
                        "dimension": "unit_ooc",
                        "category": issue.get("issue_type", "人物OOC"),
                        "severity": issue.get("severity", "warning"),
                        "location": {
                            "chapter_number": issue.get("unit_number", 0),
                            "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                        },
                        "description": issue.get("description", ""),
                        "evidence": f"{issue.get('character', '?')} - 第{issue.get('unit_number', '?')}单元",
                        "suggestion": "请修正人物行为使其符合人设，或添加合理的转变铺垫",
                        "metadata": {
                            "character": issue.get("character", ""),
                            "unit_number": issue.get("unit_number"),
                            "analysis_method": "llm_deep"
                        }
                    })
        except Exception as e:
            logger.warning(f"[人物OOC分析] LLM行为OOC检测异常: {str(e)}")

        return issues

    async def _check_character_relationship_ooc(
        self,
        chapters_data: List[Dict],
        character_profiles: List[Dict],
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM深度检测人物关系处理是否违背人设"""
        issues = []

        if not chapters_data:
            return issues

        # 构建人物设定信息
        profile_info = ""
        if character_profiles:
            profile_parts = []
            for char in character_profiles:
                if isinstance(char, dict):
                    name = char.get("name", char.get("character_name", "未知"))
                    personality = char.get(
                        "personality", char.get("character_traits", ""))
                    profile_parts.append(f"- {name}：{personality}")
            profile_info = "\n【人物设定】\n" + \
                "\n".join(profile_parts) if profile_parts else ""

        # 构建单元概述内容
        all_content = "\n".join([
            f"第{ch.get('chapter_number', 0)}单元：{(ch.get('content', '') or ch.get('summary', ''))}"
            for ch in chapters_data[:50]
        ])

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[人物OOC分析] 无法获取LLM提供者，跳过关系OOC检测")
                return issues

            prompt = f"""你是专业的人物关系审核专家，专门检测人物对待他人的方式是否违背其人设。

请分析以下单元概述中人物的关系处理是否符合其性格设定：

【单元概述列表】（共{len(chapters_data)}个单元）
{all_content}{profile_info}

【检测要求】
1. **对待方式不符**：如温柔的角色突然对亲近的人残暴且无解释
2. **忠诚度矛盾**：如忠诚的角色无故背叛
3. **情感表达不符**：如冷摸的角色突然过度表达情感且无铺垫
4. **社交方式矛盾**：如独来独往的角色突然变得极虚社交且无原因

注意区分合理的情感成长与OOC：
- 经历重大事件后的合理转变是允许的
- OOC是无铺垫、无解释的突然违背人设的社交行为

【输出格式】
```json
{{
  "relation_ooc_issues": [
    {{
      "character": "人物名",
      "target": "对方人物名",
      "unit_number": 单元号,
      "issue_type": "对待方式不符|忠诚度矛盾|情感表达不符|社交方式矛盾",
      "description": "详细描述关系OOC问题",
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
                for issue in result.get("relation_ooc_issues", []):
                    issues.append({
                        "id": f"OOC-REL-{len(issues)+1}",
                        "dimension": "unit_ooc",
                        "category": issue.get("issue_type", "关系OOC"),
                        "severity": issue.get("severity", "info"),
                        "location": {
                            "chapter_number": issue.get("unit_number", 0),
                            "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                        },
                        "description": issue.get("description", ""),
                        "evidence": f"{issue.get('character', '?')} → {issue.get('target', '?')}：第{issue.get('unit_number', '?')}单元",
                        "suggestion": "请修正人物关系处理使其符合人设，或添加合理的转变铺垫",
                        "metadata": {
                            "character": issue.get("character", ""),
                            "target": issue.get("target", ""),
                            "unit_number": issue.get("unit_number"),
                            "analysis_method": "llm_deep"
                        }
                    })
        except Exception as e:
            logger.warning(f"[人物OOC分析] LLM关系OOC检测异常: {str(e)}")

        return issues

    def _calculate_ooc_score(self, issues: List[Dict]) -> float:
        """计算OOC得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 15
            elif severity == "warning":
                score -= 8
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))
