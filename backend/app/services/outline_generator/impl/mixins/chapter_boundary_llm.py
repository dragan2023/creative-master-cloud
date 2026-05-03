"""大纲生成器 - LLM语义边界验证器Mixin

核心创新：用LLM语义理解替代关键词匹配做边界验证。

设计原则：
- 两级验证链：关键词预筛选（快速通路）→ LLM语义验证（精准判断）
- 轻量级LLM调用：短prompt，低temperature=0.1，极简输出格式
- 结构化输出：便于程序化解析和决策
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any


@dataclass
class SemanticValidationResult:
    """LLM语义验证结果"""
    passed: bool = True                   # 是否通过验证（默认通过）
    keyword_prefilter_passed: bool = True  # 关键词预筛选是否通过
    llm_validated: bool = False            # 是否执行了LLM验证
    violations: List[str] = field(default_factory=list)
    confidence: float = 1.0                # 置信度 0.0-1.0
    suggestion: str = ""                   # 修正建议


class SemanticBoundaryValidatorMixin:
    """LLM语义边界验证器

    两级验证链：
    1. 关键词预筛选：快速排除明显合规的章节（<1ms，无LLM调用）
    2. LLM语义验证：只有关键词预筛选发现疑似越界时才触发（~1-2s）
    """

    # ==================== 配置常量 ====================
    SEMANTIC_VALIDATION_TEMPERATURE = 0.1  # 极低温度，确保确定性判断
    KEYWORD_PREFILTER_MIN_MATCHES = 2      # 关键词预筛选：最少重叠词数才触发LLM验证

    async def validate_boundary_semantic(
        self,
        chapter_content: str,
        chapter_num: int,
        boundary_map: Dict[int, str],
        llm_provider=None,
        unit_label: str = "章",
    ) -> SemanticValidationResult:
        """语义边界验证（两级验证链）

        Args:
            chapter_content: 本章生成的内容
            chapter_num: 本章编号
            boundary_map: 所有章节的边界映射 {ch_num: boundary_desc}
            llm_provider: LLM提供者实例
            unit_label: 单元标签

        Returns:
            SemanticValidationResult
        """
        result = SemanticValidationResult()

        if not chapter_content or len(chapter_content.strip()) < 50:
            result.passed = True
            return result

        # ===== 第一级：关键词预筛选 =====
        keyword_violations = self._keyword_prefilter(
            chapter_content=chapter_content,
            chapter_num=chapter_num,
            boundary_map=boundary_map,
            unit_label=unit_label,
        )

        if not keyword_violations:
            result.passed = True
            result.keyword_prefilter_passed = True
            return result

        # 关键词预筛选发现疑似越界
        result.keyword_prefilter_passed = False

        # ===== 第二级：LLM语义验证 =====
        if not llm_provider:
            # 无LLM提供者，回退到关键词结果（保守策略：放行但标记警告）
            result.passed = True
            result.violations = [
                f"关键词预筛选发现疑似越界(无LLM验证): {v[:80]}" for v in keyword_violations
            ]
            result.confidence = 0.3
            return result

        try:
            result.llm_validated = True
            llm_result = await self._llm_semantic_check(
                chapter_content=chapter_content,
                chapter_num=chapter_num,
                boundary_map=boundary_map,
                keyword_violations=keyword_violations,
                llm_provider=llm_provider,
                unit_label=unit_label,
            )

            result.passed = llm_result.get("passed", True)
            result.violations = llm_result.get("violations", [])
            result.confidence = llm_result.get("confidence", 0.8)
            result.suggestion = llm_result.get("suggestion", "")

            self.logger.info(
                f"[语义边界] 第{chapter_num}{unit_label}: "
                f"通过={result.passed}, 置信度={result.confidence:.2f}, "
                f"违规={len(result.violations)}处"
            )

        except Exception as e:
            self.logger.error(f"[语义边界] LLM验证失败: {e!r}")
            # 失败时保守处理：默认放行
            result.passed = True
            result.confidence = 0.2
            result.violations = [
                f"LLM验证异常，关键词预筛选发现: {v[:80]}" for v in keyword_violations
            ]

        return result

    # ==================== 内部方法 ====================

    def _keyword_prefilter(
        self,
        chapter_content: str,
        chapter_num: int,
        boundary_map: Dict[int, str],
        unit_label: str = "章",
    ) -> List[str]:
        """关键词预筛选：快速检测疑似越界

        返回疑似越界的描述列表，空列表表示完全合规
        """
        # 提取本章内容关键词
        chapter_kw = self._extract_key_events(chapter_content)

        # 提取后续章节边界的专属关键词
        max_chapter = max(boundary_map.keys()) if boundary_map else chapter_num
        violations = []

        for future_ch in range(chapter_num + 1, min(chapter_num + 6, max_chapter + 1)):
            if future_ch not in boundary_map:
                continue
            future_boundary = boundary_map[future_ch]
            future_kw = self._extract_key_events(future_boundary)
            if not future_kw:
                continue

            # 过滤过于通用的词（<4字）
            specific_kw = {kw for kw in future_kw if len(kw) >= 4}
            overlaps = chapter_kw & specific_kw

            if len(overlaps) >= self.KEYWORD_PREFILTER_MIN_MATCHES:
                violations.append(
                    f"第{future_ch}{unit_label}专属: {', '.join(sorted(overlaps)[:5])}"
                )

        return violations

    async def _llm_semantic_check(
        self,
        chapter_content: str,
        chapter_num: int,
        boundary_map: Dict[int, str],
        keyword_violations: List[str],
        llm_provider,
        unit_label: str = "章",
    ) -> Dict[str, Any]:
        """使用LLM进行语义边界验证

        核心策略：给LLM提供当前章节内容 + 当前章节边界 + 下一章边界，
        询问"本章内容是否包含了下一章才应该出现的剧情元素？"
        """
        # 构建本章边界描述
        own_boundary = boundary_map.get(
            chapter_num, f"第{chapter_num}{unit_label}内容"
        )

        # 构建下一章边界描述（最多取2章）
        next_boundaries = []
        for future_ch in range(chapter_num + 1, min(chapter_num + 3, max(boundary_map.keys()) + 1)):
            if future_ch in boundary_map:
                next_boundaries.append(
                    f"第{future_ch}{unit_label}: {boundary_map[future_ch]}"
                )

        next_boundary_text = "\n".join(
            next_boundaries) if next_boundaries else "（无后续章节信息）"

        # 截断内容以避免token超限
        content_snippet = chapter_content[:1200] if len(
            chapter_content) > 1200 else chapter_content

        prompt = f"""你是专业的小说结构审核专家。请严格判断以下章节内容是否越界。

## 第{chapter_num}{unit_label}的专属内容范围
{own_boundary}

## 后续章节的内容范围（绝对不应出现在本章）
{next_boundary_text}

## 第{chapter_num}{unit_label}的实际内容（需要判断）
{content_snippet}

## 判断任务
上面是第{chapter_num}{unit_label}的实际内容。请判断：
**本章内容是否包含了后续章节才应该出现的剧情元素？**

注意：
- 如果本章只是为后续章节的剧情做了铺垫或伏笔，这不算越界
- 只有本章实实在在地发生了后续章节专属的事件，才算越界
- 例如：本章写"杨应龙兵败自焚"，但"兵败自焚"在第99章的专属范围内 → 越界
- 例如：本章写"主角决定去参加武林大会"，但武林大会本身在第15章 → 不算越界（只是提及/铺垫）

## 输出格式
仅输出一行JSON，不要任何额外文字：
{{"passed":true,"violations":[],"confidence":0.95,"suggestion":""}}

如果发现越界：
{{"passed":false,"violations":["具体越界内容描述"],"confidence":0.85,"suggestion":"修正建议"}}"""

        try:
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=self.SEMANTIC_VALIDATION_TEMPERATURE,
            )

            response_text = response.content if hasattr(
                response, 'content') else str(response)

            # 解析JSON响应
            import json
            import re

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                return json.loads(json_match.group(0))

            self.logger.warning(
                f"[语义边界] LLM返回非JSON格式: {response_text[:100]}")
            return {"passed": True, "violations": [], "confidence": 0.5,
                    "suggestion": ""}

        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"[语义边界] JSON解析失败: {e!r}")
            return {"passed": True, "violations": [], "confidence": 0.4,
                    "suggestion": ""}
