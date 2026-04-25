"""大纲生成器 - 单单元接续与质量验证Mixin"""
from typing import Dict
from typing import List
from typing import Any
import re


class UnitSummarySingleMixin:
    """单单元接续与质量验证"""

    async def _continue_single_unit(
        self,
        global_outline: str,
        unit_num: int,
        truncated_content: str,
        content_type: str,
        llm_provider,
        temperature: float = 0.7
    ) -> str:
        """
        接续单个不完整的单元

        Args:
            global_outline: 全局大纲
            unit_num: 单元号
            truncated_content: 被截断的内容
            content_type: 内容类型
            llm_provider: LLM提供者
            temperature: 温度参数

        Returns:
            接续后的完整内容
        """
        try:
            # 分析截断位置
            lines = truncated_content.strip().split('\n')
            last_line = lines[-1] if lines else ""

            # 提取已有信息
            title = ""
            summary_so_far = ""

            if content_type == "novel":
                # 提取标题
                for line in lines:
                    if line.strip().startswith("### 第"):
                        title_match = re.search(r'### 第\d+章[：:]\s*(.+)', line)
                        if title_match:
                            title = title_match.group(1).strip()
                            break

                # 提取已有梗概
                summary_start = -1
                for i, line in enumerate(lines):
                    if "**本章梗概**" in line or "本章梗概：" in line:
                        summary_start = i
                        break

                if summary_start >= 0:
                    summary_so_far = '\n'.join(lines[summary_start:])
            else:
                # 剧本类似
                for line in lines:
                    if line.strip().startswith("**第"):
                        title_match = re.search(
                            r'\*\*第\d+[集场][：:]\s*\*\*(.+?)\*\*', line)
                        if title_match:
                            title = title_match.group(1).strip()
                            break

                summary_start = -1
                for i, line in enumerate(lines):
                    if "**本集梗概**" in line or "本集梗概：" in line:
                        summary_start = i
                        break
                    if "**本场梗概**" in line or "本场梗概：" in line:
                        summary_start = i
                        break

                if summary_start >= 0:
                    summary_so_far = '\n'.join(lines[summary_start:])

            unit_label = "章" if content_type == "novel" else (
                "集" if content_type == "series_script" else "场")

            prompt = f"""你是专业的创意写作顾问。

## 任务
第{unit_num}{unit_label}的概述被截断,请根据已有内容接续完成。

## 全局大纲(参考故事结构)
{global_outline[:1000]}

## 已有内容(从断点处接续)
{truncated_content}

## 截断分析
- 最后一行: "{last_line}"
- 问题: 内容不完整,需要补充完整

## 接续要求
1. 从断点处自然接续,不要重复已有内容
2. 保持与前文的情节连贯性
3. 遵循全局大纲的故事结构
4. 确保接续后内容完整(包含所有必要字段)
5. 梗概内容应达到200-300字

## 输出格式
请只输出接续部分,不要包含已有的内容。
"""

            response = await llm_provider.generate(
                prompt=prompt,
                temperature=temperature
            )

            continued_part = response.content if hasattr(
                response, 'content') else str(response)

            # 合并已有内容和接续部分
            full_content = truncated_content + "\n" + continued_part

            return full_content

        except Exception as e:
            self.logger.error(f"[接续生成] 接续第{unit_num}单元失败: {str(e)}")
            return ""


    async def _validate_continuation_quality(
        self,
        original_parsed: Dict[str, Dict[str, Any]],
        continued_content: str,
        content_type: str,
        continued_units: List[int]
    ) -> Dict[str, Any]:
        """
        验证接续生成的质量

        Args:
            original_parsed: 原始解析结果
            continued_content: 接续后的内容
            content_type: 内容类型
            continued_units: 接续的单元号列表

        Returns:
            {
                "passed": bool,
                "issues": List[str],
                "metrics": Dict
            }
        """
        result = {
            "passed": True,
            "issues": [],
            "metrics": {}
        }

        try:
            # 防御性检查:验证continued_units有效性
            if continued_units and any(u < 1 for u in continued_units):
                result["issues"].append(f"接续单元号包含无效值: {continued_units}")
                result["passed"] = False
                return result

            # 重新解析接续后的内容
            expected_count = len(original_parsed)
            if continued_units:
                expected_count = max(expected_count, max(continued_units))

            new_parsed = self.parse_unit_summaries(
                continued_content,
                expected_count,
                content_type
            )

            if not new_parsed:
                result["passed"] = False
                result["issues"].append("接续后无法解析内容")
                return result

            # 验证1: 单元数量检查
            expected_count = max(len(original_parsed), len(new_parsed))
            if len(new_parsed) < expected_count:
                result["issues"].append(
                    f"单元数量不足: 预期{expected_count},实际{len(new_parsed)}")
                result["passed"] = False

            # 验证2: 接续单元完整性检查
            for unit_num in continued_units:
                unit_data = new_parsed.get(str(unit_num))
                if not unit_data:
                    result["issues"].append(f"第{unit_num}单元解析失败")
                    result["passed"] = False
                    continue

                # 检查必要字段
                full_content = unit_data.get("full_content", "")
                title = unit_data.get("title", "")
                summary = unit_data.get("summary", "")

                if not title:
                    result["issues"].append(f"第{unit_num}单元缺少标题")
                    result["passed"] = False

                if not summary or len(summary) < 50:
                    result["issues"].append(
                        f"第{unit_num}单元梗概过短({len(summary)}字)")
                    result["passed"] = False

                # 检查结构完整性
                if content_type == "novel":
                    if "**本章梗概**" not in full_content and "本章梗概：" not in full_content:
                        result["issues"].append(f"第{unit_num}单元缺少梗概字段")
                        result["passed"] = False
                else:
                    if "**本集梗概**" not in full_content and "本集梗概：" not in full_content:
                        if "**本场梗概**" not in full_content and "本场梗概：" not in full_content:
                            result["issues"].append(f"第{unit_num}单元缺少梗概字段")
                            result["passed"] = False

            # 验证3: 内容连贯性检查(启发式)
            # 检查接续单元与前序单元的主题连贯性
            sorted_units = sorted(new_parsed.items(), key=lambda x: int(x[0]))
            for i, (unit_num, unit_data) in enumerate(sorted_units):
                if int(unit_num) in continued_units and i > 0:
                    prev_unit = sorted_units[i-1][1]
                    prev_summary = prev_unit.get("summary", "")
                    curr_summary = unit_data.get("summary", "")

                    # 简单检查:如果梗概完全相同,可能有问题
                    if prev_summary and curr_summary and prev_summary == curr_summary:
                        result["issues"].append(f"第{unit_num}单元梗概与前序单元重复")
                        result["passed"] = False

            # 记录指标
            result["metrics"] = {
                "total_units": len(new_parsed),
                "continued_units_count": len(continued_units),
                "avg_summary_length": sum(
                    len(u.get("summary", "")) for u in new_parsed.values()
                ) / len(new_parsed) if new_parsed else 0
            }

        except Exception as e:
            self.logger.error(f"[接续生成] 质量验证失败: {str(e)}")
            result["passed"] = False
            result["issues"].append(f"质量验证异常: {str(e)}")

        return result


