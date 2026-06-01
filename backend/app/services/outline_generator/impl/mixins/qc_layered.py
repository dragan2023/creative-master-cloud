"""大纲生成器 - 分层质量管控与一致性检测Mixin"""
from typing import Dict
from typing import Any
import json
import re
from app.services.quality_control import QualityControlService


class QcLayeredMixin:
    """分层质量管控与一致性检测"""

    async def _perform_layered_quality_control(
        self,
        full_parsed: Dict[str, Dict[str, Any]],
        global_outline: str,
        content_type: str,
        is_resume: bool,
        new_units_start: int = None,
        llm_provider=None,
        temperature: float = 0.7,
        workflow_yield=None,
        replace_content_yield=None,
        user_id: int = 0
    ) -> Dict:
        """
        分层质量管控（核心方法）

        架构：
        - 第一层：局部检查（所有章节）
        - 第二层：边界检查（续生成时增强）
        - 第三层：增量全局检查（续生成时抽查）
        """
        from app.services.quality_control import QualityControlService

        qc_service = QualityControlService(db=self.db)

        # ==================== 第一层：局部检查 ====================
        if workflow_yield:
            yield {
                "type": "step", "step": "qc_local", "status": "running",
                "message": "正在进行局部质量检查...",
                "icon": "Search"
            }

        # 构建章节数据
        chapters_data = []
        for unit_num, unit_data in full_parsed.items():
            chapters_data.append({
                "id": int(unit_num),
                "unit_id": unit_data.get("unit_id", f"unit-{unit_num}"),
                "chapter_number": int(unit_num),
                "content": unit_data.get("full_content", "") or unit_data.get("summary", ""),
                "summary": unit_data.get("summary", ""),
                "full_content": unit_data.get("full_content", ""),
                "title": unit_data.get("title", ""),
                "status": "completed",
                "is_resumed": unit_data.get("is_resumed", False)
            })

        # 执行单元概述专用的5维度质量分析
        quality_report = await self._analyze_unit_summaries_quality(
            qc_service=qc_service,
            chapters_data=chapters_data,
            dimensions=["unit_structure",
                        "unit_character", "unit_consistency",
                        "unit_timeline_space", "unit_ooc"],
            depth="deep",
            global_outline=global_outline,
            user_id=user_id
        )

        if workflow_yield:
            issue_count = len(quality_report.get("issues", []))
            yield {
                "type": "step", "step": "qc_local", "status": "done",
                "message": f"局部检查完成，发现{issue_count}个问题",
                "icon": "Search"
            }

        # ==================== 第二层：边界检查（所有模式，不仅限于续生成）====================
        # v4.0：边界检查在所有模式下运行，防止QC修正引入越界问题
        boundary_chapter_start = new_units_start if (is_resume and new_units_start) else 1
        if workflow_yield:
            yield {
                "type": "step", "step": "qc_boundary", "status": "running",
                "message": "正在检查续生成边界连贯性...",
                "icon": "Connection"
            }

        boundary_report = await self._check_resume_boundary(
            full_parsed=full_parsed,
            new_units_start=boundary_chapter_start,
            content_type=content_type,
            llm_provider=llm_provider,
            temperature=temperature
        )

        # 合并边界检查问题
        quality_report.setdefault("issues", []).extend(
            boundary_report.get("issues", [])
        )

        if workflow_yield:
            yield {
                "type": "step", "step": "qc_boundary", "status": "done",
                "message": f"边界检查完成，发现{len(boundary_report.get('issues', []))}个问题",
                "icon": "Connection"
            }

        # ==================== 第三层：增量全局检查（续生成抽查）====================
        if is_resume:
            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_global_incremental", "status": "running",
                    "message": "正在进行增量全局检查...",
                    "icon": "Grid"
                }

            global_report = await self._check_global_consistency_incremental(
                full_parsed=full_parsed,
                global_outline=global_outline,
                new_units_start=new_units_start,
                content_type=content_type,
                llm_provider=llm_provider,
                temperature=temperature
            )

            # 合并全局检查问题
            quality_report.setdefault("issues", []).extend(
                global_report.get("issues", [])
            )

            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_global_incremental", "status": "done",
                    "message": f"全局检查完成，发现{len(global_report.get('issues', []))}个问题",
                    "icon": "Grid"
                }

        # ==================== 自动修正严重问题 ====================
        critical_issues = [
            issue for issue in quality_report.get("issues", [])
            if issue.get("severity") == "critical"
        ]

        if critical_issues:
            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_revision", "status": "running",
                    "message": f"发现{len(critical_issues)}个严重问题，正在修正...",
                    "icon": "Edit"
                }

            revision_prompt = self._build_quality_revision_prompt(
                unit_summaries=full_parsed,
                quality_report_dict=quality_report,
                global_outline=global_outline,
                content_type=content_type
            )

            # 调用LLM修正
            revision_response = await llm_provider.generate(
                prompt=revision_prompt,
                temperature=temperature
            )

            # 解析修正结果并应用
            revised_parsed = self._parse_quality_revision_result(
                revision_response.content, full_parsed
            )

            if revised_parsed:
                # 保存修正前后的对比信息
                for unit_num, revised_data in revised_parsed.items():
                    if unit_num in full_parsed:
                        full_parsed[unit_num]["original_summary"] = full_parsed[unit_num].get(
                            "summary", "")
                        full_parsed[unit_num]["original_full_content"] = full_parsed[unit_num].get(
                            "full_content", "")
                        full_parsed[unit_num]["summary"] = revised_data.get(
                            "summary", full_parsed[unit_num]["summary"])
                        # 同时应用LLM返回的full_content（如果提供且非空）
                        revised_full_content = revised_data.get("full_content", "")
                        if revised_full_content and revised_full_content != revised_data.get("summary", ""):
                            full_parsed[unit_num]["full_content"] = revised_full_content
                        full_parsed[unit_num]["quality_revised"] = True
                        full_parsed[unit_num]["revision_reason"] = revised_data.get(
                            "revision_reason", "")

                # 重新生成完整内容（使用_build_revised_content保留完整full_content）
                revised_content = self._build_revised_content(
                    full_parsed, content_type)

                if replace_content_yield:
                    yield revised_content, f"已修正{len(revised_parsed)}个单元的质量问题"

                self.logger.info("[单元概述] 质量管控修正完成")

                # ========== v4.0新增：QC修正后边界语义验证保护 ==========
                # 修正后的内容必须通过语义边界验证，防止QC修正引入新的越界问题
                if global_outline and len(global_outline) > 50 and llm_provider:
                    unit_label = {"novel": "章", "series_script": "集"}.get(
                        content_type, "章")
                    try:
                        boundary_map = self.extract_chapter_boundaries(
                            global_outline,
                            max(int(k) for k in full_parsed.keys()),
                            unit_label
                        )
                        if boundary_map:
                            for unit_num in list(revised_parsed.keys()):
                                if unit_num not in full_parsed:
                                    continue
                                chapter_num = int(unit_num)
                                content = (
                                    full_parsed[unit_num].get("full_content", "")
                                    or full_parsed[unit_num].get("summary", "")
                                )
                                if not content:
                                    continue

                                semantic_result = await self.validate_boundary_semantic(
                                    chapter_content=content,
                                    chapter_num=chapter_num,
                                    boundary_map=boundary_map,
                                    llm_provider=llm_provider,
                                    unit_label=unit_label,
                                )

                                if not semantic_result.passed or semantic_result.violations:
                                    self.logger.warning(
                                        f"[QC边界保护] 第{chapter_num}{unit_label}"
                                        f"修正后语义越界，回退到修正前版本"
                                    )
                                    self.logger.info(
                                        f"[QC边界保护] 违规: {semantic_result.violations[:3]}")
                                    # 回退：恢复修正前的original_summary和original_full_content
                                    if "original_summary" in full_parsed[unit_num]:
                                        full_parsed[unit_num]["summary"] = (
                                            full_parsed[unit_num]["original_summary"]
                                        )
                                        del full_parsed[unit_num]["original_summary"]
                                        full_parsed[unit_num]["quality_revised"] = False
                                    if "original_full_content" in full_parsed[unit_num]:
                                        full_parsed[unit_num]["full_content"] = (
                                            full_parsed[unit_num]["original_full_content"]
                                        )
                                        del full_parsed[unit_num]["original_full_content"]
                    except Exception as e:
                        self.logger.warning(
                            f"[QC边界保护] 语义边界验证异常: {e!r}")

            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_revision", "status": "done",
                    "message": "质量修正完成",
                    "icon": "Edit"
                }
        else:
            if workflow_yield:
                yield {
                    "type": "step", "step": "quality_control", "status": "done",
                    "message": "质量检查通过，无需修正",
                    "icon": "Check"
                }

        # 发送质量管控报告给前端
        if workflow_yield and quality_report:
            yield {
                "type": "quality_report",
                "report": quality_report
            }

        # 异步生成器不能使用return返回值


    async def _check_resume_boundary(
        self,
        full_parsed: Dict[str, Dict[str, Any]],
        new_units_start: int,
        content_type: str,
        llm_provider,
        temperature: float
    ) -> Dict:
        """
        边界检查：确保续生成部分与前文连贯

        检查范围：第(new_units_start-5) 到 第(new_units_start+5)章
        """
        unit_label = {"novel": "章", "series_script": "集"}.get(
            content_type, "章")

        # 获取边界章节（前后各5章）
        boundary_start = max(1, new_units_start - 5)
        boundary_end = min(new_units_start + 5, max(int(k)
                           for k in full_parsed.keys()))

        boundary_units = []
        for num in range(boundary_start, boundary_end + 1):
            if str(num) in full_parsed:
                unit = full_parsed[str(num)]
                is_new = num >= new_units_start
                boundary_units.append(
                    f"{'【新生成】' if is_new else '【已有】'}"
                    f"第{num}{unit_label}《{unit.get('title', '')}》\n"
                    f"梗概：{unit.get('summary', '')}"
                )

        check_prompt = f"""你是专业的小说/剧本结构审核专家。

## 任务
检查续生成章节与前文的连贯性。重点关注：

1. **情节衔接**：第{new_units_start-1}{unit_label}到第{new_units_start}{unit_label}的过渡是否自然？
2. **人物状态**：人物性格、关系、能力是否保持一致？
3. **人物位置一致性（重点）**：是否有"闪现/瞬移"现象？即前文明确写明某人物在A地（或未跟随/已离开/已死亡），后续{unit_label}节中该人物却突然出现在B地？
4. **伏笔线索**：前文埋下的伏笔是否在后续{unit_label}节中得到发展或回收？
5. **时间线**：时间顺序是否合理？
6. **节奏变化**：情节节奏是否有突兀变化？

## 边界{unit_label}节内容
{chr(10).join(boundary_units)}

## 输出格式
以JSON格式输出检查结果：
```json
{{
  "issues": [
    {{
      "type": "boundary_continuity",
      "description": "问题描述",
      "severity": "critical|high|medium|low",
      "affected_units": ["88", "89", "90", "91"],
      "suggestion": "修改建议"
    }}
  ]
}}
```
"""

        try:
            response = await llm_provider.generate(
                prompt=check_prompt,
                temperature=temperature
            )

            # 解析JSON响应
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                result = json.loads(json_match.group(0))
                return {"issues": result.get("issues", [])}

            return {"issues": []}

        except Exception as e:
            self.logger.error(f"[边界检查] 失败: {str(e)}")
            return {"issues": []}


    async def _check_global_consistency_incremental(
        self,
        full_parsed: Dict[str, Dict[str, Any]],
        global_outline: str,
        new_units_start: int,
        content_type: str,
        llm_provider,
        temperature: float
    ) -> Dict:
        """
        增量全局检查：续生成时抽查关键路径

        不检查全部章节，而是抽查：
        1. 开头3章（故事起点）
        2. 中间3章（转折点）
        3. 结尾3章（高潮结局）
        4. 新生成的章节（重点）
        """
        total_units = len(full_parsed)
        unit_label = {"novel": "章", "series_script": "集"}.get(
            content_type, "章")

        # 选择抽查章节
        sample_units = set()

        # 开头3章
        for num in range(1, min(4, total_units + 1)):
            sample_units.add(num)

        # 中间3章
        mid = total_units // 2
        for num in range(mid - 1, mid + 2):
            if 1 <= num <= total_units:
                sample_units.add(num)

        # 结尾3章
        for num in range(max(1, total_units - 2), total_units + 1):
            sample_units.add(num)

        # 新生成的章节（重点）
        for num in range(new_units_start, total_units + 1):
            sample_units.add(num)

        # 构建抽查内容
        sample_units_text = []
        for num in sorted(sample_units):
            if str(num) in full_parsed:
                unit = full_parsed[str(num)]
                is_new = num >= new_units_start
                sample_units_text.append(
                    f"{'【新生成】' if is_new else '【抽查】'}"
                    f"第{num}{unit_label}《{unit.get('title', '')}》\n"
                    f"梗概：{unit.get('summary', '')}"
                )

        check_prompt = f"""你是专业的小说/剧本质量审核专家。

## 任务
对以下抽查章节进行全局一致性检查：

1. **结构完整性**：故事三幕结构是否完整？
2. **伏笔回收**：开头埋下的伏笔是否在结尾得到回收？
3. **人物弧线**：主要角色的成长弧线是否合理？
4. **主题一致性**：全篇是否围绕核心主题展开？
5. **新生成章节质量**：第{new_units_start}-{total_units}{unit_label}是否与前面章节质量一致？

## 抽查章节内容
{chr(10).join(sample_units_text)}

## 全局大纲（参考）
{global_outline[:3000]}

## 输出格式
```json
{{
  "issues": [
    {{
      "type": "global_consistency",
      "description": "问题描述",
      "severity": "critical|high|medium|low",
      "affected_units": ["5", "95"],
      "suggestion": "修改建议"
    }}
  ]
}}
```
"""

        try:
            response = await llm_provider.generate(
                prompt=check_prompt,
                temperature=temperature
            )

            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                result = json.loads(json_match.group(0))
                return {"issues": result.get("issues", [])}

            return {"issues": []}

        except Exception as e:
            self.logger.error(f"[增量全局检查] 失败: {str(e)}")
            return {"issues": []}


