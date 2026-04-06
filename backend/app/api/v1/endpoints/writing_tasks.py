"""
多Agent协作文学作品生成系统 - 写作任务API端点

模块: api.v1.endpoints
文件: writing_tasks.py
功能: 提供写作任务的RESTful API接口，包括创建、查询、控制、删除等操作

依赖关系:
    - 依赖: app.services.writing_engine.task_manager, app.services.writing_engine.pipeline
    - 依赖: app.schemas.writing_task, app.models.writing_task
    - 被依赖: app.api.v1.router (路由注册)

使用说明:
    本模块提供写作任务的完整CRUD API，所有端点需要JWT认证。
    创建任务后自动启动Pipeline，通过WebSocket接收实时进度。

创建时间: 2026-03-28
最后修改: 2026-03-28
版本: 1.0.0
作者: AI Assistant
"""
import asyncio
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.core.database import get_db
from app.core.logger import get_logger
from app.api.deps import get_current_user
from app.models import User
from app.models.writing_task import WritingTask, TaskStatus
from app.models.writing_unit import WritingUnit
from app.models.writing_scene import WritingScene
from app.schemas.common import ResponseModel
from app.schemas.writing_task import (
    WritingTaskCreate, WritingTaskResponse, WritingTaskDetailResponse,
    WritingTaskListResponse, WritingUnitResponse, WritingSceneResponse,
    WritingTaskStatsDetailResponse, AgentStatItem, WritingTaskContinue
)

# 导入服务层
from app.services.writing_engine.pipeline import WritingPipeline

router = APIRouter(prefix="/writing-tasks", tags=["多Agent写作任务"])
logger = get_logger("writing_tasks")


# ==================== 辅助函数 ====================

def _build_task_response(task: WritingTask) -> WritingTaskResponse:
    """构建任务响应对象"""
    return WritingTaskResponse(
        id=task.id,
        uuid=task.uuid,
        project_id=task.project_id,
        user_id=task.user_id,
        status=task.status.value if isinstance(task.status, TaskStatus) else task.status,
        total_units=task.total_units,
        completed_units=task.completed_units,
        config=task.config or {},
        total_tokens=task.total_tokens,
        total_cost=task.total_cost,
        error_message=task.error_message,
        start_time=task.start_time,
        end_time=task.end_time,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


def _build_unit_response(unit: WritingUnit) -> WritingUnitResponse:
    """构建单元响应对象"""
    return WritingUnitResponse(
        id=unit.id,
        task_id=unit.task_id,
        unit_index=unit.unit_index,
        unit_title=unit.unit_title,
        unit_summary=unit.unit_summary,
        status=unit.status.value if hasattr(unit.status, 'value') else unit.status,
        word_count=unit.word_count,
        token_count=unit.token_count,
        duration_ms=unit.duration_ms,
        created_at=unit.created_at,
        updated_at=unit.updated_at
    )


def _build_scene_response(scene: WritingScene) -> WritingSceneResponse:
    """构建场景响应对象"""
    return WritingSceneResponse(
        id=scene.id,
        unit_id=scene.unit_id,
        scene_index=scene.scene_index,
        scene_title=scene.scene_title,
        scene_outline=scene.scene_outline or {},
        status=scene.status.value if hasattr(scene.status, 'value') else scene.status,
        final_content=scene.final_content,
        word_count=scene.word_count,
        token_count=scene.token_count,
        duration_ms=scene.duration_ms,
        created_at=scene.created_at,
        updated_at=scene.updated_at
    )


# ==================== API端点 ====================

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
        from sqlalchemy import func
        
        project_result = await db.execute(
            select(NovelProject).where(
                and_(NovelProject.id == request.project_id, NovelProject.user_id == current_user.id)
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
        start_from = request.start_from or 1
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
        task_config = request.config.dict() if hasattr(request.config, 'dict') else (request.config or {})
        if not isinstance(task_config, dict):
            task_config = {}
        
        # 注入大纲数据（从项目加载）
        if project.outline_content:
            try:
                # outline_content 可能是 JSON 字符串或纯文本
                outline_data = json.loads(project.outline_content) if project.outline_content.strip().startswith('{') else {"raw_content": project.outline_content}
                if not task_config.get("outline"):
                    task_config["outline"] = outline_data
            except (json.JSONDecodeError, AttributeError):
                # 如果解析失败，将原始内容作为 raw_content
                if not task_config.get("outline"):
                    task_config["outline"] = {"raw_content": project.outline_content}
        
        
        # 注入单元概述
        if project.unit_summaries and not task_config.get("unit_summaries"):
            task_config["unit_summaries"] = project.unit_summaries


        # 注入每章字数配置
        if not task_config.get("words_per_chapter"):
            words_per_chapter = 3000  # 默认值
            # 优先从 novel_config 获取
            if project.novel_config and isinstance(project.novel_config, dict):
                words_per_chapter = project.novel_config.get("words_per_chapter", 3000)
            # 其次从 generation_config 获取
            elif project.generation_config and isinstance(project.generation_config, dict):
                words_per_chapter = project.generation_config.get("words_per_chapter", 3000)
            task_config["words_per_chapter"] = words_per_chapter
        
        # 注入项目类型和生成模式
        task_config["project_type"] = project.project_type.value if project.project_type else "novel"
        task_config["content_type"] = project.content_type or "novel"
        
        # 根据项目类型和章节数自动判断生成模式
        # 短篇小说（少于5章）或剧本类型使用整章生成模式
        if not task_config.get("generation_mode"):
            if project.project_type and project.project_type.value == "script":
                # 剧本类型使用场景拆解模式
                task_config["generation_mode"] = "scene_split"
            elif actual_unit_count <= 5 and project.project_type.value == "novel":
                # 短篇小说使用整章生成模式
                task_config["generation_mode"] = "direct"
            else:
                # 默认使用场景拆解模式
                task_config["generation_mode"] = "scene_split"
        
        
        logger.info(f"任务配置注入完成: has_outline={bool(task_config.get('outline'))}, "
                    f"has_unit_summaries={bool(task_config.get('unit_summaries'))}, "
                    f"words_per_chapter={task_config.get('words_per_chapter')}, "
                    f"generation_mode={task_config.get('generation_mode')}")
        
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
                    unit_title=unit_summary_data.get("title") if isinstance(unit_summary_data, dict) else None,
                    unit_summary=unit_summary_data.get("summary") if isinstance(unit_summary_data, dict) else str(unit_summary_data),
                    status=UnitStatus.PENDING,
                    scenes_data=[]
                )
                db.add(unit)
                    
            await db.commit()
            logger.info(f"预创建 {total_units} 个 WritingUnit 记录: task_id={task.id}")
                
        logger.info(f"创建写作任务: task_id={task.id}, project_id={request.project_id}, user_id={current_user.id}")
        
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
    status: Optional[str] = Query(None, description="状态过滤: pending/running/interrupted/completed/failed"),
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
        query = select(WritingTask).where(WritingTask.user_id == current_user.id)
        
        if status:
            try:
                task_status = TaskStatus(status)
                query = query.where(WritingTask.status == task_status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的状态值: {status}"
                )
        
        # 获取总数
        count_query = select(WritingTask).where(WritingTask.user_id == current_user.id)
        if status:
            count_query = count_query.where(WritingTask.status == task_status)
        
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # 分页查询
        query = query.order_by(desc(WritingTask.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        # 构建响应
        items = [_build_task_response(task) for task in tasks]
        
        return ResponseModel(
            success=True,
            code=200,
            message="获取任务列表成功",
            data=WritingTaskListResponse(
                items=items,
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
                and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
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
            select(WritingUnit).where(WritingUnit.task_id == task_id).order_by(WritingUnit.unit_index)
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


@router.post("/{task_id}/interrupt", response_model=ResponseModel[WritingTaskResponse])
async def interrupt_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    中断写作任务
    
    向正在运行的任务发送中断信号，Pipeline会在下一个检查点停止。
    状态更新由Orchestrator在检测到中断后自动完成。
    可通过 `/resume` 端点续传。
    """
    try:
        # 查询任务
        result = await db.execute(
            select(WritingTask).where(
                and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 检查任务状态
        current_status = task.status.value if isinstance(task.status, TaskStatus) else task.status
        if current_status not in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务当前状态为 {current_status}，无法中断"
            )
        
        # 获取活跃的Pipeline实例并发送中断信号
        pipeline = WritingPipeline.get_active_pipeline(task_id)
        interrupt_sent = False
        
        if pipeline:
            try:
                await pipeline.interrupt()
                interrupt_sent = True
                logger.info(f"已向Pipeline发送中断信号: task_id={task_id}")
            except Exception as e:
                logger.warning(f"向Pipeline发送中断信号失败: task_id={task_id}, error={e}")
        
        # 如果没有活跃的Pipeline，直接更新状态
        if not interrupt_sent:
            logger.info(f"没有活跃的Pipeline，直接更新任务状态: task_id={task_id}")
            task.status = TaskStatus.INTERRUPTED
            task.end_time = datetime.now()
            await db.commit()
            await db.refresh(task)
        else:
            # 等待一小段时间让Pipeline处理中断，然后刷新任务状态
            import asyncio
            await asyncio.sleep(0.5)  # 给Pipeline一些时间处理中断
            await db.refresh(task)
        
        
        logger.info(f"中断写作任务: task_id={task_id}, 最终状态={task.status}")
        
        return ResponseModel(
            success=True,
            code=200,
            message="中断信号已发送" if interrupt_sent else "任务已中断",
            data=_build_task_response(task)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"中断任务失败: task_id={task_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"中断任务失败: {str(e)}"
        )


@router.post("/{task_id}/resume", response_model=ResponseModel[WritingTaskResponse])
async def resume_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    续传写作任务
    
    从中断点继续执行写作任务。
    """
    try:
        # 查询任务
        result = await db.execute(
            select(WritingTask).where(
                and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 检查任务状态
        current_status = task.status.value if isinstance(task.status, TaskStatus) else task.status
        # 允许中断或失败状态续传
        if current_status not in [TaskStatus.INTERRUPTED.value, TaskStatus.FAILED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务当前状态为 {current_status}，无法续传。只有中断或失败的任务才能续传。"
            )
        
        # 更新任务状态 - 保持INTERRUPTED，让Pipeline来更新为RUNNING
        task.end_time = None
        await db.commit()
        await db.refresh(task)
        
        # 启动Pipeline续传
        asyncio.create_task(_resume_pipeline(task_id=task_id))
        
        logger.info(f"续传写作任务: task_id={task_id}")
        
        return ResponseModel(
            success=True,
            code=200,
            message="任务续传已启动",
            data=_build_task_response(task)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"续传任务失败: task_id={task_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"续传任务失败: {str(e)}"
        )


@router.post("/{task_id}/continue", response_model=ResponseModel[WritingTaskResponse])
async def continue_task(
    task_id: int,
    request: WritingTaskContinue,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    继续生成写作任务
    
    任务完成后继续生成更多单元。从当前已完成单元的下一单元开始。
    
    参数:
    - unit_count: 要继续生成的单元数量（必需）
    
    注意：只有已完成的任务才能继续生成。
    """
    try:
        # 查询任务
        result = await db.execute(
            select(WritingTask).where(
                and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 检查任务状态 - 只有completed状态可以继续生成
        current_status = task.status.value if isinstance(task.status, TaskStatus) else task.status
        if current_status != TaskStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务当前状态为 {current_status}，无法继续生成。只有已完成的任务才能继续生成。"
            )
        
        
        # 获取项目信息
        from app.models.novel_project import NovelProject
        project_result = await db.execute(
            select(NovelProject).where(NovelProject.id == task.project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )
        
        
        # 计算新的起始位置
        start_from = task.completed_units + 1
        unit_count = request.unit_count
        
        # 计算项目的实际单元数
        actual_unit_count = 0
        if project.unit_summaries and isinstance(project.unit_summaries, dict):
            actual_unit_count = len(project.unit_summaries)
        if actual_unit_count == 0:
            from sqlalchemy import func
            from app.models.novel_chapter import NovelChapter
            chapter_count_result = await db.execute(
                select(func.count(NovelChapter.id)).where(
                    NovelChapter.project_id == task.project_id
                )
            )
            actual_unit_count = chapter_count_result.scalar() or 0
        
        
        # 验证是否还有单元可生成
        if actual_unit_count > 0 and start_from > actual_unit_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"已到达项目最后单元（{actual_unit_count}），无法继续生成"
            )
        
        
        # 计算实际可生成的单元数
        if actual_unit_count > 0:
            available_units = actual_unit_count - start_from + 1
            if unit_count > available_units:
                unit_count = available_units
        
        
        if unit_count <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有可生成的单元"
            )
        
        
        logger.info(f"继续生成任务: task_id={task_id}, start_from={start_from}, unit_count={unit_count}")
        
        # 更新任务配置和状态
        task_config = task.config or {}
        task_config["continue_from"] = start_from
        task_config["continue_unit_count"] = unit_count
        task.config = task_config
        
        # 更新任务参数
        task.total_units = task.total_units + unit_count
        task.status = TaskStatus.PENDING  # 重置为pending，让Pipeline启动
        task.end_time = None
        task.error_message = None
        
        # 预创建WritingUnit记录
        from app.models.writing_unit import WritingUnit, UnitStatus
        if project.unit_summaries and isinstance(project.unit_summaries, dict):
            unit_summaries = project.unit_summaries
            for i in range(start_from, start_from + unit_count):
                unit_key = str(i)
                unit_summary_data = unit_summaries.get(unit_key, {})
                
                # 检查是否已存在该单元
                existing_unit = await db.execute(
                    select(WritingUnit).where(
                        and_(WritingUnit.task_id == task_id, WritingUnit.unit_index == i)
                    )
                )
                if existing_unit.scalar_one_or_none():
                    continue  # 跳过已存在的单元
                
                unit = WritingUnit(
                    task_id=task.id,
                    unit_index=i,
                    unit_title=unit_summary_data.get("title") if isinstance(unit_summary_data, dict) else None,
                    unit_summary=unit_summary_data.get("summary") if isinstance(unit_summary_data, dict) else str(unit_summary_data),
                    status=UnitStatus.PENDING,
                    scenes_data=[]
                )
                db.add(unit)
        
        
        await db.commit()
        await db.refresh(task)
        
        # 启动Pipeline
        asyncio.create_task(
            _continue_pipeline(
                task_id=task.id,
                start_from=start_from,
                unit_count=unit_count
            )
        )
        
        logger.info(f"继续生成任务已启动: task_id={task_id}")
        
        return ResponseModel(
            success=True,
            code=200,
            message=f"已从第{start_from}单元继续生成{unit_count}个单元",
            data=_build_task_response(task)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"继续生成任务失败: task_id={task_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"继续生成任务失败: {str(e)}"
        )


@router.get("/{task_id}/stats", response_model=ResponseModel[WritingTaskStatsDetailResponse])
async def get_task_stats(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取写作任务统计详情
    
    包含总token消耗、总费用、按Agent统计等详细信息。
    """
    try:
        # 查询任务
        result = await db.execute(
            select(WritingTask).where(
                and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 查询Agent统计
        from app.models.writing_stat import WritingStat
        stats_result = await db.execute(
            select(WritingStat).where(WritingStat.task_id == task_id)
        )
        stats = stats_result.scalars().all()
        
        # 构建按Agent统计
        by_agent = []
        for stat in stats:
            by_agent.append(AgentStatItem(
                agent_name=stat.agent_name,
                model_id=stat.model_id,
                call_count=stat.call_count,
                total_input_tokens=stat.total_input_tokens,
                total_output_tokens=stat.total_output_tokens,
                total_tokens=stat.total_tokens,
                total_duration_sec=stat.total_duration_ms / 1000.0 if stat.total_duration_ms else 0.0,
                total_cost=stat.total_cost
            ))
        
        # 构建响应
        stats_data = WritingTaskStatsDetailResponse(
            task_id=task_id,
            total_tokens=task.total_tokens,
            total_cost=task.total_cost,
            by_agent=by_agent,
            by_scene={}  # TODO: 按场景统计
        )
        
        return ResponseModel(
            success=True,
            code=200,
            message="获取任务统计成功",
            data=stats_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务统计失败: task_id={task_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务统计失败: {str(e)}"
        )


@router.get("/{task_id}/units", response_model=ResponseModel[List[WritingUnitResponse]])
async def get_task_units(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取写作任务的单元列表
    """
    try:
        # 验证任务存在且属于当前用户
        result = await db.execute(
            select(WritingTask).where(
                and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
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
            select(WritingUnit).where(WritingUnit.task_id == task_id).order_by(WritingUnit.unit_index)
        )
        units = units_result.scalars().all()
        
        return ResponseModel(
            success=True,
            code=200,
            message="获取单元列表成功",
            data=[_build_unit_response(unit) for unit in units]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取单元列表失败: task_id={task_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取单元列表失败: {str(e)}"
        )


@router.get("/{task_id}/units/{unit_index}/scenes", response_model=ResponseModel[List[WritingSceneResponse]])
async def get_unit_scenes(
    task_id: int,
    unit_index: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定单元的场景列表
    """
    try:
        # 验证任务存在且属于当前用户
        task_result = await db.execute(
            select(WritingTask).where(
                and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
            )
        )
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 查询单元
        unit_result = await db.execute(
            select(WritingUnit).where(
                and_(WritingUnit.task_id == task_id, WritingUnit.unit_index == unit_index)
            )
        )
        unit = unit_result.scalar_one_or_none()
        
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="单元不存在"
            )
        
        # 查询场景列表
        scenes_result = await db.execute(
            select(WritingScene).where(WritingScene.unit_id == unit.id).order_by(WritingScene.scene_index)
        )
        scenes = scenes_result.scalars().all()
        
        return ResponseModel(
            success=True,
            code=200,
            message="获取场景列表成功",
            data=[_build_scene_response(scene) for scene in scenes]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取场景列表失败: task_id={task_id}, unit_index={unit_index}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取场景列表失败: {str(e)}"
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
                and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 检查任务状态
        current_status = task.status.value if isinstance(task.status, TaskStatus) else task.status
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


# ==================== 后台任务函数 ====================

async def _start_pipeline(task_id: int, project_id: int, config: dict):
    """
    启动写作Pipeline（后台任务）
    
    创建Pipeline实例并启动写作任务。Pipeline自己管理数据库会话生命周期。
    """
    from app.services.writing_engine.pipeline import WritingPipeline
    from app.agents.writing.agent_config import AgentConfig
    from app.core.database import async_session_maker
    from sqlalchemy import select
    
    # 构建Agent配置（从任务配置中解析）
    agent_config = AgentConfig()
    
    # 解析任务配置中的Agent设置（需要数据库会话）
    agents_config = config.get("agents", {})
    
    # 记录收到的原始config内容（agents部分）
    logger.info(f"[配置解析] task_id={task_id}, 收到的原始agents配置: {agents_config}")
    
    from app.agents.writing.agent_config import AgentModelConfig
    from app.agents.writing.base_agent import AgentRole
    from app.models.writing_model_config import WritingModelConfig as WMC
    from app.core.security import api_key_encryption
    
    configured_roles = []  # 记录成功配置的角色
    skipped_roles = []     # 记录被跳过的角色
    
    async with async_session_maker() as db:
        # 兜底：如果agents为空，自动查询用户的WritingModelConfig
        if not agents_config:
            logger.warning(f"[配置解析] task_id={task_id}, agents配置为空，尝试自动加载用户默认模型配置")
            # 先查询task获取user_id
            task_result = await db.execute(
                select(WritingTask).where(WritingTask.id == task_id)
            )
            task = task_result.scalar_one_or_none()
            if task is None:
                logger.error(f"[配置解析] task_id={task_id}, 未找到任务记录，无法加载默认模型配置")
                raise ValueError(f"未找到任务记录: task_id={task_id}")
            
            # 查询用户的第一个活跃WritingModelConfig
            wmc_result = await db.execute(
                select(WMC).where(
                    WMC.user_id == task.user_id,
                    WMC.is_active == True
                ).order_by(WMC.updated_at.desc()).limit(1)
            )
            default_config = wmc_result.scalar_one_or_none()
            if default_config is None:
                logger.error(f"[配置解析] task_id={task_id}, user_id={task.user_id}, 无可用模型配置，任务将失败")
                raise ValueError(f"用户未配置默认模型配置: user_id={task.user_id}")
            
            # 为所有可配置角色统一设置
            all_roles = ["orchestrator", "structural", "writer", "style_editor", "logic_editor", "compliance", "knowledge", "assembler"]
            for role_str in all_roles:
                agents_config[role_str] = {"config_id": default_config.id, "temperature": 0.7}  # 不再设置max_tokens
            logger.info(f"[配置解析] 自动使用默认模型配置: id={default_config.id}, name={default_config.name}")
        
        for role_str, role_config in agents_config.items():
            try:
                role = AgentRole(role_str)
                
                # 记录当前role的原始配置
                logger.info(f"[配置解析] task_id={task_id}, 正在解析role={role_str}, "
                           f"config_id={role_config.get('config_id')}, "
                           f"model={role_config.get('model')}, "
                           f"provider={role_config.get('provider')}")
                
                if role_config.get("config_id"):
                    # 使用预配置模型 - 从数据库加载
                    config_result = await db.execute(
                        select(WMC).where(WMC.id == role_config["config_id"])
                    )
                    saved_config = config_result.scalar_one_or_none()
                    if saved_config:
                        api_key = api_key_encryption.decrypt(saved_config.encrypted_key)
                        agent_config.update_config(role, AgentModelConfig(
                            model_id=saved_config.model_id,
                            provider=saved_config.provider,
                            api_base=saved_config.api_base,
                            api_key=api_key,
                            temperature=role_config.get("temperature", 0.7),
                            max_tokens=role_config.get("max_tokens", 4096),
                            config_id=saved_config.id  # 保存config_id用于续传
                        ))
                        configured_roles.append({
                            "role": role_str,
                            "source": "config_id",
                            "provider": saved_config.provider,
                            "model_id": saved_config.model_id
                        })
                        logger.info(f"[配置解析] task_id={task_id}, role={role_str} 使用预配置模型: "
                                   f"provider={saved_config.provider}, model_id={saved_config.model_id}")
                    else:
                        skipped_roles.append({"role": role_str, "reason": f"config_id={role_config.get('config_id')}未找到"})
                        logger.warning(f"[配置解析] task_id={task_id}, role={role_str} 的config_id="
                                      f"{role_config.get('config_id')}在数据库中未找到")
                elif role_config.get("model") and role_config.get("provider"):
                    # 使用自定义配置
                    agent_config.update_config(role, AgentModelConfig(
                        model_id=role_config["model"],
                        provider=role_config["provider"],
                        api_base=role_config.get("api_base"),
                        api_key=role_config.get("api_key"),
                        temperature=role_config.get("temperature", 0.7),
                        max_tokens=role_config.get("max_tokens", 4096)
                    ))
                    configured_roles.append({
                        "role": role_str,
                        "source": "custom",
                        "provider": role_config["provider"],
                        "model_id": role_config["model"]
                    })
                    logger.info(f"[配置解析] task_id={task_id}, role={role_str} 使用自定义配置: "
                               f"provider={role_config['provider']}, model_id={role_config['model']}")
                else:
                    # 该role没有配置模型
                    skipped_roles.append({
                        "role": role_str, 
                        "reason": f"缺少model或provider配置 (model={role_config.get('model')}, provider={role_config.get('provider')})"
                    })
                    logger.warning(f"[配置解析] task_id={task_id}, role={role_str} 缺少model或provider配置，" 
                                  f"model={role_config.get('model')}, provider={role_config.get('provider')}")
                    
            except ValueError as e:
                # AgentRole枚举值错误
                skipped_roles.append({"role": role_str, "reason": f"无效的role值: {e}"})
                logger.warning(f"[配置解析] task_id={task_id}, 无效的role值: role={role_str}, error={e}")
            except Exception as e:
                skipped_roles.append({"role": role_str, "reason": f"解析异常: {e}"})
                logger.warning(f"[配置解析] task_id={task_id}, 解析Agent配置失败: role={role_str}, error={e}")
        
        # 记录最终配置汇总
        logger.info(f"[配置解析] task_id={task_id}, 配置完成: 成功配置{len(configured_roles)}个角色, "
                   f"跳过{len(skipped_roles)}个角色")
        if configured_roles:
            for cfg in configured_roles:
                logger.info(f"[配置解析] task_id={task_id}, 已配置角色: {cfg}")
        if skipped_roles:
            for skip in skipped_roles:
                logger.warning(f"[配置解析] task_id={task_id}, 跳过角色: {skip}")
        
        # 将agent_configs保存到task.config中，以便续传时恢复
        try:
            result = await db.execute(
                select(WritingTask).where(WritingTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                task_config = task.config or {}
                task_config["agent_configs"] = agent_config.to_dict().get("configs", {})
                task.config = task_config
                await db.commit()
                logger.info(f"[配置解析] task_id={task_id}, 已将agent_configs保存到任务配置中")
        except Exception as e:
            logger.warning(f"[配置解析] task_id={task_id}, 保存agent_configs到任务配置失败: {e}")
    
    try:
        # 创建Pipeline实例（只传递task_id，Pipeline自己管理数据库会话）
        pipeline = WritingPipeline(task_id=task_id, config=agent_config)
        
        # 注入WebSocket管理器（用于实时状态推送）
        from app.services.writing_engine.websocket_manager import get_websocket_manager
        pipeline.set_ws_manager(get_websocket_manager())
        
        # 启动Pipeline（后台异步执行）
        await pipeline.start()
        
        logger.info(f"写作Pipeline已启动: task_id={task_id}")
        
    except Exception as e:
        logger.exception(f"启动Pipeline失败: task_id={task_id}, error={str(e)}")
        # 尝试更新任务状态为失败
        try:
            async with async_session_maker() as db:
                # WritingTask 已在文件开头全局导入，无需重复导入
                result = await db.execute(
                    select(WritingTask).where(WritingTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    await db.commit()
        except Exception as db_error:
            logger.error(f"更新任务失败状态也失败了: task_id={task_id}, error={str(db_error)}")


async def _resume_pipeline(task_id: int):
    """
    续传写作Pipeline（后台任务）
    
    Pipeline自己管理数据库会话，不需要外部传入db
    """
    from app.services.writing_engine.pipeline import WritingPipeline
    from app.agents.writing.agent_config import AgentConfig
    from app.services.writing_engine.websocket_manager import get_websocket_manager
    
    try:
        # 检查是否有活跃的Pipeline
        pipeline = WritingPipeline.get_active_pipeline(task_id)
        if pipeline:
            # 确保活跃Pipeline有WebSocket管理器
            if not pipeline._ws_manager:
                pipeline.set_ws_manager(get_websocket_manager())
            success = await pipeline.resume()
        else:
            # 创建新的Pipeline实例（Pipeline自己管理会话）
            pipeline = WritingPipeline(task_id=task_id, config=AgentConfig())
            # 注入WebSocket管理器
            pipeline.set_ws_manager(get_websocket_manager())
            success = await pipeline.resume()
        
        if success:
            logger.info(f"写作Pipeline已续传: task_id={task_id}")
        else:
            logger.warning(f"写作Pipeline续传失败: task_id={task_id} (可能任务状态不正确或任务不存在)")
        
    except Exception as e:
        logger.exception(f"续传Pipeline失败: task_id={task_id}, error={str(e)}")


async def _continue_pipeline(task_id: int, start_from: int, unit_count: int):
    """
    继续生成写作Pipeline（后台任务）
    
    从指定起始单元继续生成，与resume不同，continue是从已完成任务后追加新单元
    """
    from app.services.writing_engine.pipeline import WritingPipeline
    from app.agents.writing.agent_config import AgentConfig
    from app.services.writing_engine.websocket_manager import get_websocket_manager
    from app.core.database import async_session_maker
    
    try:
        # 从任务配置中恢复Agent配置
        agent_config = AgentConfig()
        
        async with async_session_maker() as db:
            result = await db.execute(
                select(WritingTask).where(WritingTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                logger.error(f"[继续生成] 未找到任务: task_id={task_id}")
                return
            
            # 恢复Agent配置
            task_config = task.config or {}
            agent_configs = task_config.get("agent_configs", {})
            
            if agent_configs:
                from app.agents.writing.agent_config import AgentModelConfig
                from app.agents.writing.base_agent import AgentRole
                
                for role_str, cfg in agent_configs.items():
                    try:
                        role = AgentRole(role_str)
                        agent_config.update_config(role, AgentModelConfig(
                            model_id=cfg.get("model_id"),
                            provider=cfg.get("provider"),
                            api_base=cfg.get("api_base"),
                            api_key=cfg.get("api_key"),
                            temperature=cfg.get("temperature", 0.7),
                            max_tokens=cfg.get("max_tokens", 4096)
                        ))
                    except Exception as e:
                        logger.warning(f"[继续生成] 恢复Agent配置失败: role={role_str}, error={e}")
            
            
            # 更新任务状态为running
            task.status = TaskStatus.RUNNING
            task.start_time = task.start_time or datetime.now()
            await db.commit()
        
        
        # 创建Pipeline实例
        pipeline = WritingPipeline(task_id=task_id, config=agent_config)
        pipeline.set_ws_manager(get_websocket_manager())
        
        # 使用continue模式启动
        success = await pipeline.continue_from(start_from, unit_count)
        
        if success:
            logger.info(f"写作Pipeline继续生成完成: task_id={task_id}, start_from={start_from}, unit_count={unit_count}")
        else:
            logger.warning(f"写作Pipeline继续生成失败: task_id={task_id}")
            
    except Exception as e:
        logger.exception(f"继续生成Pipeline失败: task_id={task_id}, error={str(e)}")
        # 更新任务状态为失败
        try:
            async with async_session_maker() as db:
                result = await db.execute(
                    select(WritingTask).where(WritingTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    await db.commit()
        except Exception as db_error:
            logger.error(f"更新任务失败状态也失败了: task_id={task_id}, error={str(db_error)}")


@router.get("/{task_id}/export")
async def export_task(
    task_id: int,
    format: str = Query("txt", pattern="^(txt|md)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导出写作任务生成的内容"""
    import io
    
    # 查询任务
    task_result = await db.execute(
        select(WritingTask).where(
            and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
        )
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 查询所有已完成的单元
    units_result = await db.execute(
        select(WritingUnit).where(WritingUnit.task_id == task_id)
        .order_by(WritingUnit.unit_index)
    )
    units = units_result.scalars().all()
    
    if not units:
        raise HTTPException(status_code=404, detail="暂无生成内容")
    
    # 构建内容
    content_parts = []
    for unit in units:
        if unit.final_content:
            title = unit.unit_title or f"第{unit.unit_index}章"
            if format == "md":
                content_parts.append(f"\n\n# {title}\n\n{unit.final_content}")
            else:
                content_parts.append(f"\n\n{'='*50}\n{title}\n{'='*50}\n\n{unit.final_content}")
    
    full_content = "\n".join(content_parts).strip()
    
    if not full_content:
        raise HTTPException(status_code=404, detail="暂无生成内容")
    
    # 文件名
    filename = f"writing_task_{task_id}.{format}"
    media_type = "text/markdown" if format == "md" else "text/plain"
    
    return StreamingResponse(
        iter([full_content.encode('utf-8')]),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": f"{media_type}; charset=utf-8"
        }
    )


@router.get("/{task_id}/units/{unit_index}/export")
async def export_unit(
    task_id: int,
    unit_index: int,
    format: str = Query("txt", pattern="^(txt|md)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导出单个单元的生成内容"""
    # 查询任务
    task_result = await db.execute(
        select(WritingTask).where(
            and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
        )
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 查询单元
    unit_result = await db.execute(
        select(WritingUnit).where(
            and_(WritingUnit.task_id == task_id, WritingUnit.unit_index == unit_index)
        )
    )
    unit = unit_result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="单元不存在")
    
    if not unit.final_content:
        raise HTTPException(status_code=404, detail="该单元暂无生成内容")
    
    # 构建内容
    title = unit.unit_title or f"第{unit.unit_index}章"
    if format == "md":
        content = f"# {title}\n\n{unit.final_content}"
    else:
        content = f"{ '='*50 }\n{title}\n{ '='*50 }\n\n{unit.final_content}"
    
    # 文件名
    filename = f"unit_{unit_index}.{format}"
    media_type = "text/markdown" if format == "md" else "text/plain"
    
    return StreamingResponse(
        iter([content.encode('utf-8')]),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": f"{media_type}; charset=utf-8"
        }
    )
