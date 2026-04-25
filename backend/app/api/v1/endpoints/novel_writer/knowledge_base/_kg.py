"""知识库管理 - 知识图谱端点（获取、构建单元图谱、批量构建）

从 knowledge_base.py 拆分，包含：
- get_project_knowledge_graph: 获取项目知识图谱数据
- build_unit_knowledge_graph: 构建单元大纲知识图谱
- _build_unit_knowledge_graph_task: 后台单元图谱构建任务
- build_all_unit_knowledge_graphs: 批量构建单元图谱
- _build_all_unit_graphs_task: 后台批量构建任务
- get_unit_graphs_status: 获取单元图谱状态

共享 novel_writer/utils.py 的 router
"""
import os
import asyncio
from typing import Optional, List, Dict, Any

from fastapi import Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import (
    ResourceNotFoundException, ValidationException,
    AppException, ErrorCode
)
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject
from app.schemas.common import ResponseModel

from ..utils import router, settings, logger


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
