"""
小说/剧本正文生成 API 端点 - 内容生成模块

提供批量内容获取、任务状态管理、内容删除等功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import json
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import ResourceNotFoundException, AppException, ErrorCode, ValidationException
from app.core.sse_ticket import get_sse_ticket_manager

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_user_from_query_or_header
from app.models import User, NovelProject, NovelChapter, ProjectStatus, ChapterStatus
from app.schemas.common import ResponseModel
from app.services.task_manager import (
    task_manager, set_memory_cancel_token, clear_memory_cancel_token,
    trigger_memory_cancel, is_memory_cancelled,
    subscribe_task_events, unsubscribe_task_events
)

from ..utils import router, logger


# ==================== SSE Ticket API ====================

@router.post("/projects/{project_id}/sse-ticket")
async def create_sse_ticket(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建 SSE 连接 ticket（短期一次性凭证）

    用于替代 URL 中直接传递 token 的方式，提升 SSE 连接安全性。
    Ticket 有效期 60 秒，使用后立即失效。

    Returns:
        ticket: 一次性 ticket 字符串
    """
    # 验证项目权限
    query = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise ResourceNotFoundException("项目不存在")

    ticket_manager = get_sse_ticket_manager()
    ticket = ticket_manager.create_ticket(
        user_id=current_user.id,
        project_id=project_id
    )

    logger.info(f"[SSE Ticket] 用户 {current_user.id} 为项目 {project_id} 创建 ticket")

    return ResponseModel(
        success=True,
        data={"ticket": ticket},
        message="SSE ticket 创建成功"
    )


# ==================== 批量获取正文内容 API ====================

@router.get("/projects/{project_id}/all-episode-content")
async def get_all_episode_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取全部剧集正文内容

    返回所有已生成的剧集正文，用于批量下载
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

        # 获取所有有正文的章节记录（按 episode_number 筛选）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number != None,
            NovelChapter.final_content != None
        ).order_by(NovelChapter.episode_number)

        chapter_result = await db.execute(chapter_query)
        chapters = chapter_result.scalars().all()

        # 构建返回数据
        contents = []
        for chapter in chapters:
            contents.append({
                "episode_number": chapter.episode_number,
                "chapter_title": chapter.chapter_title or f"第{chapter.episode_number}集",
                "content": chapter.final_content,
                "word_count": chapter.word_count
            })

        return ResponseModel(
            success=True,
            data={
                "project_title": project.title,
                "content_type": "episode",
                "total_count": len(contents),
                "contents": contents
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取全部剧集正文失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/all-chapter-content")
async def get_all_chapter_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取全部小说章节正文内容

    返回所有已生成的章节正文，用于批量下载
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

        # 获取所有有正文的章节记录（小说类型：episode_number 为空，scene_number 为空）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number == None,
            NovelChapter.scene_number == None,
            NovelChapter.final_content != None
        ).order_by(NovelChapter.chapter_number)

        chapter_result = await db.execute(chapter_query)
        chapters = chapter_result.scalars().all()

        # 构建返回数据
        contents = []
        for chapter in chapters:
            contents.append({
                "chapter_number": chapter.chapter_number,
                "chapter_title": chapter.chapter_title or f"第{chapter.chapter_number}章",
                "content": chapter.final_content,
                "word_count": chapter.word_count
            })

        return ResponseModel(
            success=True,
            data={
                "project_title": project.title,
                "content_type": "chapter",
                "total_count": len(contents),
                "contents": contents
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取全部章节正文失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/all-scene-content")
async def get_all_scene_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取全部电影场景正文内容

    返回所有已生成的场景正文，用于批量下载
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

        # 获取所有有正文的章节记录（电影类型：scene_number 不为空）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.scene_number != None,
            NovelChapter.final_content != None
        ).order_by(NovelChapter.scene_number)

        chapter_result = await db.execute(chapter_query)
        chapters = chapter_result.scalars().all()

        # 构建返回数据
        contents = []
        for chapter in chapters:
            contents.append({
                "scene_number": chapter.scene_number,
                "chapter_title": chapter.chapter_title or f"第{chapter.scene_number}场",
                "content": chapter.final_content,
                "word_count": chapter.word_count
            })

        return ResponseModel(
            success=True,
            data={
                "project_title": project.title,
                "content_type": "scene",
                "total_count": len(contents),
                "contents": contents
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取全部场景正文失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 任务状态管理 API ====================

@router.get("/projects/{project_id}/task-status")
async def get_task_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目的当前生成任务状态

    用于页面刷新后恢复生成状态UI，检查是否有正在进行的批量生成任务
    """
    # 验证项目权限
    query = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise ResourceNotFoundException("项目不存在")

    task = await task_manager.get_task(project_id)

    return ResponseModel(
        success=True,
        data=task  # 无任务时返回None
    )


@router.post("/projects/{project_id}/cancel-task")
async def cancel_generation_task(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    取消当前生成任务

    无论前端是否保持连接，都可以通过此API取消任务。
    后端会在每次循环迭代时检查任务状态，发现被取消后停止生成。
    """
    # 验证项目权限
    query = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise ResourceNotFoundException("项目不存在")

    # 检查是否有运行中的任务
    task = await task_manager.get_task(project_id)
    if not task or task.get("status") != "running":
        return ResponseModel(
            success=False,
            message="没有正在运行的任务"
        )

    # 取消任务
    cancelled_task = await task_manager.cancel_task(project_id)

    # 同时触发内存取消令牌（立即生效，不依赖 Redis）
    trigger_memory_cancel(project_id)

    logger.info(f"用户 {current_user.username} 取消了项目 {project.title} 的生成任务")

    return ResponseModel(
        success=True,
        data=cancelled_task,
        message="任务已取消，正在生成的内容将在当前项完成后停止"
    )


@router.get("/projects/{project_id}/task-events")
async def stream_task_events(
    project_id: int,
    current_user: User = Depends(get_current_user_from_query_or_header),
    db: AsyncSession = Depends(get_db)
):
    """
    SSE 端点：实时推送任务状态更新

    客户端连接后，会收到实时的任务进度更新。
    支持自动重连，断线后重新连接可继续接收更新。
    """
    # 验证项目权限
    query = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise ResourceNotFoundException("项目不存在")

    async def event_generator():
        """SSE 事件生成器"""
        queue = None
        try:
            # 订阅任务事件
            queue = subscribe_task_events(project_id)

            # 首先发送当前任务状态（如果存在）
            current_task = await task_manager.get_task(project_id)
            if current_task:
                yield f"data: {json.dumps(current_task, ensure_ascii=False)}\n\n"
            else:
                # 无任务时发送空状态
                yield f"data: null\n\n"

            # 持续监听任务更新
            while True:
                try:
                    # 等待事件，设置超时以发送心跳
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event_data}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳注释，防止连接超时
                    yield ": heartbeat\n\n"
                except asyncio.CancelledError:
                    # 客户端断开连接
                    break
        finally:
            # 清理订阅
            if queue:
                unsubscribe_task_events(project_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


# ==================== 删除正文内容 API ====================

@router.delete("/projects/{project_id}/chapter-content/{chapter_num}")
async def delete_chapter_content(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除小说章节正文内容（保留大纲）
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

        # 删除章节正文记录
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == chapter_num
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if chapter:
            # 清空正文内容，保留章节记录
            chapter.final_content = None
            chapter.draft_content = None
            chapter.word_count = 0
            chapter.status = ChapterStatus.PENDING

        # 更新章节大纲的正文生成状态
        chapter_outlines = project.chapter_outlines or {}
        if str(chapter_num) in chapter_outlines:
            chapter_outlines[str(chapter_num)]["content_status"] = None
            chapter_outlines[str(chapter_num)]["content_generated_at"] = None
            chapter_outlines[str(chapter_num)]["content_word_count"] = 0
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')

        await db.commit()
        logger.info(f"第{chapter_num}章正文已删除: {project.title}")
        return ResponseModel(success=True, message=f"第{chapter_num}章正文已删除")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除章节正文失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/episode-content/{episode_num}")
async def delete_episode_content(
    project_id: int,
    episode_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除剧集正文内容（保留大纲）
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

        # 删除剧集正文记录（通过episode_number查找）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number == episode_num
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if chapter:
            # 清空正文内容，保留章节记录
            chapter.final_content = None
            chapter.draft_content = None
            chapter.word_count = 0
            chapter.status = ChapterStatus.PENDING

        # 更新分集大纲的正文生成状态
        episode_outlines = project.episode_outlines or {}
        if str(episode_num) in episode_outlines:
            episode_outlines[str(episode_num)]["content_status"] = None
            episode_outlines[str(episode_num)]["content_generated_at"] = None
            episode_outlines[str(episode_num)]["content_word_count"] = 0
            project.episode_outlines = episode_outlines
            flag_modified(project, 'episode_outlines')

        await db.commit()
        logger.info(f"第{episode_num}集正文已删除: {project.title}")
        return ResponseModel(success=True, message=f"第{episode_num}集正文已删除")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除剧集正文失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/scene-content/{scene_num}")
async def delete_scene_content(
    project_id: int,
    scene_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除电影场景正文内容（保留大纲）
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

        # 删除场景正文记录（通过scene_number查找）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.scene_number == scene_num
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if chapter:
            # 清空正文内容，保留章节记录
            chapter.final_content = None
            chapter.draft_content = None
            chapter.word_count = 0
            chapter.status = ChapterStatus.PENDING

        # 更新场景大纲的正文生成状态
        scene_outlines = project.scene_outlines or {}
        if str(scene_num) in scene_outlines:
            scene_outlines[str(scene_num)]["content_status"] = None
            scene_outlines[str(scene_num)]["content_generated_at"] = None
            scene_outlines[str(scene_num)]["content_word_count"] = 0
            project.scene_outlines = scene_outlines
            flag_modified(project, 'scene_outlines')

        await db.commit()
        logger.info(f"第{scene_num}场正文已删除: {project.title}")
        return ResponseModel(success=True, message=f"第{scene_num}场正文已删除")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除场景正文失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/all-content")
async def delete_all_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    一键清空所有大纲和正文内容
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

        # 清空所有大纲
        project.episode_outlines = None
        project.chapter_outlines = None
        project.scene_outlines = None
        flag_modified(project, 'episode_outlines')
        flag_modified(project, 'chapter_outlines')
        flag_modified(project, 'scene_outlines')

        # 删除所有章节记录
        delete_query = delete(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        await db.execute(delete_query)

        # 重置项目进度
        project.completed_chapters = 0
        project.current_chapter = 0
        project.status = ProjectStatus.INIT

        await db.commit()
        logger.info(f"已清空所有大纲和正文: {project.title}")
        return ResponseModel(success=True, message="已清空所有大纲和正文内容")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"清空内容失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/all-outlines")
async def delete_all_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    一键清空所有大纲（保留正文）
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

        # 清空所有大纲
        project.episode_outlines = None
        project.chapter_outlines = None
        project.scene_outlines = None
        flag_modified(project, 'episode_outlines')
        flag_modified(project, 'chapter_outlines')
        flag_modified(project, 'scene_outlines')

        await db.commit()
        logger.info(f"已清空所有大纲: {project.title}")
        return ResponseModel(success=True, message="已清空所有大纲")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"清空大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/all-chapter-content")
async def delete_all_chapter_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    一键清空所有正文（保留大纲）

    注意：此操作不会影响知识库
    - 保留知识库状态 (kb_status)
    - 保留知识库向量数据 (project_kb_collection)
    - 保留知识图谱文件 (global_outline_graph_path)
    - 仅清空正文内容和生成状态
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

        # 清空所有章节正文记录
        delete_query = delete(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        await db.execute(delete_query)

        # 清空大纲中的正文状态
        content_type = project.content_type
        if content_type == 'novel':
            chapter_outlines = project.chapter_outlines or {}
            for key in chapter_outlines:
                chapter_outlines[key]["content_status"] = None
                chapter_outlines[key]["content_generated_at"] = None
                chapter_outlines[key]["content_word_count"] = 0
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')
        elif content_type == 'series_script':
            episode_outlines = project.episode_outlines or {}
            for key in episode_outlines:
                episode_outlines[key]["content_status"] = None
                episode_outlines[key]["content_generated_at"] = None
                episode_outlines[key]["content_word_count"] = 0
            project.episode_outlines = episode_outlines
            flag_modified(project, 'episode_outlines')
        elif content_type == 'movie_script':
            scene_outlines = project.scene_outlines or {}
            for key in scene_outlines:
                scene_outlines[key]["content_status"] = None
                scene_outlines[key]["content_generated_at"] = None
                scene_outlines[key]["content_word_count"] = 0
            project.scene_outlines = scene_outlines
            flag_modified(project, 'scene_outlines')

        # 重置项目进度
        project.completed_chapters = 0
        project.current_chapter = 0

        await db.commit()
        logger.info(f"已清空所有正文: {project.title}")
        return ResponseModel(success=True, message="已清空所有正文内容")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"清空正文失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))

