"""
content_pipeline - 全局大纲对齐验证模块

每N个单元触发一次，对比全局大纲中的关键情节点与已生成内容，
检测遗漏、新增、重大偏离。

@date: 2026-05-22
@version: v1.0.0
"""

from typing import Any, Dict, List, Optional


async def check_outline_alignment(
    global_outline: str,
    generated_summaries: List[str],
    llm_provider=None,
    interval: int = 5,
    logger=None
) -> Optional[str]:
    """轻量全局大纲对齐检查

    每 interval 个单元触发一次，使用LLM对比大纲关键事件与已生成内容。

    Args:
        global_outline: 全局大纲文本（或 global_context）
        generated_summaries: 已生成各单元的摘要列表
        llm_provider: LLM提供者实例（可选，无则返回None）
        interval: 触发间隔（每N个单元）
        logger: 日志记录器

    Returns:
        对齐报告文本，如果无需检查或LLM不可用则返回 None
    """
    if not llm_provider or not global_outline or not generated_summaries:
        return None

    if len(generated_summaries) % interval != 0:
        return None

    if logger:
        logger.info(f"[大纲对齐] 触发对齐检查: 已生成{len(generated_summaries)}个单元")

    # 构建提示词
    summaries_text = "\n---\n".join(
        generated_summaries[-interval:]  # 仅检查最近 interval 个单元
    )
    outline_excerpt = global_outline[:3000]  # 截断大纲以避免超token

    prompt = f"""你是大纲一致性检查器。请对比以下全局大纲与已生成内容，检测偏离情况。

## 全局大纲（关键情节点）
{outline_excerpt}

## 已生成内容摘要（最近{interval}个单元）
{summaries_text}

## 请输出如下格式的对齐报告（中文）：

### 已覆盖的规划事件
列出大纲中规划、且在生成内容中已体现的事件。

### 遗漏的规划事件
列出大纲中规划、但生成内容中未涉及的事件（如有）。

### 新增的非规划内容
列出生成内容中出现、但大纲中未规划的重要事件或转折（如有）。

### 重大偏离
列出生成内容与大纲方向明显不符的偏离（如有）。

### 总体评价
1-2句话总结大纲对齐程度。

**若无任何偏离，请仅输出"对齐检查通过：已生成内容与全局大纲一致，无遗漏或偏离。"**"""

    try:
        llm_response = await llm_provider.generate(prompt)
        report = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

        # 清理报告
        report = report.strip()
        if len(report) > 1500:
            report = report[:1500] + "\n\n...(报告过长已截断)"

        if logger:
            has_issues = any(kw in report for kw in ["遗漏", "偏离", "不一致", "未覆盖", "新增的非规划"])
            if has_issues:
                logger.warning(f"[大纲对齐] 检测到偏离: {report[:200]}...")
            else:
                logger.info(f"[大纲对齐] 对齐检查通过")

        return report

    except Exception as e:
        if logger:
            logger.warning(f"[大纲对齐] LLM调用失败: {e}")
        return None
