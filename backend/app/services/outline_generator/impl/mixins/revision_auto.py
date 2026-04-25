"""大纲生成器 - 自动质控修正与质量修正辅助Mixin"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
from datetime import datetime
import json
import re


class RevisionAutoMixin:
    """自动质控修正与质量修正辅助"""

    async def _auto_qc_and_revise(
        self,
        content: str,
        user_id: int,
        llm_provider=None,
        dimensions: List[str] = None,
        depth: str = "standard"  # 自动质控默认使用standard模式以确保LLM深度分析
    ) -> Dict[str, Any]:
        """
        自动执行质控分析并修正（v2.3新增）

        整合质控分析和修正逻辑，一步完成检测和修正。

        Args:
            content: 待检测和修正的内容
            user_id: 用户ID
            llm_provider: LLM提供者实例
            dimensions: 分析维度（默认四维度）
            depth: 分析深度（默认quick以提升速度）

        Returns:
            {
                "success": bool,
                "revised_content": str or None,
                "issues_fixed": int,
                "qc_report": dict
            }
        """
        result = {
            "success": False,
            "revised_content": None,
            "issues_fixed": 0,
            "qc_report": None
        }

        if not content or len(content.strip()) < 100:
            self.logger.warning("[自动质控] 内容过短，跳过质控")
            return result

        if dimensions is None:
            dimensions = [
                "global_structure",
                "global_character_worldview",
                "global_plot_consistency",
                "global_storyline_integrity"
            ]

        try:
            self.logger.info(f"[自动质控] 开始分析，维度: {dimensions}, 深度: {depth}")

            # 1. 执行质控分析
            qc_report = await self.analyze_global_outline_quality(
                global_outline_content=content,
                project=None,  # 两阶段模式无项目
                user_id=user_id,
                dimensions=dimensions,
                depth=depth
            )

            if not qc_report.get("success", False):
                self.logger.warning("[自动质控] 质控分析失败")
                result["qc_report"] = qc_report
                return result

            issues = qc_report.get("issues", [])
            overall_score = qc_report.get("overall_score", 0)

            self.logger.info(
                f"[自动质控] 分析完成，得分: {overall_score}, 问题数: {len(issues)}"
            )

            # 2. 判断是否需要修正
            if not issues or len(issues) == 0:
                self.logger.info("[自动质控] 未发现问题，无需修正")
                result["success"] = True
                result["qc_report"] = qc_report
                return result

            # 3. 筛选需要修正的问题（所有问题）
            issues_to_fix = [issue.get("id")
                             for issue in issues if issue.get("id")]

            if not issues_to_fix:
                self.logger.info("[自动质控] 无有效问题ID，跳过修正")
                result["success"] = True
                result["qc_report"] = qc_report
                return result

            self.logger.info(f"[自动质控] 开始修正 {len(issues_to_fix)} 个问题")

            # 4. 执行修正
            revision_result = await self.revise_global_outline_by_quality(
                original_outline=content,
                quality_report=qc_report,
                issues_to_fix=issues_to_fix,
                project=None,
                user_id=user_id
            )

            if revision_result.get("success"):
                revised_content = revision_result.get("revised_content")
                result["success"] = True
                result["revised_content"] = revised_content

                # v2.4.1: 只有修正真正生效时才统计issues_fixed
                revision_effective = revision_result.get(
                    "revision_effective", False)
                if revision_effective:
                    result["issues_fixed"] = len(issues_to_fix)
                else:
                    result["issues_fixed"] = 0
                    result["revision_skipped"] = True
                    result["skip_reason"] = revision_result.get(
                        "skip_reason", "修正未生效")

                # 更新质控报告中的修正标记
                qc_report["auto_applied"] = revision_effective
                qc_report["applied_at"] = datetime.now().isoformat()
                qc_report["issues_fixed"] = result["issues_fixed"]
                result["qc_report"] = qc_report

                self.logger.info(
                    f"[自动质控] 修正完成，原始长度: {len(content)}, "
                    f"修正后长度: {len(revised_content)}"
                )
            else:
                self.logger.warning(
                    f"[自动质控] 修正失败: {revision_result.get('error')}")
                result["qc_report"] = qc_report

        except Exception as e:
            self.logger.error(f"[自动质控] 执行失败: {e!r}")
            result["error"] = str(e)

        return result


    def _build_quality_revision_prompt(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        quality_report_dict: Dict[str, Any],
        global_outline: str,
        content_type: str
    ) -> str:
        """
        构建基于质量报告的修正提示词

        Args:
            unit_summaries: 单元概述字典
            quality_report_dict: 质量报告字典
            global_outline: 全局大纲内容
            content_type: 内容类型

        Returns:
            修正提示词字符串
        """
        # 提取所有问题（不仅限于critical，包含major和minor）
        # 修复1：确保所有级别的问题都被修正
        issues = quality_report_dict.get("issues", [])

        # v2.4新增：记录是否只修正指定问题（直接修正模式）
        is_targeted_revision = len(
            issues) == 1 and "issue_id" in quality_report_dict

        # 按严重程度排序：critical > major > minor
        severity_order = {"critical": 0, "major": 1, "minor": 2}
        sorted_issues = sorted(
            issues,
            key=lambda x: severity_order.get(x.get("severity", "minor"), 2)
        )

        # 构建问题描述
        issues_description = []
        for i, issue in enumerate(sorted_issues, 1):
            severity = issue.get('severity', 'minor')
            issue_text = f"{i}. [{severity.upper()}] [{issue.get('dimension', '')}] {issue.get('description', '')}"
            location = issue.get('location', {})
            if location:
                chapter = location.get('chapter', '')
                if chapter:
                    issue_text += f" (第{chapter}单元)"
            evidence = issue.get('evidence', '')
            if evidence:
                issue_text += f"\n   原文证据: {evidence[:100]}"
            suggestion = issue.get('suggestion', '')
            if suggestion:
                issue_text += f"\n   修改建议: {suggestion}"
            issues_description.append(issue_text)

        # 构建单元概述文本（包含完整结构化信息）
        units_text = []
        for unit_num, unit_data in sorted(unit_summaries.items(), key=lambda x: int(x[0])):
            unit_label = "章" if content_type == "novel" else "集"
            unit_parts = [
                f"【第{unit_num}{unit_label}】{unit_data.get('title', '')}"]

            # 添加梗概
            summary = unit_data.get('summary', '')
            if summary:
                unit_parts.append(f"梗概：{summary}")

            # 添加完整内容（包含情节要点、人物状态标注等所有结构化信息）
            full_content = unit_data.get('full_content', '')
            if full_content:
                unit_parts.append(f"完整内容：\n{full_content}")

            units_text.append('\n'.join(unit_parts))

        # v2.4新增: 构建修正要求的额外指令
        if is_targeted_revision:
            targeted_instructions = """### 【重要】直接修正模式 - 只修正指定问题
1. **只修正上述标注的这1个问题**，不要修改其他内容
2. **只修改与该问题直接相关的单元**，不要修改其他单元
3. 保持其他单元和内容的原样，不要做额外修改
4. 如果问题只涉及第X单元，就只修正第X单元，其他单元不要出现在输出中

### 通用要求
"""
            issue_reference = "该问题"
            precision_instruction = "精准修正该问题，不要过度修改"
        else:
            targeted_instructions = ""
            issue_reference = "每个严重问题"
            precision_instruction = "修正后内容应该解决所有标注的质量问题"

        prompt = f"""你是专业的创意写作顾问和剧本/小说结构专家。

## 任务
{'以下单元概述存在质量问题，请针对【指定问题】进行精准修正。' if is_targeted_revision else '以下单元概述存在严重的质量问题，请基于质量分析报告进行修正。'}

## 全局大纲（参考）
{global_outline[:2000]}

## 当前单元概述
{chr(10).join(units_text)}

## 发现的质量问题
{chr(10).join(issues_description)}

## 修正要求
{targeted_instructions}1. 针对{issue_reference}，修正对应的单元概述内容
2. **重要：必须保留原有的"情节要点"、"人物状态标注"等所有结构化信息**
3. 在修正梗概时，要考虑并整合这些结构化信息
4. 保持与全局大纲的一致性
5. 确保单元之间的逻辑连贯性
6. {precision_instruction}
7. 保持原有的创意和风格
8. 如果修正了梗概，确保与情节要点和人物状态标注保持一致

## 输出格式
请严格按照以下 JSON 格式输出修正结果：
```json
{{
  "revisions": {{
    "1": {{
      "summary": "修正后的第1单元梗概内容",
      "full_content": "修正后的第1单元完整内容（必须包含情节要点、人物状态标注等所有结构化信息）",
      "revision_reason": "修正原因说明"
    }},
    "2": {{
      "summary": "修正后的第2单元梗概内容",
      "full_content": "修正后的第2单元完整内容（必须包含情节要点、人物状态标注等所有结构化信息）",
      "revision_reason": "修正原因说明"
    }}
  }}
}}
```

注意：
- 只输出需要修正的单元
- summary 字段是修正后的梗概
- **full_content 字段必须包含完整的单元内容，包括情节要点、人物状态标注等所有结构化信息**
- 如果某个结构化信息不需要修改，请原样保留
- revision_reason 简要说明修正了什么问题
- 确保 JSON 格式正确，可以被解析
"""
        return prompt


    def _parse_quality_revision_result(
        self,
        revision_text: str,
        original_parsed: Dict[str, Dict[str, Any]]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        解析质量修正结果

        Args:
            revision_text: LLM 返回的修正文本
            original_parsed: 原始解析结果

        Returns:
            修正后的单元概述字典，解析失败返回 None
        """
        import json
        import re

        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', revision_text)
            if not json_match:
                self.logger.warning("[质量修正] 未找到 JSON 格式的输出")
                return None

            json_str = json_match.group(0)
            revision_data = json.loads(json_str)

            # 验证格式
            if "revisions" not in revision_data:
                self.logger.warning("[质量修正] JSON 格式错误，缺少 revisions 字段")
                return None

            revisions = revision_data["revisions"]
            if not isinstance(revisions, dict):
                self.logger.warning("[质量修正] revisions 字段格式错误")
                return None

            # 构建修正结果
            result = {}
            for unit_num, revision_info in revisions.items():
                if not isinstance(revision_info, dict):
                    continue

                summary = revision_info.get("summary", "").strip()
                full_content = revision_info.get("full_content", "").strip()
                revision_reason = revision_info.get(
                    "revision_reason", "").strip()

                if not summary:
                    continue

                result[unit_num] = {
                    "summary": summary,
                    # 如果没有full_content，使用summary
                    "full_content": full_content if full_content else summary,
                    "revision_reason": revision_reason
                }

            if result:
                self.logger.info(f"[质量修正] 成功解析 {len(result)} 个单元的修正结果")
                return result
            else:
                self.logger.warning("[质量修正] 未找到有效的修正内容")
                return None

        except json.JSONDecodeError as e:
            self.logger.error(f"[质量修正] JSON 解析失败: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"[质量修正] 解析修正结果失败: {str(e)}")
            return None


    def _build_revised_content(
        self,
        revised_parsed: Dict[str, Dict[str, Any]],
        content_type: str
    ) -> str:
        """
        根据修正后的解析结果构建完整内容

        Args:
            revised_parsed: 修正后的单元概述字典
            content_type: 内容类型

        Returns:
            完整的单元概述文本
        """
        unit_label = "章" if content_type == "novel" else "集"
        lines = []

        for unit_num in sorted(revised_parsed.keys(), key=int):
            unit_data = revised_parsed[unit_num]
            title = unit_data.get("title", "")
            summary = unit_data.get("summary", "")
            full_content = unit_data.get("full_content", "")

            # 优先使用full_content（包含情节要点、人物状态标注等完整结构化信息）
            # 如果没有full_content，则使用summary
            content_to_use = full_content if full_content else summary

            # 修复2：去除full_content中可能已有的标题行，避免重复
            # 检测并移除开头的标题行（如：### 第X章：XXX 或 **第X集**：XXX）
            import re
            title_patterns = [
                rf"^###\s*第{unit_num}{unit_label}[:：]\s*.*$",  # ### 第X章：标题
                rf"^\*\*第{unit_num}{unit_label}\*\*[:：]\s*.*$",  # **第X集**：标题
                # # 第X章 等各种Markdown标题
                rf"^#{1, 3}\s*.*{unit_num}.*{unit_label}.*$",
            ]

            content_lines = content_to_use.split('\n')
            cleaned_lines = []
            title_removed = False

            for line in content_lines:
                line_stripped = line.strip()
                # 检查是否匹配标题模式
                is_title = False
                for pattern in title_patterns:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        is_title = True
                        title_removed = True
                        break

                # 如果不是标题行，保留
                if not is_title:
                    cleaned_lines.append(line)

            # 如果移除了标题，记录日志
            if title_removed:
                self.logger.info(f"[质量修正] 第{unit_num}单元：移除full_content中的重复标题")

            # 使用清理后的内容
            content_to_use = '\n'.join(cleaned_lines)

            if content_type == "novel":
                lines.append(f"### 第{unit_num}章：{title}")
                lines.append(content_to_use)
            else:
                lines.append(f"**第{unit_num}集**：{title}")
                lines.append(content_to_use)

            lines.append("")  # 空行分隔

        return "\n".join(lines)


# 全局实例
_outline_generator = None


def get_outline_generator(db: AsyncSession = None) -> OutlineGenerator:
    """获取大纲生成器实例"""
    global _outline_generator
    if _outline_generator is None:
        _outline_generator = OutlineGenerator(db)
    elif db is not None:
        _outline_generator.db = db
    return _outline_generator


