"""大纲生成器 - 单元概述生成（非流式）Mixin"""
from typing import Dict
from typing import Any
from datetime import datetime
import re
from app.services.outline_generator.api.constants import ENABLE_QUALITY_CONTROL
from app.services.quality_control import QualityControlService
import os

# 环境变量控制：是否启用原子化逐章生成模式（默认启用）
_ENABLE_ATOMIC_MODE = os.environ.get("ATOMIC_CHAPTER_MODE", "1") == "1"


class UnitSummaryGenerateMixin:
    """单元概述生成（非流式）"""

    async def generate_unit_summaries(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,  # novel/script/movie_outline/series_outline
        series_type: str = None,  # 剧本类型专用
        episode_duration_range: str = None,  # 剧本类型专用
        provider: str = None,
        model: str = None,
        temperature: float = 0.5,  # 调整为0.5,平衡创造性与遵循性（v2.6）
        user_id: int = None,
        enable_quality_control: bool = True,  # 是否启用质量管控
        qc_mode: str = "auto",  # 质控模式（v3.0：仅自动模式）
        title_style: str = None,  # 标题风格ID（新增）
        title_style_name: str = None,  # 标题风格名称（新增）
        atomic_mode: bool = None,  # 是否使用原子化逐章生成（None=使用环境变量）
        project_id: int = None,  # GraphRAG知识库增强（v4.1新增）
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

            当 atomic_mode=True 时，额外返回 boundary_report 字段
        """
        use_atomic = atomic_mode if atomic_mode is not None else _ENABLE_ATOMIC_MODE

        if use_atomic:
            return await self._generate_unit_summaries_atomic(
                global_outline=global_outline,
                unit_count=unit_count,
                content_type=content_type,
                series_type=series_type,
                episode_duration_range=episode_duration_range,
                provider=provider,
                model=model,
                temperature=temperature,
                user_id=user_id,
                enable_quality_control=enable_quality_control,
                qc_mode=qc_mode,
                title_style=title_style,
                title_style_name=title_style_name,
                project_id=project_id,
            )

        return await self._generate_unit_summaries_legacy(
            global_outline=global_outline,
            unit_count=unit_count,
            content_type=content_type,
            series_type=series_type,
            episode_duration_range=episode_duration_range,
            provider=provider,
            model=model,
            temperature=temperature,
            user_id=user_id,
            enable_quality_control=enable_quality_control,
            qc_mode=qc_mode,
            title_style=title_style,
            title_style_name=title_style_name,
        )

    async def _generate_unit_summaries_atomic(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,
        series_type: str = None,
        episode_duration_range: str = None,
        provider: str = None,
        model: str = None,
        temperature: float = 0.5,
        user_id: int = None,
        enable_quality_control: bool = True,
        qc_mode: str = "auto",
        title_style: str = None,
        title_style_name: str = None,
        project_id: int = None,  # GraphRAG知识库增强（v4.1新增）
    ) -> Dict[str, Any]:
        """原子化逐章生成模式（新增）"""
        self.logger.info(
            f"[单元概述] 使用原子化逐章生成模式，总章节数: {unit_count}")

        # 获取LLM提供商
        llm_provider = await self.llm_manager.get_provider_from_db(
            self.db, user_id, provider)
        if not llm_provider:
            raise ValueError(f"未找到LLM提供商: {provider}")

        # 调用原子化生成器
        result = await self.generate_all_chapters_atomic(
            global_outline=global_outline,
            unit_count=unit_count,
            content_type=content_type,
            user_id=user_id,
            llm_provider=llm_provider,
            temperature=temperature,
            series_type=series_type,
            episode_duration_range=episode_duration_range,
            title_style=title_style,
            title_style_name=title_style_name,
            start_from_unit=1,
            existing_parsed=None,
            project_id=project_id,
        )

        # QC处理（原子化模式下每章已单独验证，此处做整体QC）
        if enable_quality_control and result.get("success") and result.get("parsed"):
            if qc_mode == "auto":
                try:
                    self.logger.info("[单元概述-原子化] 执行整体QC检测...")
                    from app.services.quality_control import QualityControlService
                    qc_service = QualityControlService(db=self.db)

                    chapters_data = []
                    for unit_num, unit_data in result["parsed"].items():
                        chapters_data.append({
                            "id": int(unit_num),
                            "unit_id": unit_data.get("unit_id", f"unit-{unit_num}"),
                            "chapter_number": int(unit_num),
                            "content": unit_data.get("full_content", "") or unit_data.get("summary", ""),
                            "summary": unit_data.get("summary", ""),
                            "full_content": unit_data.get("full_content", ""),
                            "title": unit_data.get("title", ""),
                            "status": "completed"})

                    quality_report = await self._analyze_unit_summaries_quality(
                        qc_service=qc_service,
                        chapters_data=chapters_data,
                        dimensions=["unit_structure", "unit_character",
                                    "unit_consistency", "unit_timeline_space", "unit_ooc"],
                        depth="deep",
                        global_outline=global_outline,
                        user_id=user_id)

                    result["quality_control"] = quality_report
                    result["qc_mode"] = "auto"

                except Exception as qc_error:
                    self.logger.error(
                        f"[单元概述-原子化] QC失败: {qc_error!r}")
                    result["quality_control"] = {"error": str(qc_error)}
            else:
                result["qc_mode"] = "manual"
                result["quality_control"] = None

        result["quality_control_enabled"] = False
        result["quality_control_message"] = (
            "质控检测已改为手动触发，请在生成完成后点击'质量检测'按钮")
        result["provider"] = provider

        return result

    async def _generate_unit_summaries_legacy(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,
        series_type: str = None,
        episode_duration_range: str = None,
        provider: str = None,
        model: str = None,
        temperature: float = 0.5,
        user_id: int = None,
        enable_quality_control: bool = True,
        qc_mode: str = "auto",
        title_style: str = None,
        title_style_name: str = None,
    ) -> Dict[str, Any]:
        """原有的一次性全量生成模式（保留作为回退）"""
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
            unit_label = {"novel": "章", "series_script": "集", "movie_script": "场", "movie_outline": "场", "series_outline": "集"}.get(
                content_type, "章"
            )
            input_params = {
                "global_outline": global_outline,
                "chapter_count": str(unit_count),
                "episode_count": str(unit_count),
                "series_type": series_type or "网剧",
                "episode_duration_range": episode_duration_range or "30-45分钟",
                "unit_label": unit_label  # 新增：单元标签变量
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

            # 章节边界识别机制（v4.0正向版）- 放在全局大纲之前，用正向指引告诉LLM分章结构
            unit_label = {"novel": "章", "series_script": "集", "movie_script": "场", "movie_outline": "场", "series_outline": "集"}.get(
                content_type, "章"
            )
            boundary_constraint = f"""# 章节边界指引（请首先阅读）

## 全局大纲中的分章结构

全局大纲包含【分章大纲】部分，其中为每个章节分配了专属内容。在开始创作之前，请先做以下工作：

### 第一步：定位分章大纲
在全局大纲中找到【分章大纲】部分，这是每个章节最细粒度的内容分配。

### 第二步：建立章节内容映射
为每个章节建立明确的内容归属，例如：

| 章节范围 | 本章专属内容 |
|---------|------------|
| 第1-10章 | 主角初入江湖，结识伙伴 |
| 第11-30章 | 江湖历练，逐渐成长 |
| 第91-98章 | 战前部署，各方势力集结 |
| 第99-100章 | 平播之战一触即发。第一部完。 |

### 第三步：逐章细化原则
- 每一章只展开其编号范围内分章大纲分配的内容
- 第98章只写到"战前准备完毕，即将开战"为止
- 第99章开始才展开平播之战的实际过程
- 如果分章大纲中某个事件在第50章才出现，在第30章时仅为该事件做铺垫和伏笔

### 核心创作原则
你的创造性体现在**如何写**（场景描写、对话设计、情感渲染），而非**写什么**（事件、角色、结果——这些由分章大纲决定）。

---

# 全局大纲（请据此创作）

"""
            
            # 前置边界约束
            filled_prompt = boundary_constraint + filled_prompt
            
            # 添加章节范围指引（v4.0正向版）
            filled_prompt += f"""

---

## 章节范围指引

### 当前任务
- **本次任务**：生成第1-{unit_count}{unit_label}的概述（第1批）
- **后续批次**：第{unit_count + 1}{unit_label}及之后会在后续批次中生成

### 生成规则
1. 从第1{unit_label}开始，按顺序逐章生成到第{unit_count}{unit_label}
2. 恰好生成{unit_count}个章节，编号连续：1, 2, 3, ..., {unit_count}
3. 后续章节的内容将留到对应批次再详细展开

### 内容分配原则
- 根据全局大纲中第1-{unit_count}{unit_label}的情节分配逐一展开
- 每个章节只展开其编号范围内分章大纲分配的内容
- 严格按照分章大纲中的时间线和事件顺序展开
- 为后续章节留下合理的发展空间

### 逐章细化指南（核心）

你的任务是**将分章大纲细化为详细的章节概述**，以下原则帮助你在正确的范围内创作：

1. **忠于大纲内容**
   - 分章大纲中已列出的事件，你负责细化、展开和丰富
   - 分章大纲中的人物、地点、事件走向均已确定，你负责将它们写得更生动

2. **尊重内容归属**
   - 每个章节只涵盖其编号范围内分章大纲分配的内容
   - 例如：分章大纲中"第99-100章：平播之战一触即发"意味着第98章写到"战前准备完毕"即可
   - 例如：分章大纲中某个事件在第50章才出现，在第5章时只需为该事件做铺垫

3. **创造性范围**
   - 你可以发挥创造力的地方：场景如何描写、对话如何设计、情感如何渲染
   - 由分章大纲决定的地方：发生什么事件、谁参与、事件的结果

4. **逐章自查指南**
   - 本章的编号范围在分章大纲中对应什么内容？
   - 我写的内容是否恰好覆盖了这些内容？
   - 下一章将展开的事件，本章是否做好了合理的铺垫和过渡？

### 输出格式
```
第1章 [章节标题]
梗概：[本章情节概述]
...

第2章 [章节标题]
梗概：[本章情节概述]
...

（继续直到第{unit_count}章）
```
"""

            # 添加日志验证（v2.3）
            self.logger.info(f"[单元概述-非流式] 提示词长度: {len(filled_prompt)} 字符")
            self.logger.info(f"[单元概述-非流式] 是否包含章节边界识别: {'章节边界识别' in filled_prompt}")
            self.logger.info(f"[单元概述-非流式] 全局大纲长度: {len(global_outline)} 字符")

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


