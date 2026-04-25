"""大纲生成器 - 手动模式单元概述质控与修正Mixin"""
from typing import Dict
from typing import Any
from datetime import datetime
import json
import re


class QcUnitManualMixin:
    """手动模式单元概述质控与修正"""

    async def analyze_unit_summaries_quality_manual(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        global_outline: str,
        content_type: str,
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        手动触发单元概述质量检测（使用LLM，参照全局大纲流程）

        Args:
            unit_summaries: 已解析的单元概述字典
            global_outline: 全局大纲
            content_type: 内容类型
            user_id: 用户ID

        Returns:
            质量检测报告
        """
        self.logger.info(f"[单元概述质控] 开始LLM质量检测，单元数: {len(unit_summaries)}")

        try:
            # 1. 构建完整的单元概述文本
            unit_label = "章" if content_type == "novel" else "集"
            full_content_parts = []

            for unit_num, unit_data in sorted(unit_summaries.items(), key=lambda x: int(x[0])):
                title = unit_data.get("title", "")
                full_content = unit_data.get(
                    "full_content", "") or unit_data.get("summary", "")
                full_content_parts.append(
                    f"### 第{unit_num}{unit_label}：{title}\n{full_content}")

            complete_outline = "\n\n".join(full_content_parts)

            # 2. 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(self.db, user_id, None)
            if not llm_provider:
                raise ValueError("未找到LLM提供商，请检查API KEY配置")

            # 3. 构建LLM检测提示词
            analysis_prompt = f"""你是资深的小说/剧本质控专家，拥有10年以上的编辑经验。你的任务是**严格、全面**地检测单元概述的质量问题。

## 全局大纲（故事的整体规划）
{global_outline if global_outline else "未提供"}

## 单元概述（待检测的具体内容）
{complete_outline}

---

## 🔍 检测任务：逐单元深度审查

你必须**按顺序逐个检查每个单元**，从以下四个维度进行深度分析：

### 📐 维度1：结构检测（structure）

**1.1 单元长度合理性**
- 检查每个单元的篇幅是否合理（过短<100字或过长>800字都要指出）
- 对比各单元长度，是否存在明显不平衡

**1.2 单元衔接流畅度**
- 检查前一个单元的结尾与后一个单元的开头是否自然衔接
- 是否存在情节跳跃、时间断层、场景突兀转换
- 是否有必要的过渡内容

**1.3 情节节奏控制**
- 检查情节发展是否有起伏（不能所有单元都是平淡叙述）
- 是否有高潮、转折、缓冲的节奏变化
- 连续多个单元是否都是同一类型的情节（如全是打斗或全是对话）

**1.4 核心事件明确性**
- 每个单元是否有一个清晰的核心事件或主要冲突
- 单元内容是否围绕核心事件展开，有无跑题

### 👥 维度2：人物检测（character）

**2.1 人物状态连续性**
- 检查人物在单元之间的状态变化是否合理（如：受伤→恢复需要时间）
- 是否存在人物状态突变（如：前一单元重伤，下一单元完好无损）
- 人物情绪变化是否有铺垫

**2.2 人物关系一致性**
- 检查人物关系是否前后矛盾（如：前文是敌人，后文突然变成朋友且无解释）
- 人物称呼、身份、职位是否一致
- 人物性格是否保持连贯（OOC检测）

**2.3 人物成长逻辑**
- 人物的能力成长、心理变化是否有合理的过程
- 是否存在人物突然掌握某项技能而无学习过程
- 重要人物的成长线索是否完整

**2.4 人物遗漏检查**
- 全局大纲中的重要人物是否在单元概述中被遗漏
- 是否有单元缺少必要的人物出场

### 🎯 维度3：一致性检测（consistency）

**3.1 情节走向一致性**
- 对比单元概述与全局大纲，检查情节走向是否一致
- 单元概述是否偏离了全局大纲设定的故事线
- 是否有全局大纲中没有的突兀情节

**3.2 核心要素完整性**
- 全局大纲中的关键情节点、转折点是否在单元概述中得到体现
- 是否有遗漏全局大纲中明确要求的重要事件
- 核心线索（如：寻找某物、解开某谜团）是否在单元中延续

**3.3 世界观设定一致性**
- 检查单元概述中的世界观设定是否与全局大纲冲突
- 力量体系、规则设定、地理环境是否前后一致
- 是否存在违背已建立设定的内容

**3.4 时间线一致性**
- 检查时间线是否合理（如：季节变化、时间跨度）
- 是否存在时间倒流或时间矛盾
- 事件发生的先后顺序是否合理

### ✍️ 维度4：质量检测（quality）

**4.1 情节要点清晰度**
- 每个单元的情节要点是否清晰明确
- 是否包含必要的"情节要点"部分
- 情节要点是否具体而非模糊笼统

**4.2 人物状态标注完整性**
- 是否包含"人物状态标注"部分
- 人物状态标注是否详细（包含情绪、伤势、能力变化等）
- 状态标注是否与单元内容匹配

**4.3 逻辑漏洞检测**
- 检查是否存在明显的逻辑错误（如：人物同时出现在两个地方）
- 因果关系是否合理（如：A导致B，但A和B之间没有必然联系）
- 是否存在违背常识的内容

**4.4 标题准确性**
- 单元标题是否准确概括了该单元的核心内容
- 标题是否与单元内容匹配
- 标题是否具有吸引力且不过度夸张

---

## ⚠️ 检测标准与要求

### 强制性要求
1. **必须逐单元检查**：不能跳过任何一个单元，必须对每个单元进行四个维度的检测
2. **发现问题必须报告**：即使是不确定是否算问题的地方，也要列为minor级别
3. **提供具体证据**：每个问题必须引用原文内容作为证据（evidence字段）
4. **给出修正建议**：每个问题必须提供具体可操作的修正建议

### severity分级标准（严格执行）
- **critical（严重）**：
  - 情节严重偏离全局大纲
  - 人物状态突变且无解释
  - 明显的逻辑矛盾或违背常识
  - 遗漏全局大纲中的关键情节
  - 人物关系严重矛盾
  
- **major（重要）**：
  - 单元衔接不流畅
  - 人物成长缺乏铺垫
  - 情节节奏失衡
  - 世界观设定轻微冲突
  - 核心要素部分缺失

- **minor（次要）**：
  - 单元长度略有不平衡
  - 标题不够吸引人
  - 情节要点表述不够清晰
  - 人物状态标注不够详细
  - 可以优化的细节

### 评分标准
- **90-100分**：几乎没有问题，质量极高
- **80-89分**：有少量minor问题，整体优秀
- **70-79分**：有一些major问题，需要改进
- **60-69分**：有critical问题，必须修正
- **60分以下**：存在严重质量问题，需要大幅修改

---

## 📋 输出格式（必须严格遵守）

请严格按照以下JSON格式输出检测结果：

```json
{{
  "overall_score": 75,
  "dimension_scores": {{
    "structure": 80,
    "character": 70,
    "consistency": 75,
    "quality": 75
  }},
  "issues": [
    {{
      "id": "ISSUE-001",
      "dimension": "structure",
      "category": "衔接问题",
      "severity": "critical",
      "unit_number": 1,
      "location": {{
        "chapter_number": 1,
        "unit_id": "unit-1"
      }},
      "description": "第1单元与第2单元之间衔接不流畅，存在情节跳跃",
      "evidence": "第1单元结尾：'他倒在地上，身受重伤'；第2单元开头：'他精神抖擞地走进大厅'",
      "suggestion": "在第1单元结尾或第2单元开头增加过渡内容，说明他是如何恢复的"
    }},
    {{
      "id": "ISSUE-002",
      "dimension": "character",
      "category": "人物状态突变",
      "severity": "critical",
      "unit_number": 3,
      "location": {{
        "chapter_number": 3,
        "unit_id": "unit-3"
      }},
      "description": "主角在第2单元中左手骨折，但第3单元中左手正常使用且无任何说明",
      "evidence": "第2单元人物状态标注：'左手骨折，无法使用武器'；第3单元情节：'他左手持剑，与敌人战斗'",
      "suggestion": "在第3单元中说明主角左手是否已经恢复，或者改为右手战斗"
    }}
  ]
}}
```

### 输出要求
1. **overall_score**：根据上述评分标准给出总体得分（0-100的整数）
2. **dimension_scores**：四个维度的独立得分（0-100的整数）
3. **issues**：必须列出**所有发现的问题**，按严重程度排序（critical在前）
4. 每个issue必须包含所有必填字段：id, dimension, category, severity, unit_number, location, description, evidence, suggestion
5. **evidence字段必须引用原文内容**，不能只说"存在某某问题"
6. 如果没有问题，issues返回空数组 []

---

## 💡 检测提示

在检测时，请特别注意以下常见但容易被忽视的问题：
1. **时间跳跃**：单元之间的时间跨度是否合理
2. **场景转换**：场景切换是否突兀
3. **人物消失/出现**：重要人物是否无故消失或突然出现
4. **能力变化**：人物能力是否有合理的成长或衰退过程
5. **情感逻辑**：人物的情感变化是否有铺垫
6. **因果链条**：事件之间的因果关系是否成立
7. **伏笔回收**：前面埋下的伏笔是否在后续单元中得到回应
8. **设定冲突**：是否违背已建立的世界观、规则体系

**记住：你的职责是找出所有问题，宁可错报也不要漏报！**
"""

            self.logger.info("[单元概述质控] 调用LLM进行质量分析...")
            self.logger.info(
                f"[单元概述质控] 全局大纲长度: {len(global_outline) if global_outline else 0} 字")
            self.logger.info(f"[单元概述质控] 单元概述总长度: {len(complete_outline)} 字")
            self.logger.info(f"[单元概述质控] 单元数量: {len(unit_summaries)}")

            response = await llm_provider.generate(prompt=analysis_prompt, temperature=0.3, timeout=1200)
            response_text = response.content if hasattr(
                response, 'content') else str(response)

            self.logger.info(f"[单元概述质控] LLM响应长度: {len(response_text)} 字")

            # 4. 解析LLM返回的JSON
            import json
            import re

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                raise ValueError(f"LLM返回格式错误，未找到JSON: {response_text[:200]}")

            quality_report = json.loads(json_match.group(0))

            # 5. 确保报告格式完整
            if "overall_score" not in quality_report:
                quality_report["overall_score"] = 50
            if "dimension_scores" not in quality_report:
                quality_report["dimension_scores"] = {}
            if "issues" not in quality_report:
                quality_report["issues"] = []

            # 6. 为每个issue添加必要字段
            for i, issue in enumerate(quality_report.get("issues", []), 1):
                if "id" not in issue:
                    issue["id"] = f"ISSUE-{i:03d}"
                if "location" not in issue:
                    unit_num = issue.get("unit_number", "")
                    issue["location"] = {
                        "chapter_number": unit_num,
                        "unit_id": f"unit-{unit_num}" if unit_num else ""
                    }

            # 详细日志输出
            issues = quality_report.get("issues", [])
            critical_count = sum(
                1 for i in issues if i.get("severity") == "critical")
            major_count = sum(
                1 for i in issues if i.get("severity") == "major")
            minor_count = sum(
                1 for i in issues if i.get("severity") == "minor")

            self.logger.info(f"[单元概述质控] LLM检测完成")
            self.logger.info(
                f"[单元概述质控] 总分: {quality_report.get('overall_score', 0)}")
            self.logger.info(
                f"[单元概述质控] 维度得分: {quality_report.get('dimension_scores', {})}")
            self.logger.info(
                f"[单元概述质控] 问题统计: 总计{len(issues)}个 (critical: {critical_count}, major: {major_count}, minor: {minor_count})")

            # 输出前5个问题的摘要
            for issue in issues[:5]:
                self.logger.info(
                    f"[单元概述质控] 问题示例: [{issue.get('severity')}] {issue.get('description', '')[:100]}")

            return quality_report

        except Exception as e:
            self.logger.error(f"[单元概述质控] LLM检测失败: {e!r}", exc_info=True)
            # 返回空报告
            return {
                "overall_score": 0,
                "dimension_scores": {},
                "issues": [],
                "error": str(e)
            }


    async def revise_unit_summaries_quality(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        quality_report: Dict[str, Any],
        global_outline: str,
        content_type: str,
        temperature: float = 0.7,
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        对单元概述执行质量修正

        Args:
            unit_summaries: 已解析的单元概述字典
            quality_report: 质量检测报告
            global_outline: 全局大纲
            content_type: 内容类型
            temperature: 温度参数
            user_id: 用户ID

        Returns:
            修正结果
        """
        # 获取LLM提供商
        llm_provider = await self.llm_manager.get_provider_from_db(
            self.db, user_id, None
        )
        if not llm_provider:
            raise ValueError("未找到LLM提供商")

        # 构建修正提示词
        revision_prompt = self._build_quality_revision_prompt(
            unit_summaries=unit_summaries,
            quality_report_dict=quality_report,
            global_outline=global_outline,
            content_type=content_type
        )

        # 调用LLM修正
        revision_response = await llm_provider.generate(
            prompt=revision_prompt,
            temperature=temperature
        )

        # 解析修正结果
        revised_parsed = self._parse_quality_revision_result(
            revision_response.content, unit_summaries
        )

        if not revised_parsed:
            self.logger.warning("[质量修正] 修正结果解析失败")
            return {
                "revised_content": None,
                "revised_parsed": None
            }

        # 合并修正数据与原始数据，保留所有原始字段
        merged_parsed = {}
        revised_units = []  # v2.4新增: 记录实际被修正的单元

        for unit_num, original_data in unit_summaries.items():
            if unit_num in revised_parsed:
                # 该单元被修正，合并数据
                revised_data = revised_parsed[unit_num]
                merged_data = {
                    **original_data,  # 保留所有原始字段
                    "summary": revised_data.get("summary", original_data.get("summary", "")),
                    "full_content": revised_data.get("full_content", original_data.get("full_content", "")),
                    "revision_reason": revised_data.get("revision_reason", ""),
                    "revised_at": datetime.now().isoformat()  # 添加修正时间标记
                }
                # 保留title（如果修正结果中有）
                if "title" in revised_data:
                    merged_data["title"] = revised_data["title"]

                merged_parsed[unit_num] = merged_data
                revised_units.append(unit_num)  # v2.4新增: 记录被修正的单元
                self.logger.info(f"[质量修正] 第{unit_num}单元已修正并合并数据")
            else:
                # 该单元未被修正，保留原始数据
                merged_parsed[unit_num] = original_data

        # v2.4修复: 只构建被修正单元的内容，而不是整个文档
        # 这样diff高亮才能精确显示修改内容
        if len(revised_units) == 1:
            # 只修正了1个单元，只返回该单元的内容
            unit_num = revised_units[0]
            unit_data = merged_parsed[unit_num]
            unit_label = "章" if content_type == "novel" else "集"
            title = unit_data.get("title", "")
            content_to_use = unit_data.get(
                "full_content", "") or unit_data.get("summary", "")

            # 移除重复标题
            import re
            title_patterns = [
                rf"^###\s*第{unit_num}{unit_label}[:：]\s*.*$",
                rf"^\*\*第{unit_num}{unit_label}\*\*[:：]\s*.*$",
                rf"^#{1, 3}\s*.*{unit_num}.*{unit_label}.*$",
            ]

            content_lines = content_to_use.split('\n')
            cleaned_lines = [line for line in content_lines if not any(
                re.match(pattern, line.strip(), re.IGNORECASE) for pattern in title_patterns
            )]
            content_to_use = '\n'.join(cleaned_lines)

            revised_content = f"### 第{unit_num}{unit_label}：{title}\n{content_to_use}"
            self.logger.info(
                f"[质量修正] 只返回第{unit_num}单元的修正内容(长度:{len(revised_content)})")
        else:
            # 修正了多个单元，返回完整内容
            revised_content = self._build_revised_content(
                merged_parsed, content_type)
            self.logger.info(f"[质量修正] 返回完整修正内容(长度:{len(revised_content)})")

        # 构建变更说明（参照全局大纲的流程）
        # 修复1：修正所有级别的问题（critical + major + minor），不仅限于critical
        all_issues = quality_report.get("issues", [])
        changes = []

        for issue in all_issues:
            changes.append({
                "issue_id": issue.get("id"),
                "category": issue.get("category"),
                "description": issue.get("description"),
                "suggestion": issue.get("suggestion"),
                "severity": issue.get("severity"),  # 添加severity字段
                "unit_number": issue.get("location", {}).get("chapter_number") or issue.get("unit_number")
            })

        return {
            "revised_content": revised_content,
            "revised_parsed": merged_parsed,
            "changes": changes
        }


