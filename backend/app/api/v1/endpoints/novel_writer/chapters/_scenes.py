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


async def list_scenes(
    project_id: int,
    current_user: User,
    db: AsyncSession,
    episode: Optional[int] = None
):
    """
    获取剧本场景列表
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

        # 获取场景列表
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        if episode:
            query = query.where(NovelChapter.episode_number == episode)

        query = query.order_by(NovelChapter.episode_number,
                               NovelChapter.scene_number)

        result = await db.execute(query)
        chapters = result.scalars().all()

        scenes_data = []
        for c in chapters:
            scene_dict = c.to_summary_dict()
            scene_dict["episode_number"] = c.episode_number
            scene_dict["scene_number"] = c.scene_number
            scenes_data.append(scene_dict)

        return ResponseModel(
            success=True,
            data=ChapterListResponse(
                project_id=project.id,
                total_chapters=project.total_chapters,
                completed_chapters=project.completed_chapters,
                chapters=scenes_data
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取场景列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))




async def list_characters(
    project_id: int,
    current_user: User,
    db: AsyncSession
):
    """
    获取剧本角色列表（从已完成章节中提取）
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

        # 从角色状态文件中读取角色信息
        characters = []
        total_dialogues = 0

        if project.characters_file and os.path.exists(project.characters_file):
            try:
                with open(project.characters_file, 'r', encoding='utf-8') as f:
                    character_state = json.load(f)
                    for name, info in character_state.items():
                        char_info = CharacterInfo(
                            character_name=name,
                            character_type="配角",  # 默认
                            first_appearance=None,
                            character_description=str(info.get("状态", "")),
                            dialogue_count=0
                        )
                        characters.append(char_info)
            except Exception as e:
                logger.warning(f"读取角色状态文件失败: {str(e)}")

        return ResponseModel(
            success=True,
            data=CharacterListResponse(
                project_id=project.id,
                characters=characters,
                total_dialogues=total_dialogues
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取角色列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 分集详细大纲 API ====================
