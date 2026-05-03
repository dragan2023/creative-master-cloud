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


async def get_episode_outlines(
    project_id: int,
    current_user: User,
    db: AsyncSession
):
    """
    获取所有分集详细大纲

    返回项目下所有已生成的分集详细大纲列表，供用户查看和管理。
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

        # 获取分集大纲
        episode_outlines = project.episode_outlines or {}

        # 获取总集数
        script_config = project.series_script_config or project.script_config or {}
        total_episodes = script_config.get("episode_count", 0)

        # 如果没有配置总集数，尝试从大纲中提取
        if total_episodes == 0 and project.outline_content:
            total_episodes = extract_chapter_count(
                project.outline_content, "series_script")

        # 构建响应列表
        episodes = []
        generated_count = 0

        for ep_num in range(1, total_episodes + 1):
            ep_outline = episode_outlines.get(str(ep_num), {})
            if ep_outline:
                generated_count += 1
                episodes.append(EpisodeOutlineResponse(
                    episode_number=ep_outline.get("episode_number", ep_num),
                    episode_title=ep_outline.get("episode_title"),
                    episode_summary=ep_outline.get("episode_summary"),
                    detailed_outline=ep_outline.get("detailed_outline", ""),
                    estimated_duration=ep_outline.get("estimated_duration"),
                    scenes=[EpisodeOutlineScene(
                        **s) for s in ep_outline.get("scenes", [])] if ep_outline.get("scenes") else None,
                    core_conflict=ep_outline.get("core_conflict"),
                    emotional_curve=ep_outline.get("emotional_curve"),
                    key_dialogues=ep_outline.get("key_dialogues"),
                    visual_highlights=ep_outline.get("visual_highlights"),
                    status=ep_outline.get("status", "generated"),
                    content_status=ep_outline.get("content_status"),
                    content_word_count=ep_outline.get("content_word_count"),
                    created_at=ep_outline.get("created_at"),
                    updated_at=ep_outline.get("updated_at")
                ))
            else:
                # 未生成的大纲
                episodes.append(EpisodeOutlineResponse(
                    episode_number=ep_num,
                    episode_title=f"第{ep_num}集",
                    episode_summary=None,
                    detailed_outline="",
                    status="pending"
                ))

        return ResponseModel(
            success=True,
            data=EpisodeOutlineListResponse(
                project_id=project.id,
                total_episodes=total_episodes,
                generated_count=generated_count,
                episodes=episodes
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取分集大纲列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))




async def get_episode_outline(
    project_id: int,
    episode: int,
    current_user: User,
    db: AsyncSession
):
    """
    获取单个分集详细大纲
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

        # 获取分集大纲
        episode_outlines = project.episode_outlines or {}
        ep_outline = episode_outlines.get(str(episode))

        if not ep_outline:
            raise ResourceNotFoundException(f"第{episode}集的详细大纲尚未生成")

        return ResponseModel(
            success=True,
            data=EpisodeOutlineResponse(
                episode_number=ep_outline.get("episode_number", episode),
                episode_title=ep_outline.get("episode_title"),
                episode_summary=ep_outline.get("episode_summary"),
                detailed_outline=ep_outline.get("detailed_outline", ""),
                estimated_duration=ep_outline.get("estimated_duration"),
                scenes=[EpisodeOutlineScene(
                    **s) for s in ep_outline.get("scenes", [])] if ep_outline.get("scenes") else None,
                core_conflict=ep_outline.get("core_conflict"),
                emotional_curve=ep_outline.get("emotional_curve"),
                key_dialogues=ep_outline.get("key_dialogues"),
                visual_highlights=ep_outline.get("visual_highlights"),
                status=ep_outline.get("status", "generated"),
                created_at=ep_outline.get("created_at"),
                updated_at=ep_outline.get("updated_at")
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取分集大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))




async def update_episode_outline(
    project_id: int,
    episode: int,
    request: EpisodeOutlineUpdate,
    current_user: User,
    db: AsyncSession
):
    """
    更新分集详细大纲

    用户可以手动编辑已生成的详细大纲，修改后的状态将标记为"edited"。
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

        # 获取现有大纲
        episode_outlines = project.episode_outlines or {}
        ep_outline = episode_outlines.get(str(episode), {})

        if not ep_outline:
            # 如果不存在，创建新的
            ep_outline = {
                "episode_number": episode,
                "episode_title": f"第{episode}集",
                "episode_summary": "",
                "detailed_outline": "",
                "status": "pending"
            }

        # 更新字段
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                if key == "scenes" and value:
                    ep_outline[key] = [s.model_dump() if hasattr(
                        s, 'model_dump') else s for s in value]
                else:
                    ep_outline[key] = value

        # 更新状态和时间
        ep_outline["status"] = "edited"
        ep_outline["updated_at"] = datetime.now().isoformat()

        # 保存
        if not project.episode_outlines:
            project.episode_outlines = {}

        # 创建新字典触发 SQLAlchemy 变更检测
        updated_outlines = dict(project.episode_outlines)
        updated_outlines[str(episode)] = ep_outline
        project.episode_outlines = updated_outlines

        # 标记字段已修改（确保 JSON 字段变更被检测）
        flag_modified(project, 'episode_outlines')

        await db.commit()
        await db.refresh(project)

        logger.info(f"第{episode}集详细大纲已更新: {project.title}")

        return ResponseModel(
            success=True,
            data=EpisodeOutlineResponse(
                episode_number=ep_outline.get("episode_number", episode),
                episode_title=ep_outline.get("episode_title"),
                episode_summary=ep_outline.get("episode_summary"),
                detailed_outline=ep_outline.get("detailed_outline", ""),
                estimated_duration=ep_outline.get("estimated_duration"),
                scenes=[EpisodeOutlineScene(
                    **s) for s in ep_outline.get("scenes", [])] if ep_outline.get("scenes") else None,
                core_conflict=ep_outline.get("core_conflict"),
                emotional_curve=ep_outline.get("emotional_curve"),
                key_dialogues=ep_outline.get("key_dialogues"),
                visual_highlights=ep_outline.get("visual_highlights"),
                status=ep_outline.get("status", "edited"),
                created_at=ep_outline.get("created_at"),
                updated_at=ep_outline.get("updated_at")
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新分集大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))




async def delete_episode_outline(
    project_id: int,
    episode: int,
    current_user: User,
    db: AsyncSession
):
    """
    删除分集详细大纲

    删除后可以重新生成。
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

        # 删除大纲
        episode_outlines = project.episode_outlines or {}
        if str(episode) in episode_outlines:
            del episode_outlines[str(episode)]
            project.episode_outlines = episode_outlines
            await db.commit()
            logger.info(f"第{episode}集详细大纲已删除: {project.title}")
            return ResponseModel(success=True, message=f"第{episode}集详细大纲已删除")
        else:
            raise ResourceNotFoundException(f"第{episode}集的详细大纲不存在")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除分集大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 数据修复端点 ====================
