import os
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import (
    ResourceNotFoundException, ValidationException, AuthorizationException,
    AppException, ErrorCode
)
from app.models import User, NovelProject, NovelChapter, ProjectStatus, ChapterStatus
from app.schemas.common import ResponseModel
from app.schemas.novel_writer import (
    DirectoryGenerateRequest, DirectoryResponse,
    DirectoryUpdateRequest, ChapterMetadata,
    ChapterContentResponse, ChapterContentUpdate, ChapterListResponse,
    ExportRequest,
    CharacterInfo, CharacterListResponse,
    EpisodeOutlineUpdate, EpisodeOutlineResponse, EpisodeOutlineListResponse, EpisodeOutlineScene
)
from app.services.novel_writer.exporter import NovelExporter
from ..utils import settings, logger, get_project_data_dir, extract_chapter_count


async def list_chapters(
    project_id: int,
    current_user: User,
    db: AsyncSession
):
    """
    获取章节列表
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取章节列表
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        ).order_by(NovelChapter.chapter_number)

        result = await db.execute(query)
        chapters = result.scalars().all()

        chapters_data = [c.to_summary_dict() for c in chapters]

        return ResponseModel(
            success=True,
            data=ChapterListResponse(
                project_id=project.id,
                total_chapters=project.total_chapters,
                completed_chapters=project.completed_chapters,
                chapters=chapters_data
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取章节列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))




async def get_chapter(
    project_id: int,
    chapter_num: int,
    current_user: User,
    db: AsyncSession
):
    """
    获取章节内容
    """
    try:
        # 获取章节
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == chapter_num
        )
        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            raise ResourceNotFoundException("章节不存在")

        # 验证用户权限
        project_query = select(NovelProject).where(
            NovelProject.id == project_id)
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project or project.user_id != current_user.id:
            raise AuthorizationException(message="无权访问此章节")

        return ResponseModel(
            success=True,
            data=ChapterContentResponse(
                id=chapter.id,
                project_id=chapter.project_id,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter.chapter_title,
                chapter_metadata=chapter.chapter_metadata,
                status=chapter.status,
                draft_content=chapter.draft_content,  # 返回原始草稿
                final_content=chapter.final_content,
                word_count=chapter.word_count,
                token_count=chapter.token_count,
                created_at=chapter.created_at,
                updated_at=chapter.updated_at
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取章节内容失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))




async def update_chapter(
    project_id: int,
    chapter_num: int,
    request: ChapterContentUpdate,
    current_user: User,
    db: AsyncSession
):
    """
    更新章节内容
    """
    try:
        # 获取章节
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == chapter_num
        )
        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            raise ResourceNotFoundException("章节不存在")

        # 更新内容
        chapter.final_content = request.content
        chapter.word_count = len(request.content)
        chapter.user_edited = 1

        await db.commit()
        
        # 同步更新 WritingUnit 表（质控系统依赖此表）
        try:
            from app.models.writing_unit import WritingUnit
            from app.models.writing_task import WritingTask
            task_query = select(WritingTask).where(
                WritingTask.project_id == project_id
            )
            task_result = await db.execute(task_query)
            tasks = task_result.scalars().all()
            
            if tasks:
                task_ids = [task.id for task in tasks]
                unit_query = select(WritingUnit).where(
                    WritingUnit.unit_index == chapter_num,
                    WritingUnit.task_id.in_(task_ids)
                ).order_by(WritingUnit.id.desc())
                unit_result = await db.execute(unit_query)
                unit = unit_result.scalars().first()
                
                if unit:
                    unit.final_content = request.content
                    unit.word_count = len(request.content)
                    await db.commit()
                    logger.info(f"WritingUnit已同步: unit_index={chapter_num}")
        except Exception as sync_error:
            logger.warning(f"WritingUnit同步失败: {sync_error}")

        logger.info(f"章节内容更新: 第{chapter_num}章")

        return ResponseModel(success=True, message="章节内容已更新")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新章节失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 导出 API ====================



async def export_project(
    project_id: int,
    request: ExportRequest,
    current_user: User,
    db: AsyncSession
):
    """
    导出项目
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取章节
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        ).order_by(NovelChapter.chapter_number)

        result = await db.execute(query)
        chapters = list(result.scalars().all())

        # 导出
        exporter = NovelExporter()
        export_result = await exporter.export_project(
            project=project,
            chapters=chapters,
            format=request.format,
            include_metadata=request.include_metadata,
            chapter_range=request.chapter_range
        )

        if not export_result["success"]:
            raise AppException(ErrorCode.INTERNAL_ERROR, export_result.get("error_message", "导出失败"))

        # 返回文件
        return FileResponse(
            path=export_result["file_path"],
            filename=export_result["file_name"],
            media_type="application/octet-stream"
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"导出失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 剧本场景 API ====================



async def sync_content_status(
    project_id: int,
    current_user: User,
    db: AsyncSession
):
    """
    同步章节正文状态（修复历史数据）

    将已生成正文的章节在 xxx_outlines 中的 content_status 设置为 'generated'
    用于修复之前批量生成时未正确更新状态的问题
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        content_type = getattr(project, 'content_type', 'novel')
        updated_count = 0

        # 获取所有已生成正文的章节记录
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.final_content != None
        )
        chapter_result = await db.execute(chapter_query)
        chapters = chapter_result.scalars().all()

        if content_type == 'novel':
            chapter_outlines = project.chapter_outlines or {}
            for chapter in chapters:
                if chapter.chapter_number:
                    ch_num = str(chapter.chapter_number)
                    if ch_num in chapter_outlines:
                        chapter_outlines[ch_num]["content_status"] = "generated"
                        chapter_outlines[ch_num]["content_word_count"] = chapter.word_count or len(
                            chapter.final_content or "")
                        chapter_outlines[ch_num]["content_generated_at"] = chapter.updated_at.isoformat(
                        ) if chapter.updated_at else datetime.now().isoformat()
                        updated_count += 1
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')

        elif content_type == 'series_script':
            episode_outlines = project.episode_outlines or {}
            for chapter in chapters:
                if chapter.episode_number:
                    ep_num = str(chapter.episode_number)
                    if ep_num in episode_outlines:
                        episode_outlines[ep_num]["content_status"] = "generated"
                        episode_outlines[ep_num]["content_word_count"] = chapter.word_count or len(
                            chapter.final_content or "")
                        episode_outlines[ep_num]["content_generated_at"] = chapter.updated_at.isoformat(
                        ) if chapter.updated_at else datetime.now().isoformat()
                        updated_count += 1
            project.episode_outlines = episode_outlines
            flag_modified(project, 'episode_outlines')

        elif content_type == 'movie_script':
            scene_outlines = project.scene_outlines or {}
            for chapter in chapters:
                if chapter.scene_number:
                    sc_num = str(chapter.scene_number)
                    if sc_num in scene_outlines:
                        scene_outlines[sc_num]["content_status"] = "generated"
                        scene_outlines[sc_num]["content_word_count"] = chapter.word_count or len(
                            chapter.final_content or "")
                        scene_outlines[sc_num]["content_generated_at"] = chapter.updated_at.isoformat(
                        ) if chapter.updated_at else datetime.now().isoformat()
                        updated_count += 1
            project.scene_outlines = scene_outlines
            flag_modified(project, 'scene_outlines')

        await db.commit()
        logger.info(f"已同步 {updated_count} 个章节的正文状态: {project.title}")
        return ResponseModel(
            success=True,
            message=f"已同步 {updated_count} 个章节的正文状态",
            data={"updated_count": updated_count}
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"同步正文状态失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))
