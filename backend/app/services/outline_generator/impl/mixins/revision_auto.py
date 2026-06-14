"""大纲生成器 - 自动质控修正与质量修正辅助Mixin"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
from datetime import datetime
import copy
import json
import re


class RevisionAutoMixin:
    """自动质控修正与质量修正辅助"""

    # ==================== Token超限处理阈值 ====================
    MAX_GLOBAL_OUTLINE_CHARS = 2000      # 全局大纲最大字符数（修正提示词中）
    MAX_UNIT_SUMMARIES_CHARS = 8000     # 单元概述总内容最大字符数（修正提示词中）
    MAX_SINGLE_UNIT_CHARS = 2000         # 单个单元最大字符数
    SHARD_BATCH_SIZE = 5                 # 分片处理时每批处理的单元数

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


    async def _auto_qc_and_revise_unit_summaries(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        global_outline: str,
        content_type: str,
        user_id: int,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        单元概述自动质控检测+修正一体化流程（v3.0重构 → v4.0弃用）

        @deprecated v4.0: 剧集/电影类型已禁用自动质控修正。
        小说类型仍保留此方法。剧集/电影类型应使用对话修正功能。

        替代原有的 analyze_unit_summaries_quality_manual + revise_unit_summaries_quality
        两步手动流程，改为一步完成的自动流程。

        流程：
        1. 调用五维度质控分析器进行检测
        2. 检测到问题后，构建修正提示词调用LLM修正
        3. 解析修正结果并构建完整内容
        4. 返回统一结果

        Args:
            unit_summaries: 单元概述字典
            global_outline: 全局大纲内容
            content_type: 内容类型
            user_id: 用户ID
            temperature: 温度参数

        Returns:
            {
                "success": bool,
                "quality_report": dict,
                "revised_content": str or None,
                "revised_parsed": dict or None,
                "changes": list,
                "has_issues": bool,
                "issues_count": int,
                "auto_revised": bool
            }
        """
        # v4.0: 剧集/电影类型跳过自动质控修正
        _is_script = content_type in (
            "series_outline", "movie_outline", "series_script", "movie_script", "script"
        )
        if _is_script:
            self.logger.info(
                f"[单元概述自动质控] 剧本类型({content_type})已禁用自动质控修正，"
                "请使用对话修正功能")
            return {
                "success": True,
                "quality_report": None,
                "revised_content": None,
                "revised_parsed": None,
                "original_content": None,
                "original_parsed": None,
                "changes": [],
                "has_issues": False,
                "issues_count": 0,
                "auto_revised": False,
                "skipped": True,
                "skip_reason": f"剧本类型({content_type})已禁用自动质控修正"
            }

        result = {
            "success": False,
            "quality_report": None,
            "revised_content": None,
            "revised_parsed": None,
            "original_content": None,
            "original_parsed": None,
            "changes": [],
            "has_issues": False,
            "issues_count": 0,
            "auto_revised": False
        }

        if not unit_summaries or len(unit_summaries) == 0:
            self.logger.warning("[单元概述自动质控] 单元概述数据为空")
            return result

        try:
            # ========== 步骤1: 五维度质控分析 ==========
            self.logger.info(
                f"[单元概述自动质控] 开始五维度质控分析，单元数: {len(unit_summaries)}")

            from app.services.quality_control import QualityControlService

            qc_service = QualityControlService(db=self.db)

            # 构建 chapters_data
            chapters_data = []
            for unit_num, unit_data in unit_summaries.items():
                chapters_data.append({
                    "id": int(unit_num),
                    "unit_id": unit_data.get("unit_id", f"unit-{unit_num}"),
                    "chapter_number": int(unit_num),
                    "content": unit_data.get("full_content", "") or unit_data.get("summary", ""),
                    "summary": unit_data.get("summary", ""),
                    "full_content": unit_data.get("full_content", ""),
                    "title": unit_data.get("title", ""),
                    "status": "completed"
                })

            quality_report = await self._analyze_unit_summaries_quality(
                qc_service=qc_service,
                chapters_data=chapters_data,
                dimensions=["unit_structure", "unit_character",
                            "unit_consistency", "unit_timeline_space", "unit_ooc"],
                depth="deep",
                global_outline=global_outline,
                user_id=user_id
            )

            result["quality_report"] = quality_report

            issues = quality_report.get("issues", [])
            result["has_issues"] = len(issues) > 0
            result["issues_count"] = len(issues)

            self.logger.info(
                f"[单元概述自动质控] 五维度分析完成，得分: {quality_report.get('overall_score', 0)}, "
                f"问题数: {len(issues)}"
            )

            # ========== 步骤2: 自动修正 ==========
            if not issues:
                self.logger.info("[单元概述自动质控] 未发现问题，无需修正")
                result["success"] = True
                return result

            self.logger.info(f"[单元概述自动质控] 发现{len(issues)}个问题，开始LLM自动修正...")

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, None
            )
            if not llm_provider:
                self.logger.error("[单元概述自动质控] 未找到LLM提供商")
                result["success"] = True  # 质控报告已生成，只是没修正
                return result

            # Token超限处理：检查内容长度，必要时分片或截断
            processed_unit_summaries, was_sharded = self._apply_token_limits(
                unit_summaries, global_outline)

            if was_sharded:
                self.logger.info(
                    f"[单元概述自动质控] 内容过长已分片处理，分{len(processed_unit_summaries)}批修正")

            # 构建修正提示词（使用处理后的内容）
            revision_prompt = self._build_quality_revision_prompt(
                unit_summaries=processed_unit_summaries,
                quality_report_dict=quality_report,
                global_outline=global_outline,
                content_type=content_type
            )

            # 调用LLM修正
            revision_response = await llm_provider.generate(
                prompt=revision_prompt,
                temperature=temperature
            )

            revision_text = revision_response.content if hasattr(
                revision_response, 'content') else str(revision_response)

            # 解析修正结果
            revised_parsed = self._parse_quality_revision_result(
                revision_text, unit_summaries
            )

            if not revised_parsed:
                self.logger.warning("[单元概述自动质控] 修正结果解析失败")
                result["success"] = True  # 质控报告可用
                return result

            # ========== 步骤3: 合并修正数据 ==========
            merged_parsed = {}
            changes = []

            for unit_num, original_data in unit_summaries.items():
                if unit_num in revised_parsed:
                    revised_data = revised_parsed[unit_num]

                    # 剥离嵌入的章节标题
                    clean_full_content = revised_data.get(
                        "full_content", "") or original_data.get("full_content", "")
                    clean_summary = revised_data.get(
                        "summary", "") or original_data.get("summary", "")

                    if clean_full_content:
                        clean_full_content = self._strip_all_chapter_titles(
                            clean_full_content, content_type, preserve_unit_num=unit_num)
                    if clean_summary:
                        clean_summary = self._strip_all_chapter_titles(
                            clean_summary, content_type, preserve_unit_num=unit_num)

                    merged_data = {
                        **original_data,
                        "summary": clean_summary,
                        "full_content": clean_full_content,
                        "revision_reason": revised_data.get("revision_reason", ""),
                        "revised_at": datetime.now().isoformat()
                    }
                    if "title" in revised_data:
                        merged_data["title"] = revised_data["title"]

                    merged_parsed[unit_num] = merged_data
                    changes.append({
                        "unit_number": unit_num,
                        "revision_reason": revised_data.get("revision_reason", ""),
                        "original_summary": original_data.get("summary", "")[:100],
                        "revised_summary": clean_summary[:100]
                    })
                else:
                    merged_parsed[unit_num] = original_data

            # ========== 步骤3.5: 边界验证保护（v4.0升级：LLM语义验证）==========
            # 修正后的内容必须通过语义边界验证，防止QC修正引入新的越界问题
            if global_outline and len(global_outline) > 50:
                boundary_violations_after_revision = await self._validate_revision_boundaries(
                    merged_parsed=merged_parsed,
                    original_parsed=unit_summaries,
                    revised_parsed=revised_parsed,
                    global_outline=global_outline,
                    content_type=content_type,
                    changes=changes,
                    llm_provider=llm_provider,
                )
                if boundary_violations_after_revision > 0:
                    self.logger.warning(
                        f"[单元概述自动质控] 修正后边界验证发现"
                        f"{boundary_violations_after_revision}处越界，"
                        f"已回退越界的修正")

            # 构建修正后的完整内容（传入原始unit_summaries以保持格式一致性）
            revised_content = self._build_revised_content(
                merged_parsed, content_type, original_unit_summaries=unit_summaries)

            # 同时构建修正前的原始内容（用于版本对比）
            original_content = self._build_revised_content(
                unit_summaries, content_type)

            result["success"] = True
            result["revised_content"] = revised_content
            result["revised_parsed"] = merged_parsed
            result["original_content"] = original_content
            result["original_parsed"] = copy.deepcopy(unit_summaries)  # 深拷贝避免下游修改污染原始数据
            result["changes"] = changes
            result["auto_revised"] = len(changes) > 0

            self.logger.info(
                f"[单元概述自动质控] 修正完成，修正{len(changes)}个单元，"
                f"修正前内容长度: {len(original_content)}, "
                f"修正后内容长度: {len(revised_content)}"
            )

        except Exception as e:
            self.logger.error(
                f"[单元概述自动质控] 执行失败: {e!r}", exc_info=True)
            result["error"] = str(e)

        return result


    def _apply_token_limits(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        global_outline: str
    ) -> tuple:
        """
        Token超限处理：截断过长内容以适配LLM上下文窗口

        策略：
        1. 全局大纲截断至 MAX_GLOBAL_OUTLINE_CHARS
        2. 单个单元内容截断至 MAX_SINGLE_UNIT_CHARS
        3. 单元概述总量截断至 MAX_UNIT_SUMMARIES_CHARS

        Args:
            unit_summaries: 原始单元概述字典
            global_outline: 全局大纲（此方法不修改，在提示词构建时截断）

        Returns:
            (processed_summaries, was_sharded): 处理后的单元概述字典和是否分片标志
        """
        processed = {}
        was_sharded = False

        # 计算总字符数
        total_chars = 0
        for unit_num, unit_data in sorted(unit_summaries.items(), key=lambda x: int(x[0])):
            unit_chars = len(unit_data.get("summary", "")) + \
                         len(unit_data.get("full_content", ""))
            total_chars += unit_chars

        self.logger.info(
            f"[Token限制] 单元概述总字符数: {total_chars}, 阈值: {self.MAX_UNIT_SUMMARIES_CHARS}")

        if total_chars <= self.MAX_UNIT_SUMMARIES_CHARS:
            # 内容未超限，仅做单单元截断
            for unit_num, unit_data in unit_summaries.items():
                processed[unit_num] = self._truncate_single_unit(unit_data)
        else:
            # 内容超限，按比例截断每个单元
            was_sharded = True
            ratio = self.MAX_UNIT_SUMMARIES_CHARS / max(total_chars, 1)

            for unit_num, unit_data in sorted(unit_summaries.items(), key=lambda x: int(x[0])):
                processed[unit_num] = self._truncate_single_unit(
                    unit_data, ratio=ratio)

            self.logger.info(
                f"[Token限制] 内容超限({total_chars} > {self.MAX_UNIT_SUMMARIES_CHARS})，"
                f"按比例{ratio:.2f}截断"
            )

        return processed, was_sharded


    def _truncate_single_unit(
        self,
        unit_data: Dict[str, Any],
        ratio: float = 1.0
    ) -> Dict[str, Any]:
        """
        截断单个单元的内容以适配token限制

        策略：优先保留summary的前半部分和full_content的结构化信息

        Args:
            unit_data: 单元数据
            ratio: 截断比例(0-1)，<1时表示需要压缩

        Returns:
            截断后的单元数据
        """
        if ratio >= 1.0:
            # 不压缩，仅限制单单元最大长度
            max_chars = self.MAX_SINGLE_UNIT_CHARS
        else:
            max_chars = int(self.MAX_SINGLE_UNIT_CHARS * ratio)

        truncated = dict(unit_data)

        # 截断summary
        summary = unit_data.get("summary", "")
        if summary and len(summary) > max_chars:
            truncated["summary"] = summary[:max_chars] + "\n...[内容过长已截断]"

        # 截断full_content
        full_content = unit_data.get("full_content", "")
        if full_content and len(full_content) > max_chars * 2:
            # full_content通常比summary长，给予更多空间
            fc_max = min(max_chars * 2, self.MAX_SINGLE_UNIT_CHARS * 2)
            truncated["full_content"] = full_content[:fc_max] + "\n...[内容过长已截断]"

        return truncated


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

        # v2.5修复：直接修正模式下，只提取受影响的单元编号
        affected_unit_nums = set()
        if is_targeted_revision and sorted_issues:
            issue = sorted_issues[0]
            location = issue.get('location', {})
            chapter = location.get(
                'chapter_number') or location.get('chapter') or issue.get('unit_number')
            if chapter:
                affected_unit_nums.add(str(chapter))
            self.logger.info(
                f"[提示词构建] 直接修正模式，受影响单元: {affected_unit_nums}")

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
        # v2.5修复：直接修正模式下，只发送受影响的单元给LLM，避免LLM误修正全部章节
        units_text = []
        unit_label = "章" if content_type == "novel" else "集"

        for unit_num, unit_data in sorted(unit_summaries.items(), key=lambda x: int(x[0])):
            # 直接修正模式：只包含受影响的单元
            if is_targeted_revision and affected_unit_nums:
                if unit_num not in affected_unit_nums:
                    continue

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

        if is_targeted_revision and affected_unit_nums:
            self.logger.info(
                f"[提示词构建] 直接修正模式：从{len(unit_summaries)}个单元中筛选出{len(units_text)}个受影响单元发送给LLM")

        # v2.4新增: 构建修正要求的额外指令
        if is_targeted_revision:
            targeted_instructions = """### 【重要】直接修正模式 - 只修正指定问题
1. **只修正上述标注的这1个问题**，不要修改其他内容
2. **只修改与该问题直接相关的单元**，不要修改其他单元
3. 保持其他单元和内容的原样，不要做额外修改
4. 如果问题只涉及第X单元，就只修正第X单元，其他单元不要出现在输出中
5. **输出JSON中只包含被修正的单元**，无需输出未被修正的单元

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
6. **人物位置一致性（v2.6新增）**：修正时必须确保人物位置演变合理，不得出现"闪现/瞬移"——即前文已写明某人物在A地（或未跟随/已离开/已死亡），后文不得突然出现在B地
7. {precision_instruction}
8. 保持原有的创意和风格
9. 如果修正了梗概，确保与情节要点和人物状态标注保持一致

## 【格式一致性强制要求 - 极其重要】
1. **禁止改变章节/剧集的标题Markdown格式**：
   - 如果原始使用 `### 第N章：` 格式，修正后的full_content中也必须使用 `### 第N章：`
   - 如果原始使用 `**第N集**：` 格式，也必须保持相同格式
   - 绝对不要将 `**第N集**` 改为 `### 第N章` 或其他格式
2. **禁止改变结构化标记**：
   - 保留原始的 `- **情节要点**：`、`- **人物状态标注**：`、`- **核心冲突**：`、`- **关键转折**：` 等所有结构化小节标题
   - 保留原始的数字列表编号（1. 2. 3.）和缩进层级
   - 保留原始的代码块、引用块等Markdown元素
3. **内容对标**：
   - full_content的输出必须与对应单元的原始输入在**格式结构上完全一致**
   - 只修改存在质量问题的具体文本内容，不改变任何格式标记
4. **示例**：
   如果原始单元格式为：
   ```
   ### 第1章：标题
   完整内容：
   - **情节要点**：
     1. xxx
   - **人物状态标注**：
     - xxx
   ```
   那么修正后的full_content也必须保持 `### 第1章：` 开头，并保留所有markdown结构化标记

## 输出格式
请严格按照以下 JSON 格式输出修正结果：
```json
{{
  "revisions": {{
    "1": {{
      "summary": "修正后的第1单元梗概内容",
      "full_content": "修正后的第1单元完整内容（必须包含情节要点、人物状态标注等所有结构化信息，且格式与原始完全一致）",
      "revision_reason": "修正原因说明"
    }},
    "2": {{
      "summary": "修正后的第2单元梗概内容",
      "full_content": "修正后的第2单元完整内容（必须包含情节要点、人物状态标注等所有结构化信息，且格式与原始完全一致）",
      "revision_reason": "修正原因说明"
    }}
  }}
}}
```

注意：
- 只输出需要修正的单元
- summary 字段是修正后的梗概
- **full_content 字段必须包含完整的单元内容，包括情节要点、人物状态标注等所有结构化信息，且格式与原始输入完全一致**
- 如果某个结构化信息不需要修改，请原样保留
- revision_reason 简要说明修正了什么问题
- 确保 JSON 格式正确，可以被解析
- **重要：full_content和summary字段中包含的双引号必须转义为\\"，中文引号""不需要转义**
- **避免在JSON字符串值中使用未转义的双引号，否则会导致解析失败**
"""
        return prompt


    def _parse_quality_revision_result(
        self,
        revision_text: str,
        original_parsed: Dict[str, Dict[str, Any]]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        解析质量修正结果

        支持三层回退策略:
        1. 标准JSON解析
        2. JSON修复后重试（移除尾部逗号）
        3. 正则表达式字段级提取（处理full_content中未转义引号）

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
            revision_data = None

            # 第1层：标准JSON解析
            try:
                revision_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.logger.warning(
                    f"[质量修正] 标准JSON解析失败: {str(e)[:120]}，尝试修复后重试")

                # 第2层：修复常见JSON问题后重试
                try:
                    repaired_json = self._repair_json_string(json_str)
                    revision_data = json.loads(repaired_json)
                    self.logger.info("[质量修正] JSON修复后解析成功")
                except json.JSONDecodeError as e2:
                    self.logger.warning(
                        f"[质量修正] JSON修复后仍解析失败: {str(e2)[:120]}，回退到正则提取")

                    # 第3层：正则表达式字段级提取
                    fallback_result = self._extract_revisions_fallback(
                        revision_text)
                    if fallback_result:
                        self.logger.info(
                            f"[质量修正] 正则提取成功，解析 {len(fallback_result)} 个单元")
                        return fallback_result

                    self.logger.error("[质量修正] 所有解析策略均失败")
                    return None

            # 标准JSON解析或修复后解析成功，验证格式
            if "revisions" not in revision_data:
                self.logger.warning("[质量修正] JSON 格式错误，缺少 revisions 字段")
                # 尝试正则回退
                fallback_result = self._extract_revisions_fallback(
                    revision_text)
                if fallback_result:
                    return fallback_result
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
                self.logger.info(
                    f"[质量修正] 成功解析 {len(result)} 个单元的修正结果")
                return result
            else:
                self.logger.warning("[质量修正] 未找到有效的修正内容")
                return None

        except Exception as e:
            self.logger.error(f"[质量修正] 解析修正结果失败: {str(e)}")
            return None

    def _repair_json_string(self, json_str: str) -> str:
        """
        修复LLM返回的JSON字符串中的常见格式问题

        修复策略:
        1. 移除尾部逗号（}, 或 ], 前多余的逗号）
        2. 统一中文/全角引号为英文引号
        """
        import re

        fixed = json_str

        # 修复1: 移除对象/数组尾部多余的逗号
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)

        # 修复2: 统一全角引号为半角（LLM偶尔会混用）
        fixed = fixed.replace('\u201c', '"').replace('\u201d', '"')
        fixed = fixed.replace('\u2018', "'").replace('\u2019', "'")

        # 修复3: 移除JSON标记外的markdown代码块标记
        fixed = re.sub(r'^```(?:json)?\s*', '', fixed)
        fixed = re.sub(r'\s*```$', '', fixed)

        return fixed

    def _extract_revisions_fallback(
        self, text: str
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        当JSON解析失败时，使用正则表达式逐字段提取revisions

        此方法专门处理full_content/summary字段中包含未转义双引号的情况。
        工作原理：
        1. 定位每个单元条目（"N": { ... }）
        2. 跟踪大括号深度找到匹配的}
        3. 对每个字段，从field_name后找到值字符串的起始和结束位置
        4. 通过检查后续字符（, } 或下一个字段名）来判断值的结束位置
        """
        import json
        import re

        result = {}

        # 第1步：找到每个单元条目
        # 匹配 "数字": { 作为条目标记
        unit_entry_starts = list(re.finditer(r'"(\d+)"\s*:\s*\{', text))

        if not unit_entry_starts:
            self.logger.warning("[正则提取] 未找到任何单元条目")
            return None

        for idx, match in enumerate(unit_entry_starts):
            unit_num = match.group(1)
            # 大括号起始位置（{字符）
            brace_start = match.end() - 1

            # 第2步：跟踪大括号深度找到匹配的}
            depth = 0
            pos = brace_start
            while pos < len(text):
                ch = text[pos]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        break
                pos += 1

            if depth != 0:
                self.logger.warning(
                    f"[正则提取] 第{unit_num}单元：大括号不匹配，跳过")
                continue

            entry_text = text[brace_start:pos + 1]  # 从{到匹配的}

            # 第3步：提取各字段值
            entry = {}

            # 已知的字段名列表
            known_fields = [
                'summary', 'full_content', 'revision_reason', 'title'
            ]

            for field_name in known_fields:
                # 找到字段起始位置: "field_name": "
                field_start_pattern = rf'"{field_name}"\s*:\s*"'
                field_start_match = re.search(
                    field_start_pattern, entry_text)
                if not field_start_match:
                    continue

                value_start = field_start_match.end()

                # 扫描找到值字符串的结束位置
                # 策略：扫描每个"字符，检查其后是否为结构标记（, } 或下一个字段名）
                value_end = -1
                i = value_start
                while i < len(entry_text):
                    if entry_text[i] == '\\' and i + 1 < len(entry_text):
                        # 跳过转义字符
                        i += 2
                        continue
                    if entry_text[i] == '"':
                        # 检查此"是否可能为值的结束
                        remaining = entry_text[i + 1:].lstrip()
                        if not remaining:
                            # 字符串到末尾
                            value_end = i
                            break
                        if remaining[0] in ',}':
                            # 后面紧跟逗号或右大括号
                            value_end = i
                            break
                        # 检查是否紧跟下一个已知字段名
                        next_field_pattern = r'"(?:' + \
                            '|'.join(known_fields) + r')"\s*:'
                        if re.match(next_field_pattern, remaining):
                            value_end = i
                            break
                    i += 1

                if value_end > value_start:
                    raw_value = entry_text[value_start:value_end]
                    # 尝试JSON反转义
                    try:
                        entry[field_name] = json.loads(
                            f'"{raw_value}"')
                    except (json.JSONDecodeError, ValueError):
                        # 回退：手动处理常见转义序列
                        unescaped = raw_value.replace(
                            '\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                        entry[field_name] = unescaped

            # 至少需要summary或full_content
            if entry.get('summary') or entry.get('full_content'):
                summary = entry.get('summary', '')
                fc = entry.get('full_content', summary)
                result[unit_num] = {
                    'summary': summary,
                    'full_content': fc if fc else summary,
                    'revision_reason': entry.get('revision_reason', '')
                }
                if 'title' in entry:
                    result[unit_num]['title'] = entry['title']

        if result:
            self.logger.info(
                f"[正则提取] 成功提取 {len(result)} 个单元的修正结果")
            return result

        self.logger.warning("[正则提取] 未找到有效的修正内容")
        return None


    def _strip_all_chapter_titles(
        self, content: str, content_type: str,
        preserve_unit_num: Optional[str] = None
    ) -> str:
        """
        从内容文本中剥离所有嵌入的章节/剧集Markdown标题行

        LLM在修正full_content时可能会附带其他章节的标题（如第1章标题出现在第46章的修正内容中）。
        此方法移除所有以 ### 第N章： 或 **第N集**： 开头的行，防止内容中出现重复/无关标题。

        Args:
            content: 待清理的内容文本
            content_type: 内容类型（novel/script）
            preserve_unit_num: 要保留的单元编号（该单元的标题不会被移除）

        Returns:
            清理后的内容文本
        """
        import re

        unit_label = "章" if content_type == "novel" else "集"

        # 匹配所有形式的章节标题行
        title_patterns = [
            # ### 第N章：xxx 或 ### 第N章: xxx
            rf"^###\s*第[\u4e00二三四五六七八九十百千\d]+{unit_label}[:：]\s*.*$",
            # **第N集**：xxx
            rf"^\*\*第[\u4e00二三四五六七八九十百千\d]+{unit_label}\*\*[:：]\s*.*$",
            # # 第N章 xxx 或 ## 第N章 xxx
            rf"^#{{1,3}}\s*第[\u4e00二三四五六七八九十百千\d]+{unit_label}\b.*$",
        ]

        # 如果要保留特定单元的标题，构建排除模式
        preserve_pattern = None
        if preserve_unit_num is not None:
            preserve_pattern = re.compile(
                rf"^#+\s*第{preserve_unit_num}{unit_label}",
                re.IGNORECASE
            )

        lines = content.split('\n')
        cleaned_lines = []
        removed_count = 0

        for line in lines:
            stripped = line.strip()
            # 如果要保留当前单元的标题，先检查是否匹配
            if preserve_pattern and preserve_pattern.match(stripped):
                cleaned_lines.append(line)
                continue

            is_title = False
            for pattern in title_patterns:
                if re.match(pattern, stripped, re.IGNORECASE):
                    is_title = True
                    break
            if is_title:
                removed_count += 1
            else:
                cleaned_lines.append(line)

        if removed_count > 0:
            self.logger.debug(
                f"[标题剥离] 移除了 {removed_count} 行嵌入的章节标题"
                + (f"（保留第{preserve_unit_num}单元标题）" if preserve_unit_num else "")
            )

        return '\n'.join(cleaned_lines)

    def _build_revised_content(
        self,
        revised_parsed: Dict[str, Dict[str, Any]],
        content_type: str,
        original_unit_summaries: Dict[str, Dict[str, Any]] = None
    ) -> str:
        """
        根据修正后的解析结果构建完整内容

        v3.1 格式一致性修复：
        - 从原始unit_summaries中推断每个单元的标题格式，保证修正后格式与原始完全一致
        - 如果无法推断，回退到默认格式（novel用###，script用**）

        Args:
            revised_parsed: 修正后的单元概述字典
            content_type: 内容类型
            original_unit_summaries: 原始单元概述字典（用于推断格式）

        Returns:
            完整的单元概述文本
        """
        # [2026-05-05] 修复：使用完整映射字典，电影类型使用"场"标签
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场",
                      "movie_outline": "场", "series_outline": "集"}.get(content_type, "章")
        lines = []

        # 推断每个单元应使用的标题格式
        unit_formats = {}
        if original_unit_summaries:
            unit_formats = self._infer_unit_title_formats(
                original_unit_summaries, content_type, unit_label)

        for unit_num in sorted(revised_parsed.keys(), key=int):
            unit_data = revised_parsed[unit_num]
            title = unit_data.get("title", "")
            summary = unit_data.get("summary", "")
            full_content = unit_data.get("full_content", "")

            # 优先使用full_content（包含情节要点、人物状态标注等完整结构化信息）
            # 如果没有full_content，则使用summary
            content_to_use = full_content if full_content else summary

            # v2.5修复: 剥离full_content中所有嵌入的章节标题（不仅是当前单元的）
            content_to_use = self._strip_all_chapter_titles(
                content_to_use, content_type)

            # 使用推断的格式或默认格式
            title_format = unit_formats.get(unit_num)
            if title_format:
                lines.append(title_format.format(
                    unit_num=unit_num, title=title, unit_label=unit_label))
            elif content_type == "novel":
                lines.append(f"### 第{unit_num}章：{title}")
            elif content_type in ("movie_script", "movie_outline"):
                # [2026-05-05] 修复：电影使用"场"标签，统一**包裹格式
                lines.append(f"**第{unit_num}场：{title}**")
            else:
                # [2026-05-05] 修复：剧集使用"集"标签，统一**包裹格式（前端解析器匹配）
                lines.append(f"**第{unit_num}集：{title}**")

            # [2026-05-05] 修复：标题和内容之间必须有空行，否则Markdown渲染时会合并到同一行
            lines.append("")  # 标题后空行
            lines.append(content_to_use)
            lines.append("")  # 单元之间空行分隔

        return "\n".join(lines)

    def _infer_unit_title_formats(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        content_type: str,
        unit_label: str
    ) -> Dict[str, str]:
        """
        从原始unit_summaries中推断每个单元的标题格式模板

        支持的格式：
        - ### 第N章：{title}
        - ### 第N章 {title}
        - ## 第N章：{title}
        - **第N集**：{title}
        - 【第N章】{title}

        Args:
            unit_summaries: 原始单元概述字典
            content_type: 内容类型
            unit_label: 单元标签（章/集）

        Returns:
            {unit_num: format_template} 字典，format_template支持 .format(unit_num=, title=, unit_label=)
        """
        import re
        formats = {}

        # 从每个单元的full_content中提取原始标题格式
        for unit_num, unit_data in unit_summaries.items():
            full_content = unit_data.get("full_content", "")
            if not full_content:
                continue

            # 尝试匹配多种标题格式（半角:和全角：分别处理，保留原始冒号类型）
            title_patterns = [
                # ### 第N章：xxx（全角冒号）
                (r"^###\s*第([\u4e00二三四五六七八九十百千\d]+)" + unit_label + r"：\s*(.*)$",
                 "### 第{unit_num}{unit_label}：{title}"),
                # ### 第N章: xxx（半角冒号）
                (r"^###\s*第([\u4e00二三四五六七八九十百千\d]+)" + unit_label + r":\s*(.*)$",
                 "### 第{unit_num}{unit_label}:{title}"),
                # ### 第N章 xxx（空格分隔，无冒号）
                (r"^###\s*第([\u4e00二三四五六七八九十百千\d]+)" + unit_label + r"\s+(.*)$",
                 "### 第{unit_num}{unit_label} {title}"),
                # ## 第N章：xxx（全角冒号）
                (r"^##\s*第([\u4e00二三四五六七八九十百千\d]+)" + unit_label + r"：\s*(.*)$",
                 "## 第{unit_num}{unit_label}：{title}"),
                # ## 第N章: xxx（半角冒号）
                (r"^##\s*第([\u4e00二三四五六七八九十百千\d]+)" + unit_label + r":\s*(.*)$",
                 "## 第{unit_num}{unit_label}:{title}"),
                # **第N集**：xxx（全角冒号）
                (r"^\*\*第([\u4e00二三四五六七八九十百千\d]+)" + unit_label + r"\*\*：\s*(.*)$",
                 "**第{unit_num}{unit_label}**：{title}"),
                # **第N集**: xxx（半角冒号）
                (r"^\*\*第([\u4e00二三四五六七八九十百千\d]+)" + unit_label + r"\*\*:\s*(.*)$",
                 "**第{unit_num}{unit_label}**:{title}"),
                # 【第N章】xxx（无冒号）
                (r"^【第([\u4e00二三四五六七八九十百千\d]+)" + unit_label + r"】(.*)$",
                 "【第{unit_num}{unit_label}】{title}"),
            ]

            first_line = full_content.split('\n')[0].strip() if full_content else ""
            for pattern, template in title_patterns:
                if re.match(pattern, first_line):
                    formats[unit_num] = template
                    break

        if formats:
            self.logger.debug(
                f"[格式推断] 从{len(formats)}个单元推断出标题格式")

        return formats

    async def _validate_revision_boundaries(
        self,
        merged_parsed: Dict[str, Dict[str, Any]],
        original_parsed: Dict[str, Dict[str, Any]],
        revised_parsed: Dict[str, Dict[str, Any]],
        global_outline: str,
        content_type: str,
        changes: List[Dict[str, Any]],
        llm_provider=None,
    ) -> int:
        """
        QC修正后的语义边界验证保护（v4.0升级：两级验证链）

        对每个被修正的章节进行语义边界验证（关键词预筛 + LLM语义验证），
        如果发现修正后的内容引入了新的边界违规，则回退到修正前的原始版本。

        v4.0升级：
        - 从关键词匹配升级为LLM语义验证（两级验证链）
        - 关键词预筛选快速排除合规章节
        - 只有疑似越界时才触发LLM语义验证

        Args:
            merged_parsed: 合并后的解析结果（会被原地修改：回退越界修正）
            original_parsed: 修正前的原始解析结果
            revised_parsed: 修正后的解析结果
            global_outline: 全局大纲
            content_type: 内容类型
            changes: 变更列表（会被原地修改：移除回退的变更）
            llm_provider: LLM提供者实例（语义验证需要）

        Returns:
            发现的边界违规数量
        """
        unit_label = "章" if content_type == "novel" else "集"
        total_violations = 0

        # 提取边界映射
        try:
            boundary_map = self.extract_chapter_boundaries(
                global_outline,
                max(int(k) for k in merged_parsed.keys()),
                unit_label
            )
        except Exception as e:
            self.logger.warning(
                f"[边界验证] 边界提取失败，跳过: {e!r}")
            return 0

        if not boundary_map:
            return 0

        # 只验证被修正过的章节
        for change in changes:
            unit_num = str(change["unit_number"])
            if unit_num not in merged_parsed or unit_num not in original_parsed:
                continue

            chapter_num = int(unit_num)
            revised_content = (
                merged_parsed[unit_num].get("full_content", "")
                or merged_parsed[unit_num].get("summary", "")
            )

            if not revised_content:
                continue

            # v4.0升级：执行语义边界验证（关键词预筛 + LLM语义验证）
            semantic_validation = await self.validate_boundary_semantic(
                chapter_content=revised_content,
                chapter_num=chapter_num,
                boundary_map=boundary_map,
                llm_provider=llm_provider,
                unit_label=unit_label,
            )

            if not semantic_validation.passed or semantic_validation.violations:
                self.logger.warning(
                    f"[边界验证] 第{chapter_num}{unit_label}修正后出现边界违规，"
                    f"回退到修正前版本"
                )
                self.logger.info(
                    f"[边界验证] 违规详情: {semantic_validation.violations[:3]}")

                # 回退：恢复修正前的原始内容
                merged_parsed[unit_num] = original_parsed[unit_num]

                # 从changes列表中移除该变更
                change["reverted"] = True
                change["revert_reason"] = (
                    f"边界违规: {'; '.join(semantic_validation.violations[:2])}")

                total_violations += 1

        # 清理被回退的changes
        changes[:] = [c for c in changes if not c.get("reverted")]

        if total_violations > 0:
            self.logger.info(
                f"[边界验证] 共回退{total_violations}处修正，"
                f"剩余有效修正{len(changes)}处")

        return total_violations


