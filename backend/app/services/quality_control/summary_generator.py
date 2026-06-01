"""
章节摘要自动生成器

在章节正文生成完成后，调用 LLM 生成 150-300 字的章节摘要，
存储到 NovelChapter.chapter_metadata["auto_summary"]，
供质控分析的 ±N 章上下文机制使用。

设计原则：
- 轻量 LLM 调用（低温度 + 短输出）
- 失败不阻塞主流程（摘要生成失败仅记录日志，不影响章节保存）
- 摘要强调"实际发生了什么"，而非大纲"计划发生什么"

@date: 2026-05-22
@version: v1.0.0
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.novel_chapter import NovelChapter

logger = logging.getLogger("quality_control.summary_generator")

# 摘要生成的提示词模板
CHAPTER_SUMMARY_PROMPT = """请为以下小说章节生成一个简洁的摘要（150-300字）。

要求：
1. 只描述本章**实际发生**的关键事件和情节转折
2. 包含主要人物的关键行动和状态变化
3. 语言精炼，不添加评价性语句
4. 直接输出摘要文本，不要任何前缀或标签

章节内容（前2000字）：
{content_preview}

章节摘要："""


async def generate_and_store_chapter_summary(
    db: AsyncSession,
    chapter_id: int,
    chapter_content: str,
    llm_provider=None,
    user_id: Optional[int] = None,
) -> Optional[str]:
    """为指定章节生成 LLM 摘要并存储到 chapter_metadata.auto_summary。

    此函数设计为异步非阻塞调用，失败时仅记录日志，不抛出异常。

    Args:
        db: 数据库会话
        chapter_id: NovelChapter 的主键 ID
        chapter_content: 章节正文内容
        llm_provider: 可选的 LLM 提供者（如未传入，尝试从 DB 或系统预置获取）
        user_id: 用户ID（优先从 DB 获取用户配置的 API Key）

    Returns:
        生成的摘要文本，失败返回 None
    """
    if not chapter_content or not chapter_content.strip():
        logger.warning(f"[摘要生成] 章节内容为空，跳过: chapter_id={chapter_id}")
        return None

    # 获取 LLM 提供者
    if llm_provider is None:
        try:
            from app.agents.llm_manager import get_llm_manager
            llm_mgr = get_llm_manager()
            # 优先使用用户 DB 中配置的 API Key
            if user_id is not None:
                try:
                    llm_provider = await llm_mgr.get_provider_from_db(db, user_id)
                    if llm_provider:
                        logger.info(f"[摘要生成] 使用用户 DB 配置的 LLM 提供者: user_id={user_id}")
                except Exception:
                    pass
            # 回退：按优先级尝试多个系统预置提供者
            if llm_provider is None:
                default_providers = ["qianwen", "doubao", "siliconflow", "t8star"]
                for provider_name in default_providers:
                    try:
                        llm_provider = await llm_mgr.get_system_provider(provider_name)
                        if llm_provider:
                            logger.info(f"[摘要生成] 使用系统预置 LLM 提供者: {provider_name}")
                            break
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"[摘要生成] 获取 LLM 提供者失败: {e}")
            return None

    if llm_provider is None:
        logger.warning("[摘要生成] 无可用的 LLM 提供者，跳过")
        return None

    # 截取前 2000 字作为 LLM 输入（足够生成摘要，同时控制 token 消耗）
    content_preview = chapter_content[:2000] if len(chapter_content) > 2000 else chapter_content

    prompt = CHAPTER_SUMMARY_PROMPT.format(content_preview=content_preview)

    try:
        response = await llm_provider.generate(
            prompt=prompt,
            temperature=0.2,
            module_name="chapter_summary_generator"
        )
        summary = response.content if hasattr(response, 'content') else str(response)
        summary = summary.strip()

        # 验证摘要质量（字数控制由提示词完成，不强行截断）
        if len(summary) < 50:
            logger.warning(
                f"[摘要生成] 生成的摘要过短({len(summary)}字)，可能质量不佳: chapter_id={chapter_id}"
            )
            return None

    except Exception as e:
        logger.error(f"[摘要生成] LLM 调用失败: chapter_id={chapter_id}, error={e!r}")
        return None

    # 存储到 chapter_metadata.auto_summary
    try:
        query = select(NovelChapter).where(NovelChapter.id == chapter_id)
        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            logger.warning(f"[摘要生成] 章节不存在: chapter_id={chapter_id}")
            return None

        metadata = chapter.chapter_metadata or {}
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata)
        metadata["auto_summary"] = summary
        chapter.chapter_metadata = metadata
        await db.commit()

        logger.info(
            f"[摘要生成] 摘要已存储: chapter_id={chapter_id}, "
            f"chapter_number={chapter.chapter_number}, "
            f"summary_length={len(summary)}"
        )
        return summary

    except Exception as e:
        logger.error(f"[摘要生成] 存储摘要失败: chapter_id={chapter_id}, error={e!r}")
        await db.rollback()
        return None
