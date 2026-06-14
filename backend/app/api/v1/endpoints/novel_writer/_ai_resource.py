"""小说/剧本正文生成 - AI视觉资源管理端点

提供AI视觉资源内容的获取、保存和生成功能。
AI资源独立于剧本正文存储，用户可选择任意版本剧本(初稿/修正稿/自主修订稿)作为输入来生成。

@date: 2026-06-04
@version: v1.0.0
"""
import json
from typing import Optional
from datetime import datetime

from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.schemas.common import ResponseModel

from .utils import router, logger


# ==================== 请求/响应模型 ====================

class SaveAIResourceRequest(BaseModel):
    """手动保存AI资源内容请求"""
    content: str


class GenerateAIResourceRequest(BaseModel):
    """生成AI资源请求"""
    source_version: str = "draft"  # "draft" | "qc_fix" | "self_revise"


# ==================== 辅助函数 ====================

async def _get_writing_unit(
    db: AsyncSession,
    project_id: int,
    unit_index: int,
    user_id: int
):
    """查找指定项目和单元的 WritingUnit 记录"""
    from app.models.writing_unit import WritingUnit
    from app.models.writing_task import WritingTask

    task_query = select(WritingTask).where(
        WritingTask.project_id == project_id,
        WritingTask.user_id == user_id
    )
    task_result = await db.execute(task_query)
    tasks = task_result.scalars().all()

    if not tasks:
        return None, "未找到项目的写作任务"

    task_ids = [task.id for task in tasks]
    unit_query = select(WritingUnit).where(
        WritingUnit.unit_index == unit_index,
        WritingUnit.task_id.in_(task_ids)
    ).order_by(WritingUnit.id.desc())
    unit_result = await db.execute(unit_query)
    unit = unit_result.scalars().first()

    if not unit:
        return None, f"未找到单元 {unit_index}"

    return unit, None


def _get_version_content(unit, source_version: str) -> str:
    """根据版本标识获取对应的剧本正文内容

    WritingUnit 模型中的内容版本字段（v3.0）：
    - content_after_generation: LLM生成的初稿内容
    - content_after_qc_fix: 质控修正后的内容
    - content_after_self_revise: 用户自主修订后的内容
    """
    if source_version == "self_revise":
        return getattr(unit, 'content_after_self_revise', None) or ""
    elif source_version == "qc_fix":
        return getattr(unit, 'content_after_qc_fix', None) or ""
    else:  # draft
        return getattr(unit, 'content_after_generation', None) or ""


# ==================== 端点 ====================

@router.get("/projects/{project_id}/units/{unit_index}/ai-resource", response_model=ResponseModel)
async def get_ai_resource(
    project_id: int,
    unit_index: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定单元的AI视觉资源内容

    Args:
        project_id: 项目ID
        unit_index: 单元序号
    """
    try:
        unit, error_msg = await _get_writing_unit(db, project_id, unit_index, current_user.id)
        if not unit:
            return ResponseModel(success=False, message=error_msg)

        ai_content = unit.ai_resource_content or ""
        return ResponseModel(
            success=True,
            message="获取AI资源内容成功",
            data={
                "unit_index": unit_index,
                "content": ai_content,
                "content_length": len(ai_content),
                "has_content": bool(ai_content),
            }
        )
    except Exception as e:
        logger.error(f"[AI资源获取] 失败: {e}", exc_info=True)
        return ResponseModel(success=False, message=f"获取AI资源内容失败: {str(e)}")


@router.put("/projects/{project_id}/units/{unit_index}/ai-resource", response_model=ResponseModel)
async def save_ai_resource(
    project_id: int,
    unit_index: int,
    request: SaveAIResourceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    手动保存AI视觉资源内容

    Args:
        project_id: 项目ID
        unit_index: 单元序号
        request: 包含AI资源内容的请求体
    """
    try:
        unit, error_msg = await _get_writing_unit(db, project_id, unit_index, current_user.id)
        if not unit:
            return ResponseModel(success=False, message=error_msg)

        unit.ai_resource_content = request.content
        await db.commit()
        await db.refresh(unit)

        logger.info(
            f"[AI资源保存] unit_index={unit_index}, project_id={project_id}, "
            f"content_length={len(request.content)}"
        )

        return ResponseModel(
            success=True,
            message=f"单元 {unit_index} AI资源内容已保存",
            data={
                "unit_index": unit_index,
                "content_length": len(request.content),
                "updated_at": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"[AI资源保存] 失败: {e}", exc_info=True)
        await db.rollback()
        return ResponseModel(success=False, message=f"保存AI资源内容失败: {str(e)}")


@router.post("/projects/{project_id}/units/{unit_index}/generate-ai-resource")
async def generate_ai_resource(
    project_id: int,
    unit_index: int,
    request: GenerateAIResourceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    基于指定版本的剧本内容生成AI视觉资源(SSE流式)

    工作流程:
    1. 根据 source_version 获取剧本正文内容
    2. 获取项目风格配置
    3. 构建AI资源生成提示词
    4. 调用LLM流式生成
    5. 自动保存到 ai_resource_content 字段

    Args:
        project_id: 项目ID
        unit_index: 单元序号
        request: 生成请求(指定源版本)
    """
    source_version = request.source_version
    full_content = ""  # v4.3: 提前声明，避免 except 块中 UnboundLocalError

    async def _generate_stream():
        nonlocal full_content
        try:
            # 1. 获取单元和内容
            unit, error_msg = await _get_writing_unit(db, project_id, unit_index, current_user.id)
            if not unit:
                yield _format_sse("error", {"message": error_msg})
                return

            script_content = _get_version_content(unit, source_version)
            if not script_content:
                yield _format_sse("error", {
                    "message": f"单元 {unit_index} 的{_get_version_label(source_version)}内容为空，请先生成剧本正文"
                })
                return

            unit_title = unit.unit_title or f"第{unit_index}集"

            # 2. 获取项目风格配置
            style_config = await _get_style_config(db, project_id, current_user.id)

            # 3. 调用AI资源生成引擎(流式)
            from app.services.ai_resource import AIResourceGenerator
            generator = AIResourceGenerator()

            async for sse_event in generator.generate_stream(
                script_content=script_content,
                unit_title=unit_title,
                style_config=style_config,
                db=db,
                user_id=current_user.id
            ):
                # 解析SSE事件以提取内容
                if sse_event.startswith('event: chunk'):
                    try:
                        data_part = sse_event.split('data: ', 1)[1].strip()
                        event_data = json.loads(data_part)
                        full_content += event_data.get("text", "")
                    except (json.JSONDecodeError, IndexError):
                        pass
                elif sse_event.startswith('event: complete'):
                    # 解析complete事件获取生成内容
                    try:
                        data_part = sse_event.split('data: ', 1)[1].strip()
                        event_data = json.loads(data_part)
                        if event_data.get("content"):
                            full_content = event_data["content"]
                    except (json.JSONDecodeError, IndexError):
                        pass
                elif sse_event.startswith('event: error'):
                    yield sse_event  # 直接传递错误
                    return

                yield sse_event  # 透传SSE事件给前端

            # 4. 保存到数据库
            if full_content:
                try:
                    unit.ai_resource_content = full_content
                    await db.commit()
                    await db.refresh(unit)
                    logger.info(
                        f"[AI资源生成] 已保存: unit_index={unit_index}, "
                        f"source_version={source_version}, length={len(full_content)}"
                    )
                    yield _format_sse("saved", {
                        "message": "AI资源已保存",
                        "content_length": len(full_content),
                        "unit_index": unit_index,
                    })
                except Exception as save_err:
                    logger.error(f"[AI资源生成] 保存失败: {save_err}", exc_info=True)
                    await db.rollback()
                    yield _format_sse("error", {
                        "message": "AI资源生成完成但保存失败，请手动保存",
                        "content_length": len(full_content),
                    })

        except Exception as e:
            logger.error(f"[AI资源生成] 生成失败: {e}", exc_info=True)
            # v2.7: 异常中断时尝试保存已累积的部分内容，避免内容全部丢失
            if full_content:
                try:
                    unit.ai_resource_content = full_content
                    await db.commit()
                    logger.info(f"[AI资源生成] 异常中断前已保存部分内容, length={len(full_content)}")
                except Exception as partial_save_err:
                    logger.error(f"[AI资源生成] 部分内容保存也失败: {partial_save_err}")
                    await db.rollback()
            yield _format_sse("error", {"message": f"AI资源生成失败: {str(e)}"})

    return StreamingResponse(
        _generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


# ==================== 辅助函数 ====================

async def _get_style_config(db, project_id: int, user_id: int) -> dict:
    """获取项目风格配置（用于AI视觉资源生成）

    注意：style_names/style_dimensions 是创作层面的风格选择器数据
    （如"导演风格"、"叙事风格"），不应直接作为视觉风格标签。
    此处将其作为上下文传递给提示词构建函数，由提示词引导 LLM
    从剧本内容中自主推导合适的视觉风格术语。
    """
    style_config = {}
    try:
        from app.models.writing_task import WritingTask as WT
        task_q = select(WT).where(
            WT.project_id == project_id,
            WT.user_id == user_id
        )
        task_r = await db.execute(task_q)
        task = task_r.scalars().first()
        if task and task.config:
            cfg = task.config if isinstance(task.config, dict) else {}
            # v4.3: content_type 存储在 WritingTask.config JSON 中，不是顶层字段
            content_type = cfg.get("content_type", "")
            if content_type in ("series_script",):
                style_config["style_names"] = cfg.get("series_style_names", [])
                style_config["style_dimensions"] = cfg.get("series_style_dimensions", {})
                style_config["style_intensity"] = cfg.get("series_style_intensity", 0.7)
                style_config["content_type"] = "series"
                style_config["aspect_ratio"] = cfg.get("aspect_ratio", "16:9")
                # 提取题材信息用于视觉风格推导
                genre_parts = []
                if cfg.get("series_type"):
                    genre_parts.append(cfg["series_type"])
                if cfg.get("theme"):
                    genre_parts.append(cfg["theme"])
                if genre_parts:
                    style_config["genre_info"] = "、".join(genre_parts)
            elif content_type in ("movie_script", "script"):
                style_config["style_names"] = cfg.get("movie_style_names", [])
                style_config["style_dimensions"] = cfg.get("movie_style_dimensions", {})
                style_config["style_intensity"] = cfg.get("movie_style_intensity", 0.7)
                style_config["content_type"] = "movie"
                style_config["aspect_ratio"] = cfg.get("aspect_ratio", "16:9")
                # 提取题材信息
                genre_parts = []
                if cfg.get("theme"):
                    genre_parts.append(cfg["theme"])
                if genre_parts:
                    style_config["genre_info"] = "、".join(genre_parts)
    except Exception as cfg_err:
        logger.warning(f"[AI资源生成] 获取风格配置失败: {cfg_err}")
        style_config = {"content_type": "series", "style_names": [], "aspect_ratio": "16:9"}
    return style_config


# v2.7: 统一SSE格式化函数到AIResourceGenerator，避免重复定义
from app.services.ai_resource.generator import AIResourceGenerator as _Gen
_format_sse = _Gen._format_sse
def _get_version_label(version: str) -> str:
    """获取版本中文标签"""
    labels = {"draft": "初稿", "qc_fix": "修正稿", "self_revise": "自主修订稿"}
    return labels.get(version, version)
