"""知识库管理 - 知识库 CRUD 端点（构建、状态查询、配置更新、删除）

从 knowledge_base.py 拆分，包含：
- build_project_knowledge_base: 构建项目专属知识库
- _build_knowledge_base_task: 后台知识库构建任务
- get_knowledge_base_status: 获取构建状态
- update_knowledge_base_config: 更新知识库配置
- delete_project_knowledge_base: 删除知识库

共享 novel_writer/utils.py 的 router
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, BackgroundTasks
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

from ..utils import router, settings, logger


@router.post("/projects/{project_id}/build-knowledge-base")
async def build_project_knowledge_base(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    [已废弃] 构建项目专属知识库
    
    ⚠️ 此端点已废弃，不作为前端功能暴露。
    知识图谱应从四阶段流程（创意生成）构建后，通过项目创建API的
    `inherit_kb_from_project_id` 字段继承。
    
    保留此端点仅作为内部回退和调试用途。
    
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

        # 检查是否正在构建中（同时检测幽灵状态）
        is_stale_build = False
        if project.kb_status == "building":
            # 幽灵状态检测：检查进度更新时间
            progress_info = project.kb_build_progress or {}
            updated_at_str = progress_info.get("updated_at") or progress_info.get("started_at")
            
            if updated_at_str:
                try:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    # 如果超过30分钟没有更新，认为是幽灵状态
                    stale_threshold = timedelta(minutes=30)
                    if datetime.now() - updated_at > stale_threshold:
                        is_stale_build = True
                        logger.warning(
                            f"检测到知识库构建幽灵状态，自动重置: project_id={project_id}, last_update={updated_at_str}")
                except Exception as e:
                    logger.warning(f"解析进度时间戳失败: {e}")
            else:
                # 没有时间戳信息，检查项目更新时间
                if project.updated_at:
                    stale_threshold = timedelta(hours=1)
                    if datetime.now() - project.updated_at > stale_threshold:
                        is_stale_build = True
                        logger.warning(
                            f"检测到知识库构建幽灵状态（无进度时间戳）: project_id={project_id}")
            
            # 如果不是幽灵状态，则拒绝请求
            if not is_stale_build:
                raise ValidationException("知识库正在构建中，请稍后再试")
            
            # 幽灵状态：自动重置为pending，允许重新构建
            logger.info(f"幽灵状态已重置，允许重新构建: project_id={project_id}")

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
    """后台执行知识库构建任务（P1增强：进度细分+预估时间）"""
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.agents.llm_manager import llm_manager
    from app.core.database import async_session_maker
    import time

    start_time = time.time()
    estimated_total_seconds = 60  # 预估总耗时60秒

    async with async_session_maker() as db:
        try:
            # 获取项目
            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                logger.error(f"知识库构建失败: 项目不存在 project_id={project_id}")
                return

            # 阶段1: 初始化 (5%)
            project.kb_build_progress = {
                "stage": "initializing",
                "progress": 5,
                "message": "正在初始化知识库...",
                "started_at": datetime.now().isoformat(),
                "estimated_remaining": "约60秒"
            }
            await db.commit()

            # 初始化知识库管理器
            kb_manager = ProjectKnowledgeBase(db=db)

            # 阶段2: 解析大纲 (15%)
            elapsed = time.time() - start_time
            remaining = max(5, int(estimated_total_seconds - elapsed))
            project.kb_build_progress = {
                "stage": "parsing_outline",
                "progress": 15,
                "message": "正在解析大纲结构...",
                "started_at": project.kb_build_progress.get("started_at"),
                "estimated_remaining": f"约{remaining}秒"
            }
            await db.commit()

            # 获取LLM提供者
            llm_provider = None
            if graphrag_enabled:
                try:
                    llm_provider = await llm_manager.get_provider_from_db(db, project.user_id)
                except Exception as e:
                    logger.warning(f"获取LLM提供者失败，将使用规则提取: {str(e)}")

            # 阶段3: 提取人物 (30%)
            elapsed = time.time() - start_time
            remaining = max(5, int(estimated_total_seconds - elapsed))
            project.kb_build_progress = {
                "stage": "extracting_characters",
                "progress": 30,
                "message": "正在提取人物设定...",
                "started_at": project.kb_build_progress.get("started_at"),
                "estimated_remaining": f"约{remaining}秒"
            }
            await db.commit()

            # 阶段4: 提取世界观 (50%)
            elapsed = time.time() - start_time
            remaining = max(5, int(estimated_total_seconds - elapsed))
            project.kb_build_progress = {
                "stage": "extracting_world",
                "progress": 50,
                "message": "正在提取世界观设定...",
                "started_at": project.kb_build_progress.get("started_at"),
                "estimated_remaining": f"约{remaining}秒"
            }
            await db.commit()

            # 阶段5: 提取关系 (70%)
            elapsed = time.time() - start_time
            remaining = max(5, int(estimated_total_seconds - elapsed))
            project.kb_build_progress = {
                "stage": "extracting_relations",
                "progress": 70,
                "message": "正在构建人物关系网络...",
                "started_at": project.kb_build_progress.get("started_at"),
                "estimated_remaining": f"约{remaining}秒"
            }
            await db.commit()

            # 构建全局大纲图谱
            build_result = await kb_manager.build_global_outline_graph(
                project_id=project_id,
                outline_content=outline_content,
                llm_provider=llm_provider
            )

            # 阶段6: 构建索引 (85%)
            elapsed = time.time() - start_time
            remaining = max(3, int(estimated_total_seconds - elapsed))
            project.kb_build_progress = {
                "stage": "building_index",
                "progress": 85,
                "message": "正在优化知识图谱索引...",
                "started_at": project.kb_build_progress.get("started_at"),
                "estimated_remaining": f"约{remaining}秒"
            }
            await db.commit()

            if build_result["success"]:
                # 阶段7: 完成 (100%)
                elapsed = time.time() - start_time
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
                    "completed_at": datetime.now().isoformat(),
                    "elapsed_seconds": int(elapsed),
                    "estimated_remaining": "已完成"
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


@router.post("/projects/{project_id}/knowledge-base/reset-status")
async def reset_knowledge_base_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    重置知识库构建状态（用于清除幽灵状态）

    当知识库构建任务异常中断或服务器重启导致状态卡在 "building" 时，
    可以通过此API手动重置状态为 "pending"，允许重新发起构建。
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

        previous_status = project.kb_status or "pending"

        # 只有当状态为 building 或 failed 时才允许重置
        if previous_status not in ["building", "failed"]:
            raise ValidationException(
                f"当前状态为 '{previous_status}'，无需重置"
            )

        # 重置状态
        project.kb_status = "pending"
        project.kb_build_progress = None
        await db.commit()

        logger.info(
            f"知识库状态已重置: project_id={project_id}, {previous_status} → pending")

        return ResponseModel(
            success=True,
            message="知识库状态已重置",
            data={
                "previous_status": previous_status,
                "new_status": "pending"
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"重置知识库状态失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))
