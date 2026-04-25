"""大纲生成器 - 单元概述生成（非流式）Mixin"""
from typing import Dict
from typing import Any
from datetime import datetime
import re
from app.services.outline_generator.api.constants import ENABLE_QUALITY_CONTROL
from app.services.quality_control import QualityControlService


class UnitSummaryGenerateMixin:
    """单元概述生成（非流式）"""

    async def generate_unit_summaries(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,  # novel/script
        series_type: str = None,  # 剧本类型专用
        episode_duration_range: str = None,  # 剧本类型专用
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_quality_control: bool = True,  # 是否启用质量管控
        qc_mode: str = "manual",  # 新增参数: manual=手动模式, auto=自动模式
        title_style: str = None,  # 标题风格ID（新增）
        title_style_name: str = None  # 标题风格名称（新增）
    ) -> Dict[str, Any]:
        """
        生成单元简要概述（第二阶段）

        Args:
            global_outline: 全局大纲内容
            unit_count: 单元数量（章节数/集数）
            content_type: 内容类型 (novel/script)
            series_type: 剧本类型（剧本专用）
            episode_duration_range: 每集时长区间（剧本专用）
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            user_id: 用户ID
            enable_quality_control: 是否启用质量管控
            title_style: 标题风格ID
            title_style_name: 标题风格名称

        Returns:
            生成结果，包含单元概述列表
        """
        start_time = datetime.now()
        result = {
            "success": False,
            "content": None,
            "parsed": None,
            "error": None,
            "duration_ms": 0,
            "quality_control": None  # 质量管控结果
        }

        try:
            # 确定模块名称
            module_name = f"{content_type}_unit_summaries"

            # 构建输入参数
            input_params = {
                "global_outline": global_outline,
                "chapter_count": str(unit_count),
                "episode_count": str(unit_count),
                "series_type": series_type or "网剧",
                "episode_duration_range": episode_duration_range or "30-45分钟"
            }

            # 生成标题风格指导文本（新增）
            if content_type == "novel" and title_style:
                from app.agents.writing.prompts.title_style_guidance import get_title_style_guidance
                title_style_guidance = get_title_style_guidance(
                    title_style, title_style_name or "")
                input_params["title_style_guidance"] = title_style_guidance
                self.logger.info(
                    f"[单元概述] 使用标题风格: {title_style_name} ({title_style})")
            else:
                input_params["title_style_guidance"] = ""

            # 获取提示词模板（使用默认模板，不需要数据库）
            prompt_template = self.prompt_manager.get_default_prompt(
                module_name)
            if not prompt_template:
                raise ValueError(f"未找到提示词模板: {module_name}")

            # 渲染提示词（填充变量）
            filled_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module_name
            )

            # 添加第一批生成的批次约束提示（防止LLM提前生成后续章节内容）
            unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
                content_type, "章"
            )
            filled_prompt += f"""

## 🚨🚨🚨 极其重要：第1批生成任务 - 严格的章节范围约束

### 当前任务状态
- **本次任务**：生成第1-{unit_count}{unit_label}的概述（第1批）
- **全局大纲**：已提供完整的1-{unit_count}章以上的大纲（供参考整体设定）
- **后续批次**：第{unit_count + 1}章及之后会在后续批次中生成

### ⛔ 绝对禁止的行为
1. ❌ 严禁生成超过第{unit_count}章的内容
2. ❌ 严禁跳过任何章节（必须1, 2, 3, ..., {unit_count}连续）
3. ❌ 严禁将第{unit_count + 1}章及之后的情节压缩到当前批次

### ✅ 必须严格遵守的规则
1. ✅ **必须从第1{unit_label}开始生成**
2. ✅ **必须按顺序生成**：第1章 → 第2章 → ... → 第{unit_count}章
3. ✅ **必须生成恰好{unit_count}个章节**，不多不少
4. ✅ **章节编号必须连续**：1, 2, 3, ..., {unit_count}

### 情节分配要求
- 根据全局大纲中第1-{unit_count}{unit_label}的情节分配进行生成
- 每个章节只生成对应章节的情节，不要提前生成后续章节
- 保持情节发展的自然节奏
- 为后续章节留下发展空间

### 输出格式示例
```
第1章 [章节标题]
梗概：[本章情节概述]
...

第2章 [章节标题]
梗概：[本章情节概述]
...

（继续直到第{unit_count}章）
```

**再次强调：从第1章开始，生成到第{unit_count}章结束，共{unit_count}章！**
"""

            self.logger.info(
                f"[单元概述] 开始生成，模块: {module_name}，单元数: {unit_count}")

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            # 调用LLM生成（不传递model参数，使用provider初始化时的model_name）
            llm_response = await llm_provider.generate(
                prompt=filled_prompt,
                temperature=temperature
            )

            content = llm_response.content if hasattr(
                llm_response, 'content') else str(llm_response)

            # 解析单元概述
            parsed = self.parse_unit_summaries(
                content, unit_count, content_type)

            # ==================== 截断检测与接续生成 ====================
            # 注意: 截断检测已禁用,现在使用分段生成机制替代
            # expected_count = self.get_expected_unit_count(...)
            # truncation_info = self.detect_truncated_units(...)

            # self.logger.info(
            #     f"[单元概述] 截断检测已禁用,使用分段生成机制"
            # )

            # 记录截断信息为空(保持兼容性)
            result["truncation_info"] = {
                "has_truncation": False,
                "missing_units": [],
                "truncated_units": [],
                "message": "截断检测已禁用,使用分段生成机制"
            }

            # ==================== 质量管控系统检查 ====================
            # 注意：根据qc_mode参数决定是否执行质控
            # - manual模式: 跳过自动质控,等待用户手动触发
            # - auto模式: 自动执行质控检测与修正
            # 使用环境变量 ENABLE_QUALITY_CONTROL 控制是否启用
            if ENABLE_QUALITY_CONTROL and enable_quality_control and parsed:
                if qc_mode == "auto":
                    # 自动模式: 执行质控检测与修正
                    try:
                        self.logger.info("[单元概述] 自动模式: 开始自动质控检测与修正...")

                        # 初始化质量管控服务
                        from app.services.quality_control import QualityControlService
                        qc_service = QualityControlService(db=self.db)

                        # 构建章节数据(用于质量管控系统)
                        chapters_data = []
                        for unit_num, unit_data in parsed.items():
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

                        # 执行质量分析（使用专用的单元概述五维度质控机制）
                        quality_report_dict = await self._analyze_unit_summaries_quality(
                            qc_service=qc_service,
                            chapters_data=chapters_data,
                            dimensions=["unit_structure",
                                        "unit_character", "unit_consistency",
                                        "unit_timeline_space", "unit_ooc"],
                            depth="deep",
                            global_outline=global_outline,
                            user_id=user_id
                        )

                        result["quality_control"] = quality_report_dict

                        # 如果有严重问题,尝试自动修正
                        issues = quality_report_dict.get("issues", [])
                        critical_issues = [
                            issue for issue in issues
                            if issue.get("severity") == "critical"
                        ]

                        if critical_issues:
                            self.logger.info(
                                f"[单元概述] 发现{len(critical_issues)}个严重问题,尝试修正..."
                            )

                            # 构建修正提示词
                            revision_prompt = self._build_quality_revision_prompt(
                                unit_summaries=parsed,
                                quality_report_dict=quality_report_dict,
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
                                revision_response.content if hasattr(
                                    revision_response, 'content') else str(revision_response),
                                parsed
                            )

                            if revised_parsed:
                                # 合并修正数据
                                merged_parsed = {}
                                for unit_num, original_data in parsed.items():
                                    if unit_num in revised_parsed:
                                        revised_data = revised_parsed[unit_num]
                                        merged_data = {
                                            **original_data,
                                            "summary": revised_data.get("summary", original_data.get("summary", "")),
                                            "full_content": revised_data.get("full_content", original_data.get("full_content", "")),
                                            "revision_reason": revised_data.get("revision_reason", ""),
                                            "revised_at": datetime.now().isoformat()
                                        }
                                        if "title" in revised_data:
                                            merged_data["title"] = revised_data["title"]
                                        merged_parsed[unit_num] = merged_data
                                    else:
                                        merged_parsed[unit_num] = original_data

                                # 重新构建内容
                                revised_content = self._build_revised_content(
                                    merged_parsed, content_type)
                                content = revised_content
                                parsed = merged_parsed
                                result["auto_revised"] = True
                                result["revised_content"] = revised_content
                                self.logger.info(f"[单元概述] 自动修正完成")
                            else:
                                result["auto_revised"] = False
                                self.logger.warning("[单元概述] 自动修正解析失败")
                        else:
                            result["auto_revised"] = False
                            self.logger.info("[单元概述] 无严重问题,跳过自动修正")

                        result["qc_mode"] = "auto"
                        self.logger.info("[单元概述] 自动模式质控完成")

                    except Exception as qc_error:
                        self.logger.error(
                            f"[单元概述] 自动质控失败: {str(qc_error)}", exc_info=True)
                        result["qc_mode"] = "auto"
                        result["auto_revised"] = False
                        result["quality_control"] = {"error": str(qc_error)}

                elif qc_mode == "manual":
                    # 手动模式: 跳过自动质控,等待用户手动触发
                    self.logger.info("[单元概述] 手动模式: 跳过自动质控,等待用户手动触发")
                    result["qc_mode"] = "manual"
                    result["auto_revised"] = False
                    result["quality_control"] = None  # 明确返回null

            # 记录质控状态（供前端参考）
            result["quality_control_enabled"] = False
            result["quality_control_message"] = "质控检测已改为手动触发，请在生成完成后点击'质量检测'按钮"

            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            result["success"] = True
            result["content"] = content
            result["parsed"] = parsed
            result["duration_ms"] = duration_ms
            result["model"] = getattr(
                llm_response, 'model', llm_provider.model_name)
            result["provider"] = provider

            self.logger.info(
                f"[单元概述] 生成完成，耗时: {duration_ms}ms，解析单元数: {len(parsed)}")

        except Exception as e:
            self.logger.error(f"[单元概述] 生成失败: {str(e)}")
            result["error"] = str(e)

        return result


