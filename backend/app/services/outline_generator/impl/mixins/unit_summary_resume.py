"""大纲生成器 - 单元概述续生成与缺失单元补全Mixin"""
from typing import Dict
from typing import List
from typing import Any
import re


class UnitSummaryResumeMixin:
    """单元概述续生成与缺失单元补全"""

    async def continue_unit_summaries_generation(
        self,
        global_outline: str,
        existing_content: str,
        existing_parsed: Dict[str, Dict[str, Any]],
        truncation_info: Dict[str, Any],
        content_type: str,
        llm_provider,
        temperature: float = 0.3,  # 降低到0.3，减少创造性，增强遵循性（v2.5）
    ) -> Dict[str, Any]:
        """
        接续生成被截断或缺失的单元概述

        Args:
            global_outline: 全局大纲内容
            existing_content: 已生成的内容
            existing_parsed: 已解析的单元概述
            truncation_info: 截断检测信息
            content_type: 内容类型
            llm_provider: LLM提供者
            temperature: 温度参数

        Returns:
            {
                "success": bool,
                "continued_content": str,
                "continued_parsed": Dict,
                "continued_units": List[int]
            }
        """
        result = {
            "success": False,
            "continued_content": existing_content,
            "continued_parsed": existing_parsed,
            "continued_units": [],
            "error": None,
            "history": []  # 新增:接续历史记录
        }

        try:
            missing_units = truncation_info.get("missing_units", [])
            truncated_units = truncation_info.get("truncated_units", [])

            if not missing_units and not truncated_units:
                result["success"] = True
                return result

            self.logger.info(
                f"[接续生成] 开始接续{len(missing_units)}个缺失单元, "
                f"{len(truncated_units)}个不完整单元"
            )

            # 1. 生成缺失的单元
            if missing_units:
                # 记录接续历史(新增)
                result["history"].append({
                    "type": "generate_missing",
                    "units": missing_units,
                    "count": len(missing_units),
                    "timestamp": "now"
                })

                missing_content = await self._generate_missing_units(
                    global_outline=global_outline,
                    existing_parsed=existing_parsed,
                    missing_units=missing_units,
                    content_type=content_type,
                    llm_provider=llm_provider,
                    temperature=temperature
                )

                if missing_content:
                    existing_content += "\n\n" + missing_content
                    result["continued_units"].extend(missing_units)
                    self.logger.info(f"[接续生成] 缺失单元生成完成: {missing_units}")

            # 2. 接续不完整的单元(新增)
            if truncated_units:
                for unit_num in truncated_units:
                    unit_data = existing_parsed.get(str(unit_num))
                    if unit_data:
                        original_content = unit_data.get("full_content", "")

                        continued_unit = await self._continue_single_unit(
                            global_outline=global_outline,
                            unit_num=unit_num,
                            truncated_content=original_content,
                            content_type=content_type,
                            llm_provider=llm_provider,
                            temperature=temperature
                        )

                        if continued_unit:
                            # 记录接续历史(新增)
                            result["history"].append({
                                "unit_num": unit_num,
                                "type": "continue_single",
                                "original_length": len(original_content),
                                "continued_length": len(continued_unit),
                                "timestamp": "now"
                            })

                            # 安全替换原有内容(修复:防止空字符串误替换)
                            if original_content and original_content in existing_content:
                                existing_content = existing_content.replace(
                                    original_content,
                                    continued_unit,
                                    1  # 只替换第一次出现
                                )
                                result["continued_units"].append(unit_num)
                                self.logger.info(f"[接续生成] 第{unit_num}单元接续完成")
                            else:
                                self.logger.warning(
                                    f"[接续生成] 第{unit_num}单元原始内容为空或未找到,跳过替换"
                                )

            # 3. 质量验证(新增)
            quality_check = await self._validate_continuation_quality(
                original_parsed=existing_parsed,
                continued_content=existing_content,
                content_type=content_type,
                continued_units=result["continued_units"]
            )

            result["quality_validation"] = quality_check

            if not quality_check["passed"]:
                self.logger.warning(
                    f"[接续生成] 质量验证未通过: {quality_check['issues']}")
                # 不阻断流程,仅记录警告

            # 4. 重新解析合并后的内容
            expected_unit_count = len(original_parsed)
            if result["continued_units"]:
                expected_unit_count = max(
                    expected_unit_count, max(result["continued_units"]))

            new_parsed = self.parse_unit_summaries(
                continued_content, expected_unit_count, content_type
            )

            if new_parsed and len(new_parsed) >= len(existing_parsed):
                result["success"] = True
                result["continued_content"] = existing_content
                result["continued_parsed"] = new_parsed

                self.logger.info(
                    f"[接续生成] 完成: 原{len(existing_parsed)}个单元 → "
                    f"新{len(new_parsed)}个单元"
                )
            else:
                result["error"] = "接续后重新解析失败"
                self.logger.error(f"[接续生成] {result['error']}")

        except Exception as e:
            self.logger.error(f"[接续生成] 失败: {str(e)}")
            result["error"] = str(e)

        return result


    async def _generate_missing_units(
        self,
        global_outline: str,
        existing_parsed: Dict[str, Dict[str, Any]],
        missing_units: List[int],
        content_type: str,
        llm_provider,
        temperature: float = 0.3,  # 降低到0.3，减少创造性，增强遵循性（v2.5）
        max_batch_size: int = 20  # 新增:批量大小限制
    ) -> str:
        """
        生成缺失的单元概述(支持批量优化和智能重试)

        Args:
            global_outline: 全局大纲
            existing_parsed: 已存在的单元概述
            missing_units: 缺失的单元号列表
            content_type: 内容类型
            llm_provider: LLM提供者
            temperature: 温度参数
            max_batch_size: 每批最大生成单元数(默认20)

        Returns:
            新生成的单元概述内容
        """
        all_content = []

        # 创建副本避免修改原对象(修复:防止副作用)
        working_parsed = {k: v for k, v in existing_parsed.items()}

        try:
            # 批量优化:如果缺失单元超过max_batch_size,分批生成
            if len(missing_units) > max_batch_size:
                self.logger.info(
                    f"[批量接续] 缺失单元{len(missing_units)}个,超过阈值{max_batch_size},开始分批生成"
                )

                # 分批处理
                batches = [
                    missing_units[i:i+max_batch_size]
                    for i in range(0, len(missing_units), max_batch_size)
                ]

                for batch_idx, batch_units in enumerate(batches, 1):
                    self.logger.info(
                        f"[批量接续] 处理第{batch_idx}/{len(batches)}批: {batch_units[0]}-{batch_units[-1]}"
                    )

                    # 智能重试:每批最多重试3次
                    batch_content = None
                    max_retries = 3

                    for retry in range(max_retries):
                        try:
                            batch_content = await self._generate_units_batch(
                                global_outline=global_outline,
                                existing_parsed=existing_parsed,
                                missing_units=batch_units,
                                content_type=content_type,
                                llm_provider=llm_provider,
                                temperature=temperature
                            )

                            if batch_content and len(batch_content) > 100:
                                # 验证生成质量
                                if "**" in batch_content or "梗概" in batch_content:
                                    self.logger.info(
                                        f"[批量接续] 第{batch_idx}批生成成功(尝试{retry+1}/{max_retries})"
                                    )
                                    break
                                else:
                                    self.logger.warning(
                                        f"[批量接续] 第{batch_idx}批内容格式异常,重试..."
                                    )
                            else:
                                self.logger.warning(
                                    f"[批量接续] 第{batch_idx}批内容为空或过短,重试..."
                                )

                        except Exception as e:
                            self.logger.error(
                                f"[批量接续] 第{batch_idx}批生成异常(尝试{retry+1}/{max_retries}): {str(e)}"
                            )

                        # 重试前等待(指数退避)
                        if retry < max_retries - 1:
                            import asyncio
                            wait_time = 2 ** retry  # 1s, 2s, 4s
                            self.logger.info(f"[批量接续] 等待{wait_time}秒后重试...")
                            await asyncio.sleep(wait_time)

                    if batch_content:
                        all_content.append(batch_content)

                        # 更新working_parsed用于下一批的参考(使用副本)
                        temp_content = "\n\n".join(all_content)
                        temp_parsed = self.parse_unit_summaries(
                            temp_content, len(all_content), content_type
                        )
                        if temp_parsed:
                            working_parsed.update(temp_parsed)
                    else:
                        self.logger.error(
                            f"[批量接续] 第{batch_idx}批生成失败,跳过"
                        )
            else:
                # 少量单元,直接生成(带重试)
                max_retries = 3

                for retry in range(max_retries):
                    try:
                        content = await self._generate_units_batch(
                            global_outline=global_outline,
                            existing_parsed=existing_parsed,
                            missing_units=missing_units,
                            content_type=content_type,
                            llm_provider=llm_provider,
                            temperature=temperature
                        )

                        if content and len(content) > 100:
                            if "**" in content or "梗概" in content:
                                self.logger.info(
                                    f"[接续生成] 生成成功(尝试{retry+1}/{max_retries})"
                                )
                                all_content.append(content)
                                break
                            else:
                                self.logger.warning(
                                    f"[接续生成] 内容格式异常,重试..."
                                )
                        else:
                            self.logger.warning(
                                f"[接续生成] 内容为空或过短,重试..."
                            )

                    except Exception as e:
                        self.logger.error(
                            f"[接续生成] 生成异常(尝试{retry+1}/{max_retries}): {str(e)}"
                        )

                    # 重试前等待(指数退避)
                    if retry < max_retries - 1:
                        import asyncio
                        wait_time = 2 ** retry  # 1s, 2s, 4s
                        self.logger.info(f"[接续生成] 等待{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)

            return "\n\n".join(all_content) if all_content else ""

        except Exception as e:
            self.logger.error(f"[接续生成] 生成缺失单元失败: {str(e)}")
            return ""


    async def _generate_units_batch(
        self,
        global_outline: str,
        existing_parsed: Dict[str, Dict[str, Any]],
        missing_units: List[int],
        content_type: str,
        llm_provider,
        temperature: float = 0.3,  # 降低到0.3，减少创造性，增强遵循性（v2.5）
    ) -> str:
        """
        生成一批单元概述(内部方法,不含重试逻辑)
        """
        try:
            # 获取前序单元作为参考
            previous_units_text = self._build_previous_units_reference(
                existing_parsed, content_type, max_units=5
            )

            start_num = min(missing_units)
            end_num = max(missing_units)
            # 统一使用content_type判断(修复:与_continue_single_unit保持一致)
            # [2026-05-05] 修复：补全 movie_outline/series_outline 映射
            unit_label = {"novel": "章", "series_script": "集", "movie_script": "场",
                         "movie_outline": "场", "series_outline": "集"}.get(content_type, "章")

            prompt = f"""你是专业的创意写作顾问。

## 任务
以下单元概述缺失,请根据全局大纲和已生成的前序单元,生成这些单元的概述。

## 全局大纲(参考故事结构)
{global_outline[:1500]}

## 已生成的前序单元(参考情节连贯性)
{previous_units_text}

## 需要生成的单元
- 第{start_num}{unit_label} 至 第{end_num}{unit_label}

## 生成要求
1. 保持与前序单元的情节连贯性
2. 遵循全局大纲的故事结构
3. 确保每个单元的概述完整(包含标题、梗概等)
4. 严格按照以下格式输出:

"""

            if content_type == "novel":
                prompt += """### 第X章：[章节标题]
**本章梗概**：[概述内容，200-300字]

"""
            else:
                # [2026-05-05] 修复：根据 content_type 使用正确的单元标签和梗概标签
                summary_label = "本集" if content_type in ("series_script", "series_outline") else "本场"
                prompt += f"""**第X{unit_label}**：[{unit_label}标题]
**{summary_label}梗概**：[概述内容，200-300字]

"""

            prompt += f"""
## 开始生成
请从第{start_num}{unit_label}开始生成,一直到第{end_num}{unit_label}。
"""

            response = await llm_provider.generate(
                prompt=prompt,
                temperature=temperature
            )

            content = response.content if hasattr(
                response, 'content') else str(response)
            return content

        except Exception as e:
            self.logger.error(f"[接续生成] 生成缺失单元失败: {str(e)}")
            return ""


    def _build_previous_units_reference(
        self,
        parsed: Dict[str, Dict[str, Any]],
        content_type: str,
        max_units: int = 5
    ) -> str:
        """
        构建前序单元的参考文本

        Args:
            parsed: 单元概述字典
            content_type: 内容类型
            max_units: 最多包含的单元数

        Returns:
            前序单元参考文本
        """
        units_text = []
        # [2026-05-05] 修复：补全 movie_outline/series_outline 映射
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场",
                     "movie_outline": "场", "series_outline": "集"}.get(content_type, "章")

        # 获取最后max_units个单元
        sorted_units = sorted(parsed.items(), key=lambda x: int(x[0]))
        recent_units = sorted_units[-max_units:] if len(
            sorted_units) > max_units else sorted_units

        for unit_num, unit_data in recent_units:
            title = unit_data.get("title", "")
            summary = unit_data.get("summary", "")

            units_text.append(
                f"第{unit_num}{unit_label}《{title}》：{summary[:150]}")

        return "\n".join(units_text) if units_text else "（无前序单元）"


