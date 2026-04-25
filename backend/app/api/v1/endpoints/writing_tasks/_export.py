"""
写作任务 API - 导出端点

@date: 2026-04-24
@version: v3.1.0 (从writing_tasks.py拆分)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db
from app.core.logger import get_logger
from app.api.deps import get_current_user
from app.models import User
from app.models.writing_task import WritingTask
from app.models.writing_unit import WritingUnit

logger = get_logger("writing_tasks")


def register_export_routes(router: APIRouter):
    """注册导出路由"""

    @router.get("/{task_id}/export")
    async def export_task(
        task_id: int,
        format: str = Query("txt", pattern="^(txt|md)$"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """导出写作任务生成的内容"""
        import io

        # 查询任务
        task_result = await db.execute(
            select(WritingTask).where(
                and_(WritingTask.id == task_id,
                     WritingTask.user_id == current_user.id)
            )
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 查询所有已完成的单元
        units_result = await db.execute(
            select(WritingUnit).where(WritingUnit.task_id == task_id)
            .order_by(WritingUnit.unit_index)
        )
        units = units_result.scalars().all()

        if not units:
            raise HTTPException(status_code=404, detail="暂无生成内容")

        # 构建内容
        content_parts = []
        for unit in units:
            if unit.final_content:
                title = unit.unit_title or f"第{unit.unit_index}章"
                if format == "md":
                    content_parts.append(f"\n\n# {title}\n\n{unit.final_content}")
                else:
                    content_parts.append(
                        f"\n\n{'='*50}\n{title}\n{'='*50}\n\n{unit.final_content}")

        full_content = "\n".join(content_parts).strip()

        if not full_content:
            raise HTTPException(status_code=404, detail="暂无生成内容")

        # 文件名
        filename = f"writing_task_{task_id}.{format}"
        media_type = "text/markdown" if format == "md" else "text/plain"

        return StreamingResponse(
            iter([full_content.encode('utf-8')]),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": f"{media_type}; charset=utf-8"
            }
        )

    @router.get("/{task_id}/units/{unit_index}/export")
    async def export_unit(
        task_id: int,
        unit_index: int,
        format: str = Query("txt", pattern="^(txt|md)$"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """导出单个单元的生成内容"""
        # 查询任务
        task_result = await db.execute(
            select(WritingTask).where(
                and_(WritingTask.id == task_id,
                     WritingTask.user_id == current_user.id)
            )
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 查询单元
        unit_result = await db.execute(
            select(WritingUnit).where(
                and_(WritingUnit.task_id == task_id,
                     WritingUnit.unit_index == unit_index)
            )
        )
        unit = unit_result.scalar_one_or_none()
        if not unit:
            raise HTTPException(status_code=404, detail="单元不存在")

        if not unit.final_content:
            raise HTTPException(status_code=404, detail="该单元暂无生成内容")

        # 构建内容
        title = unit.unit_title or f"第{unit.unit_index}章"
        if format == "md":
            content = f"# {title}\n\n{unit.final_content}"
        else:
            content = f"{'='*50}\n{title}\n{'='*50}\n\n{unit.final_content}"

        # 文件名
        filename = f"unit_{unit_index}.{format}"
        media_type = "text/markdown" if format == "md" else "text/plain"

        return StreamingResponse(
            iter([content.encode('utf-8')]),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": f"{media_type}; charset=utf-8"
            }
        )
