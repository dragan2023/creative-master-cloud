"""
QA测试钩子端点（仅测试环境启用）

模块: api.v1.endpoints
文件: qa_test_hooks.py
功能: 为断网恢复等E2E测试提供可控的任务数据准备与真实WebSocket推送触发。

安全边界:
    - 仅当环境变量 QA_TEST_HOOKS=1 时由 main.py 条件挂载，生产环境不注册本路由
    - 所有端点仍要求登录认证，且只能操作当前用户自己的项目/任务
    - 不启动真实写作Pipeline，不调用任何LLM

创建时间: 2026-07-18（阶段03 §3.5 断网恢复E2E配套）
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logger import get_logger
from app.models import NovelProject, User, WritingTask
from app.models.writing_task import TaskStatus
from app.schemas.common import ResponseModel
from app.services.writing_engine.websocket_manager import get_websocket_manager

router = APIRouter(prefix="/qa-test-hooks", tags=["QA测试钩子"])
logger = get_logger("qa_test_hooks")


class SeedRunningTaskRequest(BaseModel):
    """创建运行中测试任务的请求"""
    project_id: int = Field(..., description="目标项目ID（必须属于当前用户）")
    total_units: int = Field(5, ge=1, le=100, description="总单元数")


class EmitCompleteRequest(BaseModel):
    """触发任务完成推送的请求"""
    total_word_count: int = Field(12000, ge=0, description="推送的总字数")


@router.post("/writing-tasks/seed-running", response_model=ResponseModel[dict])
async def seed_running_writing_task(
    request: SeedRunningTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    为E2E测试创建一个状态为running的写作任务记录。

    只写数据库，不启动Pipeline，因此任务会保持running状态，
    为断网/恢复测试提供持续时间足够的活动任务。
    """
    project_result = await db.execute(
        select(NovelProject).where(
            and_(
                NovelProject.id == request.project_id,
                NovelProject.user_id == current_user.id,
            )
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权访问",
        )

    task = WritingTask(
        project_id=project.id,
        user_id=current_user.id,
        status=TaskStatus.RUNNING,
        total_units=request.total_units,
        completed_units=0,
        config={"qa_test_hook": True},
        start_from=1,
        start_time=datetime.now(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info(
        "QA钩子创建running任务: task_id=%s, project_id=%s, user_id=%s",
        task.id, project.id, current_user.id,
    )
    return ResponseModel(
        success=True,
        code=200,
        message="测试任务已创建",
        data={"task_id": task.id, "project_id": project.id, "status": "running"},
    )


@router.post("/writing-tasks/{task_id}/emit-complete", response_model=ResponseModel[dict])
async def emit_writing_task_complete(
    task_id: int,
    request: EmitCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    将任务置为completed并通过真实WebSocket通道广播task_complete消息。

    消息经由生产同款 WebSocketManager.send_task_complete 发送，
    用于E2E验证前端终态处理（内容校准一次、连接关闭、不再重连）。
    """
    task_result = await db.execute(
        select(WritingTask).where(
            and_(WritingTask.id == task_id, WritingTask.user_id == current_user.id)
        )
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权访问",
        )

    task.status = TaskStatus.COMPLETED
    task.completed_units = task.total_units
    task.end_time = datetime.now()
    await db.commit()

    ws_manager = get_websocket_manager()
    delivered_connections = await ws_manager.send_task_complete(
        task_id=task_id,
        total_units=task.total_units or 0,
        total_word_count=request.total_word_count,
        total_tokens=0,
        total_cost=0.0,
        duration_sec=1.0,
    )

    logger.info(
        "QA钩子推送task_complete: task_id=%s, 送达连接数=%s",
        task_id, delivered_connections,
    )
    return ResponseModel(
        success=True,
        code=200,
        message="task_complete已广播",
        data={"task_id": task_id, "delivered_connections": delivered_connections},
    )
