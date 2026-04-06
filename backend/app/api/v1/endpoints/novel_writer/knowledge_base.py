"""
小说/剧本正文生成 API 端点 - 知识库管理模块

包含项目专属知识库构建、单元图谱构建、知识图谱获取等功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import (
    ResourceNotFoundException, ValidationException, KnowledgeBaseException,
    AppException, ErrorCode
)

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject
from app.schemas.common import ResponseModel

from .utils import router, settings, logger


# ==================== 项目专属知识库端点 ====================

@router.post("/projects/{project_id}/build-knowledge-base")
async def build_project_knowledge_base(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    构建项目专属知识库

    执行流程：
    1. 解析全局大纲内容
    2. 使用GraphRAG生成知识图谱
    3. 存入项目专属向量数据库

    该操作在后台异步执行，可通过 get-knowledge-base-status 查询进度
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查是否有大纲内容
        if not project.outline_content:
            raise ValidationException("项目没有大纲内容，无法构建知识库")

        # 检查是否正在构建中
        if project.kb_status == "building":
            raise ValidationException("知识库正在构建中，请稍后再试")

        # 更新状态为构建中
        project.kb_status = "building"
        project.kb_build_progress = {
            "stage": "initializing",
            "progress": 0,
            "message": "正在初始化知识库...",
            "started_at": datetime.now().isoformat()
        }
        await db.commit()

        # 添加后台任务
        background_tasks.add_task(
            _build_knowledge_base_task,
            project_id=project_id,
            outline_content=project.outline_content,
            graphrag_enabled=project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True
        )

        return ResponseModel(
            success=True,
            message="知识库构建任务已启动，请稍后查询进度",
            data={
                "project_id": project_id,
                "status": "building"
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"启动知识库构建失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


async def _build_knowledge_base_task(
    project_id: int,
    outline_content: str,
    graphrag_enabled: bool
):
    """后台执行知识库构建任务"""
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.agents.llm_manager import llm_manager
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
        try:
            # 获取项目
            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                logger.error(f"知识库构建失败: 项目不存在 project_id={project_id}")
                return

            # 更新进度
            project.kb_build_progress = {
                "stage": "initializing",
                "progress": 10,
                "message": "正在初始化知识库...",
                "started_at": datetime.now().isoformat()
            }
            await db.commit()

            # 初始化知识库管理器
            kb_manager = ProjectKnowledgeBase(db=db)

            # 获取LLM提供者
            llm_provider = None
            if graphrag_enabled:
                try:
                    llm_provider = await llm_manager.get_provider_from_db(db, project.user_id)
                except Exception as e:
                    logger.warning(f"获取LLM提供者失败，将使用规则提取: {str(e)}")

            # 更新进度
            project.kb_build_progress = {
                "stage": "extracting_entities",
                "progress": 30,
                "message": "正在提取实体和关系...",
                "started_at": project.kb_build_progress.get("started_at")
            }
            await db.commit()

            # 构建全局大纲图谱
            build_result = await kb_manager.build_global_outline_graph(
                project_id=project_id,
                outline_content=outline_content,
                llm_provider=llm_provider
            )

            if build_result["success"]:
                # 更新项目状态
                project.kb_status = "ready"
                project.project_kb_collection = kb_manager.get_collection_name(
                    project_id)
                project.global_outline_graph_path = build_result["graph_path"]
                project.kb_build_progress = {
                    "stage": "completed",
                    "progress": 100,
                    "message": "知识库构建完成",
                    "entity_count": build_result["entity_count"],
                    "relation_count": build_result["relation_count"],
                    "started_at": project.kb_build_progress.get("started_at"),
                    "completed_at": datetime.now().isoformat()
                }

                logger.info(
                    f"知识库构建完成: project_id={project_id}, "
                    f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                )
            else:
                raise Exception(build_result.get("error", "未知错误"))

            await db.commit()

        except Exception as e:
            logger.error(f"知识库构建任务失败: project_id={project_id}, error={str(e)}")

            # 更新失败状态
            try:
                query = select(NovelProject).where(
                    NovelProject.id == project_id)
                result = await db.execute(query)
                project = result.scalar_one_or_none()
                if project:
                    project.kb_status = "failed"
                    project.kb_build_progress = {
                        "stage": "failed",
                        "progress": 0,
                        "message": f"构建失败: {str(e)}",
                        "error": str(e),
                        "started_at": project.kb_build_progress.get("started_at") if project.kb_build_progress else None,
                        "failed_at": datetime.now().isoformat()
                    }
                    await db.commit()
            except Exception as update_error:
                logger.error(f"更新失败状态时出错: {str(update_error)}")


@router.get("/projects/{project_id}/knowledge-base-status")
async def get_knowledge_base_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目知识库构建状态

    返回：
    - status: pending/building/ready/failed
    - progress: 构建进度信息
    - stats: 知识库统计信息
    - is_stale: 状态是否过时（幽灵状态检测）
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        stats = kb_manager.get_kb_stats(project_id)

        # 幽灵状态检测：检查构建任务是否真正在运行
        is_stale = False
        current_status = project.kb_status or "pending"

        if current_status == "building":
            # 检查进度更新时间，判断是否为幽灵状态
            progress_info = project.kb_build_progress or {}
            updated_at_str = progress_info.get(
                "updated_at") or progress_info.get("started_at")

            if updated_at_str:
                try:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    # 如果超过30分钟没有更新，认为是幽灵状态
                    stale_threshold = timedelta(minutes=30)
                    if datetime.now() - updated_at > stale_threshold:
                        is_stale = True
                        logger.warning(
                            f"检测到知识库构建幽灵状态: project_id={project_id}, last_update={updated_at_str}")
                except Exception as e:
                    logger.warning(f"解析进度时间戳失败: {e}")
            else:
                # 没有时间戳信息，检查是否超过1小时（从项目更新时间判断）
                if project.updated_at:
                    stale_threshold = timedelta(hours=1)
                    if datetime.now() - project.updated_at > stale_threshold:
                        is_stale = True
                        logger.warning(
                            f"检测到知识库构建幽灵状态（无进度时间戳）: project_id={project_id}")

        return ResponseModel(
            success=True,
            data={
                "status": current_status,
                "progress": project.kb_build_progress,
                "graphrag_enabled": project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True,
                "collection_name": project.project_kb_collection,
                "stats": stats,
                "is_stale": is_stale  # 前端可用于判断是否需要重置
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取知识库状态失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/knowledge-graph")
async def get_project_knowledge_graph(
    project_id: int,
    unit_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目知识图谱数据（用于可视化）

    参数：
    - unit_number: 单元号，不传则返回全局大纲图谱

    返回：
    - nodes: 节点列表
    - edges: 边列表
    - stats: 统计信息
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_data = kb_manager.get_knowledge_graph_data(
            project_id, unit_number)

        return ResponseModel(
            success=True,
            data=graph_data
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/projects/{project_id}/build-unit-knowledge-graph")
async def build_unit_knowledge_graph(
    project_id: int,
    unit_number: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    构建单元大纲的知识图谱

    在单元大纲生成完成后调用，将该单元的大纲内容存入知识库

    参数：
    - unit_number: 单元号（章节号/集数/场景号）
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取单元大纲内容
        content_type = project.content_type or "novel"
        unit_outline_content = None

        if content_type == "novel":
            chapter_outlines = project.chapter_outlines or {}
            unit_outline = chapter_outlines.get(str(unit_number), {})
            unit_outline_content = unit_outline.get(
                "detailed_outline") or unit_outline.get("chapter_summary")
        elif content_type == "series_script":
            episode_outlines = project.episode_outlines or {}
            unit_outline = episode_outlines.get(str(unit_number), {})
            unit_outline_content = unit_outline.get(
                "detailed_outline") or unit_outline.get("episode_summary")
        elif content_type == "movie_script":
            scene_outlines = project.scene_outlines or {}
            unit_outline = scene_outlines.get(str(unit_number), {})
            unit_outline_content = unit_outline.get(
                "detailed_outline") or unit_outline.get("scene_summary")

        if not unit_outline_content:
            raise ValidationException(f"单元 {unit_number} 没有详细大纲内容")

        # 添加后台任务
        background_tasks.add_task(
            _build_unit_knowledge_graph_task,
            project_id=project_id,
            unit_number=unit_number,
            unit_outline_content=unit_outline_content,
            graphrag_enabled=project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True,
            user_id=project.user_id
        )

        return ResponseModel(
            success=True,
            message=f"单元 {unit_number} 知识图谱构建任务已启动",
            data={
                "project_id": project_id,
                "unit_number": unit_number,
                "status": "building"
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"启动单元知识图谱构建失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


async def _build_unit_knowledge_graph_task(
    project_id: int,
    unit_number: int,
    unit_outline_content: str,
    graphrag_enabled: bool,
    user_id: int
):
    """后台执行单元知识图谱构建任务"""
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.agents.llm_manager import llm_manager
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
        try:
            # 初始化知识库管理器
            kb_manager = ProjectKnowledgeBase(db=db)

            # 获取LLM提供者
            llm_provider = None
            if graphrag_enabled:
                try:
                    llm_provider = await llm_manager.get_provider_from_db(db, user_id)
                except Exception as e:
                    logger.warning(f"获取LLM提供者失败，将使用规则提取: {str(e)}")

            # 构建单元图谱
            build_result = await kb_manager.build_unit_outline_graph(
                project_id=project_id,
                unit_number=unit_number,
                unit_outline_content=unit_outline_content,
                llm_provider=llm_provider
            )

            if build_result["success"]:
                logger.info(
                    f"单元知识图谱构建完成: project_id={project_id}, unit={unit_number}, "
                    f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                )
            else:
                logger.error(
                    f"单元知识图谱构建失败: project_id={project_id}, unit={unit_number}, "
                    f"error={build_result.get('error')}"
                )

        except Exception as e:
            logger.error(
                f"单元知识图谱构建任务失败: project_id={project_id}, unit={unit_number}, error={str(e)}")


@router.post("/projects/{project_id}/build-all-unit-graphs")
async def build_all_unit_knowledge_graphs(
    project_id: int,
    unit_numbers: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量构建单元大纲的知识图谱

    参数：
    - unit_numbers: 可选，要构建的单元号列表，逗号分隔（如 "1,2,3"）。不传则构建所有单元。

    返回：
    - 启动的任务信息和待构建单元列表
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")
        if project.kb_status != "ready":
            raise ValidationException("请先构建全局知识库")

        # 获取单元大纲列表
        content_type = project.content_type or "novel"
        unit_outlines = {}
        if content_type == "novel":
            unit_outlines = project.chapter_outlines or {}
        elif content_type == "series_script":
            unit_outlines = project.episode_outlines or {}
        elif content_type == "movie_script":
            unit_outlines = project.scene_outlines or {}

        # 确定要构建的单元
        if unit_numbers:
            # 解析用户指定的单元号
            target_units = [int(u.strip())
                            for u in unit_numbers.split(",") if u.strip().isdigit()]
        else:
            # 构建所有有详细大纲的单元
            target_units = []
            for unit_num, outline in unit_outlines.items():
                detailed = outline.get("detailed_outline") or outline.get(
                    "chapter_summary") or outline.get("episode_summary") or outline.get("scene_summary")
                if detailed:
                    target_units.append(int(unit_num))

        target_units.sort()

        if not target_units:
            return ResponseModel(
                success=False,
                message="没有找到可构建的单元大纲",
                data={"units_to_build": []}
            )

        # 添加后台任务
        background_tasks.add_task(
            _build_all_unit_graphs_task,
            project_id=project_id,
            unit_numbers=target_units,
            unit_outlines=unit_outlines,
            graphrag_enabled=project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True,
            user_id=project.user_id
        )

        return ResponseModel(
            success=True,
            message=f"已启动 {len(target_units)} 个单元图谱构建任务",
            data={
                "project_id": project_id,
                "units_to_build": target_units,
                "total_count": len(target_units),
                "status": "building"
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"启动批量单元图谱构建失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


async def _build_all_unit_graphs_task(
    project_id: int,
    unit_numbers: List[int],
    unit_outlines: Dict[str, Any],
    graphrag_enabled: bool,
    user_id: int
):
    """后台执行批量单元知识图谱构建任务"""
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.agents.llm_manager import llm_manager
    from app.core.database import async_session_maker
    from app.services.task_manager import task_manager

    async with async_session_maker() as db:
        try:
            # 初始化知识库管理器
            kb_manager = ProjectKnowledgeBase(db=db)

            # 获取LLM提供者
            llm_provider = None
            if graphrag_enabled:
                try:
                    llm_provider = await llm_manager.get_provider_from_db(db, user_id)
                except Exception as e:
                    logger.warning(f"获取LLM提供者失败: {str(e)}")

            # 创建任务追踪
            await task_manager.create_task(
                project_id, "unit_graph_build",
                total_count=len(unit_numbers)
            )

            success_count = 0
            failed_count = 0

            for i, unit_number in enumerate(unit_numbers):
                # 更新任务进度
                await task_manager.update_task_progress(
                    project_id, "unit_graph_build",
                    completed=i,
                    current_item=f"第{unit_number}单元"
                )

                # 获取单元大纲内容
                outline = unit_outlines.get(str(unit_number), {})
                unit_content = outline.get("detailed_outline") or \
                    outline.get("chapter_summary") or \
                    outline.get("episode_summary") or \
                    outline.get("scene_summary")

                if not unit_content:
                    logger.warning(
                        f"单元 {unit_number} 没有大纲内容，跳过")
                    failed_count += 1
                    continue

                try:
                    build_result = await kb_manager.build_unit_outline_graph(
                        project_id=project_id,
                        unit_number=unit_number,
                        unit_outline_content=unit_content,
                        llm_provider=llm_provider
                    )

                    if build_result["success"]:
                        logger.info(
                            f"单元图谱构建完成: project_id={project_id}, unit={unit_number}, "
                            f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                        )
                        success_count += 1
                    else:
                        logger.error(
                            f"单元图谱构建失败: project_id={project_id}, unit={unit_number}, "
                            f"error={build_result.get('error')}"
                        )
                        failed_count += 1

                except Exception as e:
                    logger.error(
                        f"单元图谱构建异常: project_id={project_id}, unit={unit_number}, error={str(e)}")
                    failed_count += 1

                # 每个单元之间稍作等待，避免API限流
                await asyncio.sleep(1)

            # 任务完成
            await task_manager.complete_task(project_id, "unit_graph_build")

            logger.info(
                f"批量单元图谱构建完成: project_id={project_id}, "
                f"success={success_count}, failed={failed_count}"
            )

        except Exception as e:
            logger.error(
                f"批量单元图谱构建任务失败: project_id={project_id}, error={str(e)}")


@router.get("/projects/{project_id}/unit-graphs-status")
async def get_unit_graphs_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目单元图谱状态

    返回所有单元的图谱构建状态，包括：
    - 已构建的单元列表
    - 未构建的单元列表
    - 各单元图谱的统计信息
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_dir = kb_manager.settings.get_knowledge_graph_dir()

        # 获取单元大纲列表
        content_type = project.content_type or "novel"
        unit_outlines = {}
        if content_type == "novel":
            unit_outlines = project.chapter_outlines or {}
        elif content_type == "series_script":
            unit_outlines = project.episode_outlines or {}
        elif content_type == "movie_script":
            unit_outlines = project.scene_outlines or {}

        # 检查各单元图谱状态
        built_units = []
        unbuilt_units = []

        for unit_num, outline in unit_outlines.items():
            unit_number = int(unit_num)
            has_outline = bool(
                outline.get("detailed_outline") or
                outline.get("chapter_summary") or
                outline.get("episode_summary") or
                outline.get("scene_summary")
            )

            graph_path = kb_manager.get_graph_path(project_id, unit_number)
            has_graph = os.path.exists(graph_path)

            unit_info = {
                "unit_number": unit_number,
                "has_outline": has_outline,
                "has_graph": has_graph
            }

            if has_graph:
                # 获取图谱统计
                try:
                    graph_data = kb_manager.get_knowledge_graph_data(
                        project_id, unit_number)
                    unit_info["node_count"] = graph_data.get(
                        "stats", {}).get("node_count", 0)
                    unit_info["edge_count"] = graph_data.get(
                        "stats", {}).get("edge_count", 0)
                except Exception as e:
                    logger.warning(f"获取图谱数据失败: {e}")
                    unit_info["node_count"] = 0
                    unit_info["edge_count"] = 0
                built_units.append(unit_info)
            elif has_outline:
                unbuilt_units.append(unit_info)

        # 排序
        built_units.sort(key=lambda x: x["unit_number"])
        unbuilt_units.sort(key=lambda x: x["unit_number"])

        return ResponseModel(
            success=True,
            data={
                "project_id": project_id,
                "total_units": len(unit_outlines),
                "built_count": len(built_units),
                "unbuilt_count": len(unbuilt_units),
                "built_units": built_units,
                "unbuilt_units": unbuilt_units
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取单元图谱状态失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.put("/projects/{project_id}/knowledge-base-config")
async def update_knowledge_base_config(
    project_id: int,
    graphrag_enabled: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新项目知识库配置

    参数：
    - graphrag_enabled: 是否启用GraphRAG
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if graphrag_enabled is not None:
            project.kb_graphrag_enabled = graphrag_enabled

        await db.commit()

        return ResponseModel(
            success=True,
            message="知识库配置已更新",
            data={
                "graphrag_enabled": project.kb_graphrag_enabled
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新知识库配置失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/knowledge-base")
async def delete_project_knowledge_base(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除项目知识库

    删除向量数据库和知识图谱文件，重置知识库状态
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        success = await kb_manager.delete_project_kb(project_id)

        if success:
            # 重置项目知识库状态
            project.kb_status = "pending"
            project.project_kb_collection = None
            project.global_outline_graph_path = None
            project.kb_build_progress = None
            await db.commit()

            return ResponseModel(
                success=True,
                message="知识库已删除"
            )
        else:
            raise KnowledgeBaseException("删除知识库失败")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除知识库失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 一致性检查报告端点 ====================

@router.get("/projects/{project_id}/consistency-report")
async def get_consistency_report(
    project_id: int,
    unit_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目一致性检查报告

    返回当前项目的知识图谱一致性状态，包括：
    - 人物状态摘要（身份、位置、关系、能力、心理状态等）
    - 设施状态摘要（运营状态、归属、物理状态等）
    - 未完成事件跟踪
    - 群体组织动态
    - 道具归属情况
    - 待回收伏笔提醒
    - 世界规则约束
    - 一致性警告和潜在冲突点

    参数：
    - unit_number: 单元号（章节号/集数/场景号），不传则返回全局一致性状态

    返回：
    - chapter: 当前章节号
    - character_states: 人物状态摘要
    - facility_states: 设施状态摘要
    - unfinished_events: 未完成事件列表
    - group_states: 群体动态
    - item_ownership: 道具归属情况
    - pending_foreshadows: 待回收伏笔
    - active_rules: 世界规则约束
    - time_context: 时间上下文
    - consistency_warnings: 一致性警告
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查知识库状态
        if project.kb_status != "ready":
            return ResponseModel(
                success=True,
                data={
                    "status": "not_ready",
                    "kb_status": project.kb_status,
                    "message": "知识库尚未构建完成，请先构建知识库",
                    "chapter": unit_number,
                    "character_states": {},
                    "facility_states": {},
                    "unfinished_events": [],
                    "group_states": {},
                    "item_ownership": {},
                    "pending_foreshadows": [],
                    "active_rules": [],
                    "time_context": {},
                    "consistency_warnings": []
                }
            )

        # 加载知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number or 1)

        if not graph_path or not os.path.exists(graph_path):
            # 尝试获取全局图谱
            graph_path = project.global_outline_graph_path
            if not graph_path or not os.path.exists(graph_path):
                return ResponseModel(
                    success=True,
                    data={
                        "status": "no_graph",
                        "message": "知识图谱文件不存在",
                        "chapter": unit_number,
                        "character_states": {},
                        "facility_states": {},
                        "unfinished_events": [],
                        "group_states": {},
                        "item_ownership": {},
                        "pending_foreshadows": [],
                        "active_rules": [],
                        "time_context": {},
                        "consistency_warnings": []
                    }
                )

        # 加载知识图谱并获取一致性报告
        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        consistency_report = knowledge_graph.get_consistency_report(
            unit_number)

        # 添加项目基础信息
        consistency_report["project_id"] = project_id
        consistency_report["project_title"] = project.title
        consistency_report["status"] = "ready"

        return ResponseModel(
            success=True,
            data=consistency_report
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取一致性报告失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/character-states")
async def get_character_states(
    project_id: int,
    unit_number: Optional[int] = None,
    character_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取人物状态详情

    返回指定人物或所有人物的状态信息，包括：
    - 身份变化
    - 位置变化
    - 关系变化
    - 能力成长
    - 心理状态

    参数：
    - unit_number: 单元号，不传则返回全部
    - character_name: 角色名称，不传则返回所有角色
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查知识库状态
        if project.kb_status != "ready":
            return ResponseModel(
                success=True,
                data={
                    "status": "not_ready",
                    "message": "知识库尚未构建完成",
                    "character_states": {}
                }
            )

        # 加载知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number or 1)

        if not graph_path or not os.path.exists(graph_path):
            graph_path = project.global_outline_graph_path

        if not graph_path or not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={
                    "status": "no_graph",
                    "message": "知识图谱文件不存在",
                    "character_states": {}
                }
            )

        # 加载知识图谱
        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        # 获取人物状态实体
        state_entities = knowledge_graph.get_character_state_entities(
            chapter_num=unit_number)

        # 如果指定了角色名称，过滤结果
        if character_name:
            filtered_entities = {
                "identity_changes": [],
                "location_changes": [],
                "relationship_changes": [],
                "ability_growth": [],
                "mental_states": []
            }
            for category in filtered_entities:
                for entity in state_entities.get(category, []):
                    if entity.get("character") == character_name:
                        filtered_entities[category].append(entity)
            state_entities = filtered_entities

        return ResponseModel(
            success=True,
            data={
                "status": "ready",
                "unit_number": unit_number,
                "character_name": character_name,
                "character_states": state_entities
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取人物状态失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/extended-entities")
async def get_extended_entities(
    project_id: int,
    unit_number: Optional[int] = None,
    entity_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取扩展实体状态

    返回扩展实体的状态信息，包括：
    - 设施状态
    - 事件进展
    - 群体动态
    - 道具归属
    - 世界规则
    - 时间线
    - 伏笔线索

    参数：
    - unit_number: 单元号，不传则返回全部
    - entity_type: 实体类型，可选值：facility/event/group/item/rule/timeline/foreshadow
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查知识库状态
        if project.kb_status != "ready":
            return ResponseModel(
                success=True,
                data={
                    "status": "not_ready",
                    "message": "知识库尚未构建完成",
                    "entities": {}
                }
            )

        # 加载知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number or 1)

        if not graph_path or not os.path.exists(graph_path):
            graph_path = project.global_outline_graph_path

        if not graph_path or not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={
                    "status": "no_graph",
                    "message": "知识图谱文件不存在",
                    "entities": {}
                }
            )

        # 加载知识图谱
        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        # 获取扩展实体
        extended_entities = knowledge_graph.get_extended_state_entities(
            chapter_num=unit_number)

        # 根据entity_type过滤
        if entity_type:
            type_mapping = {
                "facility": ["facilities", "facility_states"],
                "event": ["events", "event_states"],
                "group": ["groups", "group_members"],
                "item": ["items", "item_ownerships", "item_states"],
                "rule": ["world_rules"],
                "timeline": ["time_nodes", "time_flows"],
                "foreshadow": ["foreshadows", "foreshadow_resolutions"]
            }
            keys = type_mapping.get(entity_type, [])
            filtered_entities = {k: v for k,
                                 v in extended_entities.items() if k in keys}
            extended_entities = filtered_entities

        return ResponseModel(
            success=True,
            data={
                "status": "ready",
                "unit_number": unit_number,
                "entity_type": entity_type,
                "entities": extended_entities
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取扩展实体失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/projects/{project_id}/check-content-consistency")
async def check_content_consistency(
    project_id: int,
    content: str,
    unit_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    检查内容一致性

    对指定内容进行一致性检查，返回与知识图谱中已有信息的冲突点。

    参数：
    - content: 待检查的内容
    - unit_number: 当前单元号

    返回：
    - is_consistent: 是否一致
    - conflicts: 冲突点列表
    - suggestions: 修正建议
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查知识库状态
        if project.kb_status != "ready":
            return ResponseModel(
                success=True,
                data={
                    "status": "not_ready",
                    "is_consistent": True,
                    "conflicts": [],
                    "suggestions": [],
                    "message": "知识库尚未构建，跳过一致性检查"
                }
            )

        # 加载知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number or 1)

        if not graph_path or not os.path.exists(graph_path):
            graph_path = project.global_outline_graph_path

        if not graph_path or not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={
                    "status": "no_graph",
                    "is_consistent": True,
                    "conflicts": [],
                    "suggestions": [],
                    "message": "知识图谱不存在，跳过一致性检查"
                }
            )

        # 加载知识图谱
        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        # 获取一致性报告作为参考
        consistency_report = knowledge_graph.get_consistency_report(
            unit_number)

        # 简单的一致性检查逻辑（可扩展为LLM辅助检查）
        conflicts = []
        suggestions = []

        # 检查人物状态冲突
        for char_name, state in consistency_report.get("character_states", {}).items():
            if char_name in content:
                # 检查位置冲突
                latest_location = state.get("latest_location")
                if latest_location and latest_location not in content:
                    conflicts.append({
                        "type": "character_location",
                        "character": char_name,
                        "expected": latest_location,
                        "description": f"角色'{char_name}'当前位置应为'{latest_location}'，但内容中未体现"
                    })
                    suggestions.append(f"建议确认角色'{char_name}'的位置是否正确")

        # 检查设施状态冲突
        for facility_name, state in consistency_report.get("facility_states", {}).items():
            if facility_name in content:
                facility_status = state.get("status")
                if facility_status in ["关闭", "暂停营业", "损坏"]:
                    conflicts.append({
                        "type": "facility_status",
                        "facility": facility_name,
                        "status": facility_status,
                        "description": f"设施'{facility_name}'当前状态为'{facility_status}'，请注意一致性"
                    })

        # 检查道具归属冲突
        for item_name, state in consistency_report.get("item_ownership", {}).items():
            if item_name in content:
                owner = state.get("owner")
                status = state.get("status")
                if status in ["丢失", "损坏", "销毁"]:
                    conflicts.append({
                        "type": "item_status",
                        "item": item_name,
                        "status": status,
                        "description": f"道具'{item_name}'当前状态为'{status}'，请注意一致性"
                    })

        # 添加待回收伏笔提醒
        for foreshadow in consistency_report.get("pending_foreshadows", []):
            suggestions.append({
                "type": "foreshadow_reminder",
                "name": foreshadow.get("name"),
                "importance": foreshadow.get("importance"),
                "planted_chapter": foreshadow.get("planted_chapter"),
                "description": f"待回收伏笔: {foreshadow.get('name')} (第{foreshadow.get('planted_chapter', '?')}章)"
            })

        is_consistent = len(conflicts) == 0

        return ResponseModel(
            success=True,
            data={
                "status": "ready",
                "is_consistent": is_consistent,
                "conflicts": conflicts,
                "suggestions": suggestions,
                "warnings": consistency_report.get("consistency_warnings", []),
                "unit_number": unit_number
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"检查内容一致性失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/character-profile-history")
async def get_character_profile_history(
    project_id: int,
    character_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取人物设定变更历史

    返回人物设定在写作过程中的变更历史，包括：
    - 身份变化历史
    - 位置变化历史
    - 性格发展记录
    - 与初始设定的偏差

    参数：
    - character_name: 人物名称，不传则返回所有人物
    """
    try:
        # 查询项目
        result = await db.execute(
            select(NovelProject).where(NovelProject.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 加载全局知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number=None)

        if not graph_path or not os.path.exists(graph_path):
            graph_path = project.global_outline_graph_path

        if not graph_path or not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={
                    "status": "no_graph",
                    "message": "全局知识图谱不存在",
                    "profiles": []
                }
            )

        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        # 从图谱中提取人物设定及其变更历史
        profiles = []
        graph = knowledge_graph.graph

        for node_id, node_data in graph.nodes(data=True):
            if node_data.get("type") == "人物设定":
                char_name = node_data.get("text", "")

                # 如果指定了人物名称，过滤
                if character_name and char_name != character_name:
                    continue

                attributes = node_data.get("attributes", {})

                # 构建变更历史
                change_history = []
                for key in ["身份", "位置", "性格特点"]:
                    history_key = f"{key}_变更历史"
                    if history_key in attributes:
                        for change in attributes[history_key]:
                            change_history.append({
                                "attribute": key,
                                "chapter": change.get("chapter"),
                                "old_value": change.get("old_value"),
                                "new_value": change.get("new_value")
                            })

                # 按章节排序
                change_history.sort(key=lambda x: x.get("chapter", 0))

                profile_info = {
                    "name": char_name,
                    "description": node_data.get("description", ""),
                    "current_identity": attributes.get("身份", ""),
                    "current_location": attributes.get("当前位置", attributes.get("初始位置", "")),
                    "personality": attributes.get("性格特点", ""),
                    "background": attributes.get("背景故事", ""),
                    "first_appearance": node_data.get("first_appearance_chapter"),
                    "last_updated": node_data.get("last_updated_chapter"),
                    "change_history": change_history,
                    "性格发展记录": attributes.get("性格发展记录", [])
                }

                profiles.append(profile_info)

        return ResponseModel(
            success=True,
            data={
                "status": "ready",
                "character_name": character_name,
                "profiles": profiles,
                "total_count": len(profiles)
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取人物设定变更历史失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))
