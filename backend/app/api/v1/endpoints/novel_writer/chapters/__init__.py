"""章节管理 API 端点包

FastAPI路由定义，将请求分发给各处理函数
"""
from typing import Optional

from fastapi import Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import ResponseModel
from app.schemas.novel_writer import (
    DirectoryGenerateRequest, DirectoryResponse,
    ChapterContentResponse, ChapterContentUpdate, ChapterListResponse,
    ExportRequest,
    CharacterInfo, CharacterListResponse,
    EpisodeOutlineUpdate, EpisodeOutlineResponse, EpisodeOutlineListResponse,
)
from ..utils import router, settings, logger

from ._directory import (
    get_directory,
    generate_directory,
    update_chapter_title,
)
from ._content import (
    list_chapters,
    get_chapter,
    update_chapter,
    export_project,
    sync_content_status,
)
from ._scenes import (
    list_scenes,
    list_characters,
)
from ._episode_outlines import (
    get_episode_outlines,
    get_episode_outline,
    update_episode_outline,
    delete_episode_outline,
)


# ==================== 章节目录 API ====================

@router.get("/projects/{project_id}/directory", response_model=ResponseModel[DirectoryResponse])
async def get_directory(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取章节目录"""
    return await get_directory(project_id, current_user, db)


@router.post("/projects/{project_id}/generate-directory", response_model=ResponseModel[DirectoryResponse])
async def generate_directory(
    project_id: int,
    request: DirectoryGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成章节目录"""
    return await generate_directory(project_id, request, current_user, db)


@router.put("/projects/{project_id}/chapters/{chapter_num}/title")
async def update_chapter_title(
    project_id: int,
    chapter_num: int,
    title: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新单个章节标题"""
    return await update_chapter_title(project_id, chapter_num, title, current_user, db)


# ==================== 章节内容 API ====================

@router.get("/projects/{project_id}/chapters", response_model=ResponseModel[ChapterListResponse])
async def list_chapters(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取章节列表"""
    return await list_chapters(project_id, current_user, db)


@router.get("/projects/{project_id}/chapters/{chapter_num}", response_model=ResponseModel[ChapterContentResponse])
async def get_chapter(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取章节内容"""
    return await get_chapter(project_id, chapter_num, current_user, db)


@router.put("/projects/{project_id}/chapters/{chapter_num}")
async def update_chapter(
    project_id: int,
    chapter_num: int,
    request: ChapterContentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新章节内容"""
    return await update_chapter(project_id, chapter_num, request, current_user, db)


# ==================== 导出 API ====================

@router.post("/projects/{project_id}/export")
async def export_project(
    project_id: int,
    request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导出项目"""
    return await export_project(project_id, request, current_user, db)


# ==================== 剧本场景 API ====================

@router.get("/projects/{project_id}/scenes", response_model=ResponseModel[ChapterListResponse])
async def list_scenes(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    episode: Optional[int] = None
):
    """获取剧本场景列表"""
    return await list_scenes(project_id, current_user, db, episode)


@router.get("/projects/{project_id}/characters", response_model=ResponseModel[CharacterListResponse])
async def list_characters(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取剧本角色列表（从已完成章节中提取）"""
    return await list_characters(project_id, current_user, db)


# ==================== 分集详细大纲 API ====================

@router.get("/projects/{project_id}/episode-outlines", response_model=ResponseModel[EpisodeOutlineListResponse])
async def get_episode_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取所有分集详细大纲"""
    return await get_episode_outlines(project_id, current_user, db)


@router.get("/projects/{project_id}/episode-outlines/{episode}", response_model=ResponseModel[EpisodeOutlineResponse])
async def get_episode_outline(
    project_id: int,
    episode: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个分集详细大纲"""
    return await get_episode_outline(project_id, episode, current_user, db)


@router.put("/projects/{project_id}/episode-outlines/{episode}")
async def update_episode_outline(
    project_id: int,
    episode: int,
    request: EpisodeOutlineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新分集详细大纲"""
    return await update_episode_outline(project_id, episode, request, current_user, db)


@router.delete("/projects/{project_id}/episode-outlines/{episode}")
async def delete_episode_outline(
    project_id: int,
    episode: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除分集详细大纲"""
    return await delete_episode_outline(project_id, episode, current_user, db)


# ==================== 数据修复端点 ====================

@router.post("/projects/{project_id}/sync-content-status")
async def sync_content_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """同步章节正文状态（修复历史数据）"""
    return await sync_content_status(project_id, current_user, db)
