"""
写作任务 API - 任务CRUD端点

@date: 2026-04-24
@version: v3.1.0 (从writing_tasks.py拆分)
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from app.core.database import get_db
from app.core.logger import get_logger
from app.api.deps import get_current_user
from app.models import User
from app.models.writing_task import WritingTask, TaskStatus
from app.models.writing_unit import WritingUnit
from app.schemas.common import ResponseModel
from app.schemas.writing_task import (
    WritingTaskCreate, WritingTaskResponse, WritingTaskListResponse,
    WritingTaskDetailResponse,
)

from ._common import _build_task_response, _build_unit_response
from ._pipeline import _start_pipeline

logger = get_logger("writing_tasks")


def register_crud_routes(router: APIRouter):
    """注册任务CRUD路由"""

    @router.post("", response_model=ResponseModel[WritingTaskResponse])
    async def create_task(
        request: WritingTaskCreate,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        创建写作任务

        创建任务后自动启动Pipeline进行异步生成。
        通过WebSocket `/api/v1/writing-tasks/{task_id}/ws` 接收实时进度。
        """
        try:
            # 检查项目是否存在且属于当前用户
            from app.models.novel_project import NovelProject
            from app.models.novel_chapter import NovelChapter

            project_result = await db.execute(
                select(NovelProject).where(
                    and_(NovelProject.id == request.project_id,
                         NovelProject.user_id == current_user.id)
                )
            )
            project = project_result.scalar_one_or_none()
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="项目不存在或无权限访问"
                )

            # 计算项目的实际单元数
            # 优先从 unit_summaries (JSON字段) 获取，否则从 NovelChapter 表查询
            actual_unit_count = 0
            if project.unit_summaries and isinstance(project.unit_summaries, dict):
                actual_unit_count = len(project.unit_summaries)

            if actual_unit_count == 0:
                # 从 NovelChapter 表查询章节数
                chapter_count_result = await db.execute(
                    select(func.count(NovelChapter.id)).where(
                        NovelChapter.project_id == request.project_id
                    )
                )
                actual_unit_count = chapter_count_result.scalar() or 0

            if actual_unit_count == 0:
                # 兜底：使用项目的 total_chapters 字段
                actual_unit_count = project.total_chapters or 0

            # 根据 start_from 和 unit_count 计算实际要生成的单元数
            start_from = max(1, min(request.start_from or 1, actual_unit_count))
            unit_count = request.unit_count

            # 计算从 start_from 开始可用的单元数
            available_units = max(0, actual_unit_count - start_from + 1)

            # 确定最终的 total_units
            if unit_count is not None:
                # 用户指定了生成数量，取指定数量和可用数量的较小值
                total_units = min(unit_count, available_units)
            else:
                # 未指定数量，生成从 start_from 到最后的所有单元
                total_units = available_units

            logger.info(f"创建写作任务: project_id={request.project_id}, actual_units={actual_unit_count}, "
                        f"start_from={start_from}, unit_count={unit_count}, total_units={total_units}")

            # 构建任务配置，注入项目数据
            import json
            # 兼容 Pydantic v2：优先 model_dump()，回退旧版 dict()，消除弃用告警
            if hasattr(request.config, "model_dump"):
                task_config = request.config.model_dump()
            elif hasattr(request.config, "dict"):
                task_config = request.config.dict()
            else:
                task_config = request.config or {}
            if not isinstance(task_config, dict):
                task_config = {}

            # 注入大纲数据（从项目加载）
            if project.outline_content:
                try:
                    # outline_content 可能是 JSON 字符串或纯文本
                    outline_data = json.loads(project.outline_content) if project.outline_content.strip(
                    ).startswith('{') else {"raw_content": project.outline_content}
                    if not task_config.get("outline"):
                        task_config["outline"] = outline_data
                except (json.JSONDecodeError, AttributeError):
                    # 如果解析失败，将原始内容作为 raw_content
                    if not task_config.get("outline"):
                        task_config["outline"] = {
                            "raw_content": project.outline_content}

            # 注入单元概述
            if project.unit_summaries and not task_config.get("unit_summaries"):
                task_config["unit_summaries"] = project.unit_summaries

            # 注入每章字数配置（按内容类型差异化）
            content_type = project.content_type or "novel"
            if content_type in ("series_script", "movie_script"):
                # 剧本类型包含大量视觉方案内容（分镜设计、拍摄指导、运镜设计、
                # 光影方案、演出指导、剪辑思路、AI视觉资源生成提示词），
                # 字数需求远超纯文本小说，强制设置为较大的宽松值
                # 无论前端传了什么值都覆盖，因为剧本不应受字数约束
                words_per_chapter = 20000
                task_config["words_per_chapter"] = words_per_chapter
            elif not task_config.get("words_per_chapter"):
                words_per_chapter = 3000  # 小说默认值
                # 优先从 novel_config 获取
                if project.novel_config and isinstance(project.novel_config, dict):
                    words_per_chapter = project.novel_config.get(
                        "words_per_chapter", 3000)
                # 其次从 generation_config 获取
                elif project.generation_config and isinstance(project.generation_config, dict):
                    words_per_chapter = project.generation_config.get(
                        "words_per_chapter", 3000)
                task_config["words_per_chapter"] = words_per_chapter

            # 注入项目类型和生成模式
            task_config["project_type"] = project.project_type.value if project.project_type else "novel"
            task_config["content_type"] = project.content_type or "novel"

            # [重构] 注入剧集/电影类型专属配置（对齐小说类型的直接生成方式）
            content_type = project.content_type or "novel"
            if content_type == "series_script":
                if project.series_script_config and isinstance(project.series_script_config, dict):
                    sc = project.series_script_config
                    task_config["series_type"] = task_config.get("series_type") or sc.get("series_type", "电视剧")
                    task_config["episode_duration_range"] = task_config.get("episode_duration_range") or sc.get("episode_duration_range", [30, 45])
                    task_config["script_mode"] = task_config.get("script_mode") or sc.get("script_mode", "real")
                    task_config["scenes_per_episode_range"] = task_config.get("scenes_per_episode_range") or sc.get("scenes_per_episode_range")
                    task_config["narrative_mode"] = task_config.get("narrative_mode") or sc.get("narrative_mode", "serialized")
                    logger.info(f"[任务配置注入] 剧集类型专属配置: series_type={task_config['series_type']}, "
                                f"episode_duration_range={task_config['episode_duration_range']}, "
                                f"script_mode={task_config['script_mode']}, "
                                f"narrative_mode={task_config.get('narrative_mode', 'unknown')}")
            elif content_type == "movie_script":
                if project.movie_script_config and isinstance(project.movie_script_config, dict):
                    mc = project.movie_script_config
                    task_config["movie_type"] = task_config.get("movie_type") or mc.get("movie_type", "电影")
                    task_config["duration_range"] = task_config.get("duration_range") or mc.get("duration_range", [10, 15])
                    task_config["script_mode"] = task_config.get("script_mode") or mc.get("script_mode", "real")
                    task_config["total_scenes"] = task_config.get("total_scenes") or mc.get("total_scenes", 0)
                    task_config["narrative_mode"] = task_config.get("narrative_mode") or mc.get("narrative_mode", "serialized")
                    logger.info(f"[任务配置注入] 电影类型专属配置: movie_type={task_config['movie_type']}, "
                                f"duration_range={task_config['duration_range']}, "
                                f"script_mode={task_config['script_mode']}, "
                                f"narrative_mode={task_config.get('narrative_mode', 'unknown')}")

            # 注入文风知识库配置（style_guide → style_library_guide）
            # 前端传入的 config.style_guide 会被合并到 task_config 中
            # 如果前端未传 style_guide.style_library_guide，从项目元数据兜底加载
            style_guide = task_config.get("style_guide", {})
            if not isinstance(style_guide, dict):
                style_guide = {}

            if not style_guide.get("style_library_guide"):
                # 尝试从项目的 generation_config 中获取文风配置并重建
                style_ids = style_guide.get("writing_styles") or []
                intensity = style_guide.get("style_intensity", 0.7)

                # 也可从项目 generation_config 中获取
                if not style_ids and project.generation_config and isinstance(project.generation_config, dict):
                    style_ids = project.generation_config.get("writing_styles", [])
                    intensity = project.generation_config.get(
                        "style_intensity", 0.7)

                if style_ids:
                    try:
                        from app.tools.style_library import build_style_guide
                        rebuilt_guide = build_style_guide(style_ids, intensity)

                        # 验证重建的guide结构
                        if rebuilt_guide and isinstance(rebuilt_guide, dict):
                            # 检查必需字段
                            required_keys = ["writing_styles", "style_intensity"]
                            missing_keys = [
                                k for k in required_keys if k not in rebuilt_guide]

                            if missing_keys:
                                logger.warning(
                                    f"[文风注入] 重建的guide缺少必需字段: {missing_keys}, "
                                    f"style_ids={style_ids}"
                                )
                                # 即使缺少字段，只要有style_library_guide就使用
                                if "style_library_guide" in rebuilt_guide:
                                    style_guide["style_library_guide"] = rebuilt_guide
                                    logger.info(
                                        f"[文风注入] 从文风知识库重建 style_library_guide (部分字段缺失), "
                                        f"style_ids={style_ids}, intensity={intensity}"
                                    )
                            else:
                                # 结构完整，直接使用
                                style_guide["style_library_guide"] = rebuilt_guide
                                logger.info(
                                    f"[文风注入] 从文风知识库重建 style_library_guide, "
                                    f"style_ids={style_ids}, intensity={intensity}"
                                )
                        else:
                            logger.warning(
                                f"[文风注入] build_style_guide 返回格式异常: "
                                f"type={type(rebuilt_guide)}, style_ids={style_ids}"
                            )
                    except Exception as e:
                        logger.warning(f"[文风注入] 重建 style_library_guide 失败: {e}")

            task_config["style_guide"] = style_guide

            # 系统统一使用整章直接生成模式（direct mode）
            task_config["generation_mode"] = "direct"

            logger.info(f"任务配置注入完成: has_outline={bool(task_config.get('outline'))}, "
                        f"has_unit_summaries={bool(task_config.get('unit_summaries'))}, "
                        f"words_per_chapter={task_config.get('words_per_chapter')}, "
                        f"generation_mode={task_config.get('generation_mode')}, "
                        f"has_style_library_guide={bool(task_config.get('style_guide', {}).get('style_library_guide'))}")

            # 创建任务记录
            task = WritingTask(
                project_id=request.project_id,
                user_id=current_user.id,
                status=TaskStatus.PENDING,
                config=task_config,
                start_from=start_from,
                unit_count=unit_count,
                total_units=total_units,
                completed_units=0,
                total_tokens=0,
                total_cost=0.0
            )
            db.add(task)
            await db.commit()
            await db.refresh(task)

            # 根据 unit_summaries 预创建 WritingUnit 记录
            if project.unit_summaries and isinstance(project.unit_summaries, dict):
                from app.models.writing_unit import WritingUnit, UnitStatus

                unit_summaries = project.unit_summaries
                for i in range(start_from, start_from + total_units):
                    unit_key = str(i)
                    unit_summary_data = unit_summaries.get(unit_key, {})

                    unit = WritingUnit(
                        task_id=task.id,
                        unit_index=i,
                        unit_title=unit_summary_data.get("title") if isinstance(
                            unit_summary_data, dict) else None,
                        unit_summary=unit_summary_data.get("summary") if isinstance(
                            unit_summary_data, dict) else str(unit_summary_data),
                        status=UnitStatus.PENDING,
                        scenes_data=[]
                    )
                    db.add(unit)

                await db.commit()
                logger.info(
                    f"预创建 {total_units} 个 WritingUnit 记录: task_id={task.id}")

            logger.info(
                f"创建写作任务: task_id={task.id}, project_id={request.project_id}, user_id={current_user.id}")

            # 启动Pipeline（后台异步执行）
            asyncio.create_task(
                _start_pipeline(
                    task_id=task.id,
                    project_id=request.project_id,
                    config=task_config
                )
            )

            return ResponseModel(
                success=True,
                code=200,
                message="任务创建成功",
                data=_build_task_response(task)
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"创建写作任务失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建任务失败: {str(e)}"
            )

    @router.get("", response_model=ResponseModel[WritingTaskListResponse])
    async def list_tasks(
        status_filter: Optional[str] = Query(
            None, alias="status", description="状态过滤: pending/running/interrupted/completed/failed"),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=100, description="每页大小"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取写作任务列表

        支持分页和状态过滤，只返回当前用户的任务。
        """
        try:
            # 构建查询条件
            conditions = [WritingTask.user_id == current_user.id]
            if status_filter:
                try:
                    status_enum = TaskStatus(status_filter)
                    conditions.append(WritingTask.status == status_enum)
                except ValueError:
                    pass  # 忽略无效的状态值

            # 查询总数
            count_result = await db.execute(
                select(func.count(WritingTask.id)).where(*conditions)
            )
            total = count_result.scalar() or 0

            # 分页查询
            result = await db.execute(
                select(WritingTask).where(*conditions)
                .order_by(desc(WritingTask.created_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            tasks = result.scalars().all()

            return ResponseModel(
                success=True,
                code=200,
                message="获取任务列表成功",
                data=WritingTaskListResponse(
                    items=[_build_task_response(task) for task in tasks],
                    total=total,
                    page=page,
                    page_size=page_size
                )
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取任务列表失败: {str(e)}"
            )

    @router.get("/{task_id}", response_model=ResponseModel[WritingTaskDetailResponse])
    async def get_task_detail(
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取写作任务详情

        包含任务基本信息、单元列表和统计摘要。
        """
        try:
            # 查询任务
            result = await db.execute(
                select(WritingTask).where(
                    and_(WritingTask.id == task_id,
                         WritingTask.user_id == current_user.id)
                )
            )
            task = result.scalar_one_or_none()

            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="任务不存在"
                )

            # 查询单元列表
            units_result = await db.execute(
                select(WritingUnit).where(WritingUnit.task_id ==
                                          task_id).order_by(WritingUnit.unit_index)
            )
            units = units_result.scalars().all()
            unit_responses = [_build_unit_response(unit) for unit in units]

            # 构建统计摘要
            from app.schemas.writing_task import WritingStatsResponse
            stats_summary = WritingStatsResponse(
                total_tokens=task.total_tokens,
                total_cost=task.total_cost,
                by_agent={}  # TODO: 从WritingStat表聚合
            )

            # 构建详细响应
            task_data = _build_task_response(task)
            detail_data = WritingTaskDetailResponse(
                **task_data.model_dump(),
                units=unit_responses,
                stats_summary=stats_summary
            )

            return ResponseModel(
                success=True,
                code=200,
                message="获取任务详情成功",
                data=detail_data
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取任务详情失败: task_id={task_id}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取任务详情失败: {str(e)}"
            )

    @router.delete("/{task_id}", response_model=ResponseModel[dict])
    async def delete_task(
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        删除写作任务

        删除任务及其所有关联数据（单元、场景、统计等）。
        """
        try:
            # 查询任务
            result = await db.execute(
                select(WritingTask).where(
                    and_(WritingTask.id == task_id,
                         WritingTask.user_id == current_user.id)
                )
            )
            task = result.scalar_one_or_none()

            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="任务不存在"
                )

            # 检查任务状态
            current_status = task.status.value if isinstance(
                task.status, TaskStatus) else task.status
            if current_status == TaskStatus.RUNNING.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="任务正在运行中，请先中断后再删除"
                )

            # 删除任务（级联删除关联数据）
            await db.delete(task)
            await db.commit()

            logger.info(f"删除写作任务: task_id={task_id}")

            return ResponseModel(
                success=True,
                code=200,
                message="任务已删除",
                data={"task_id": task_id, "deleted": True}
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除任务失败: task_id={task_id}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"删除任务失败: {str(e)}"
            )
