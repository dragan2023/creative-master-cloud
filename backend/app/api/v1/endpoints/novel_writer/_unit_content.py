"""小说/剧本正文生成 - 单元内容更新端点

提供用户手动编辑单元正文内容的API支持。

@date: 2026-05-23
@version: v1.0.0
"""
from typing import Optional
from datetime import datetime

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.schemas.common import ResponseModel

from .utils import router, logger
from .quality_control_v2._common import _sync_writing_unit_to_novel_chapter


# ==================== 请求模型 ====================

class UpdateUnitContentRequest(BaseModel):
    """单元内容更新请求"""
    content: str
    save_as: Optional[str] = "qc_fix"  # "qc_fix" 或 "self_revise"


# ==================== 端点 ====================

@router.put("/units/{unit_index}/content", response_model=ResponseModel)
async def update_unit_content(
    unit_index: int,
    request: UpdateUnitContentRequest,
    project_id: int = Query(..., description="项目ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新指定单元的内容
    
    用户手动编辑单元正文后，通过此接口保存修改。
    修改会同步到 WritingUnit、NovelChapter 两张表，
    并同时更新 content_after_qc_fix（视为最终修正稿）。
    
    Args:
        unit_index: 单元序号（章/集/场号）
        project_id: 项目ID（query参数）
        request: 包含新内容的请求体
    
    Returns:
        更新结果
    """
    try:
        from app.models.writing_unit import WritingUnit
        from app.models.writing_task import WritingTask

        logger.info(
            f"[单元内容更新] unit_index={unit_index}, project_id={project_id}, "
            f"user={current_user.id}, content_length={len(request.content)}"
        )

        # 1. 查找关联的 WritingTask
        task_query = select(WritingTask).where(
            WritingTask.project_id == project_id,
            WritingTask.user_id == current_user.id
        )
        task_result = await db.execute(task_query)
        tasks = task_result.scalars().all()

        if not tasks:
            return ResponseModel(
                success=False,
                message=f"未找到项目 {project_id} 的写作任务"
            )

        # 2. 查找对应的 WritingUnit（取最新记录）
        task_ids = [task.id for task in tasks]
        unit_query = select(WritingUnit).where(
            WritingUnit.unit_index == unit_index,
            WritingUnit.task_id.in_(task_ids)
        ).order_by(WritingUnit.id.desc())
        unit_result = await db.execute(unit_query)
        unit = unit_result.scalars().first()

        if not unit:
            return ResponseModel(
                success=False,
                message=f"未找到单元 {unit_index}"
            )

        # 3. 确定保存目标字段
        save_as = request.save_as or "qc_fix"
        
        # 4. 保存内容
        original_content = unit.final_content
        unit.final_content = request.content
        unit.word_count = len(request.content)

        # 5. 根据 save_as 参数决定保存到哪个版本字段
        if save_as == "self_revise":
            # 用户自主修订稿：存入 content_after_self_revise
            unit.content_after_self_revise = request.content
        else:
            # 默认：手动编辑等同于质控修正稿
            unit.content_after_qc_fix = request.content

        # 6. 如果从未设置过初稿，将当前内容作为初稿保留
        if not unit.content_after_generation:
            unit.content_after_generation = original_content or request.content

        await db.commit()
        await db.refresh(unit)

        logger.info(
            f"[单元内容更新] WritingUnit 已更新: unit={unit_index}, "
            f"save_as={save_as}, word_count={unit.word_count}"
        )

        # 7. 同步到 NovelChapter
        try:
            await _sync_writing_unit_to_novel_chapter(
                db=db,
                project_id=project_id,
                unit_index=unit_index,
                final_content=request.content,
                unit_title=getattr(unit, 'unit_title', '') or f"第{unit_index}章"
            )
            logger.info(f"[单元内容更新] NovelChapter 同步成功: chapter_number={unit_index}")
        except Exception as sync_error:
            logger.error(f"[单元内容更新] NovelChapter 同步失败: {sync_error}")
            # 非致命错误，不影响主流程

        return ResponseModel(
            success=True,
            message=f"单元 {unit_index} 内容已更新",
            data={
                "unit_index": unit_index,
                "word_count": unit.word_count,
                "content_length": len(request.content),
                "updated_at": datetime.now().isoformat()
            }
        )

    except Exception as e:
        logger.error(f"[单元内容更新] 失败: {e}", exc_info=True)
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"更新单元内容失败: {str(e)}"
        )
