"""
NovelChapter 数据同步服务

提供 WritingUnit → NovelChapter 的统一同步入口。
原则：NovelChapter 必须永远存在，不存在时自动创建。

@date: 2026-05-08
@version: v1.0.0
"""
import logging
from typing import Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.novel_chapter import NovelChapter, ChapterStatus

# 模块级默认 logger
_default_logger = logging.getLogger(__name__)


async def sync_writing_unit_to_novel_chapter(
    db: AsyncSession,
    project_id: int,
    unit_index: int,
    final_content: str,
    unit_title: str = "",
    logger: Optional[logging.Logger] = None,
) -> bool:
    """
    将 WritingUnit 的修正结果同步到 NovelChapter 表（正文表单显示层）

    核心策略：当 NovelChapter 记录不存在时自动创建，确保数据永远不丢失。

    此函数是所有 WritingUnit → NovelChapter 同步的唯一入口。
    任何需要同步内容的代码路径都必须调用此函数，禁止使用 inline 代码。

    Args:
        db: 数据库会话
        project_id: 项目ID
        unit_index: 单元序号（对应 NovelChapter.chapter_number）
        final_content: 内容
        unit_title: 单元标题（用于新建 NovelChapter 的默认标题）
        logger: 可选的日志记录器（默认使用模块级 logger）

    Returns:
        True 表示同步成功

    Raises:
        不再静默吞掉异常——调用方负责决定如何处理失败。
    """
    log = logger or _default_logger

    chapter_query = select(NovelChapter).where(
        NovelChapter.project_id == project_id,
        NovelChapter.chapter_number == unit_index
    )
    chapter_result = await db.execute(chapter_query)
    chapter = chapter_result.scalar_one_or_none()

    if chapter:
        chapter.final_content = final_content
        chapter.word_count = len(final_content)
        # 内容已生成，状态升级为 COMPLETED（确保前端正文表单能正常显示）
        if chapter.status != ChapterStatus.COMPLETED:
            chapter.status = ChapterStatus.COMPLETED
        await db.commit()
        log.info(
            f"[NovelChapter同步] 已更新: project={project_id}, "
            f"chapter={unit_index}, word_count={len(final_content)}"
        )
    else:
        chapter = NovelChapter(
            project_id=project_id,
            chapter_number=unit_index,
            chapter_title=unit_title or f"第{unit_index}章",
            final_content=final_content,
            word_count=len(final_content),
            status=ChapterStatus.COMPLETED  # 内容已生成，直接设为已完成
        )
        db.add(chapter)
        await db.commit()
        log.info(
            f"[NovelChapter同步] 已自动创建: project={project_id}, "
            f"chapter={unit_index}, word_count={len(final_content)}"
        )

    return True
