"""
QA测试钩子端点（仅测试环境启用）

模块: api.v1.endpoints
文件: qa_test_hooks.py
功能: 为断网恢复等E2E测试提供可控的任务数据准备与真实WebSocket推送触发。

安全边界:
    - 仅当 QA_TEST_HOOKS=1 且 RUNTIME_ENV=test 时由 main.py 条件挂载
    - 所有端点仍要求登录认证，且只能操作当前用户自己的项目/任务
    - 任务必须存在于本进程私有registry；数据库字段不能伪造QA操作权
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

# 进程内私有登记是QA操作权的唯一来源；普通API无法写入或伪造。
_qa_task_registry: dict[int, tuple[int, int]] = {}


def _register_qa_task(task_id: int, user_id: int, project_id: int) -> None:
    _qa_task_registry[task_id] = (user_id, project_id)


def _require_qa_task_owner(task_id: int, user_id: int) -> int:
    registration = _qa_task_registry.get(task_id)
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="任务不是本进程创建的QA任务",
        )
    owner_id, project_id = registration
    if owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作其他用户的QA任务",
        )
    return project_id


def _clear_qa_task_registry_for_tests() -> None:
    """仅供单元测试隔离模块进程状态。"""
    _qa_task_registry.clear()


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
    _register_qa_task(task.id, current_user.id, project.id)

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
    将任务置为completed并通过真实WebSocket通道广播生产status_change消息。

    消息经由Pipeline._notify_status_change同款WebSocketManager.send_status_change发送，
    用于E2E验证前端终态处理（内容校准一次、连接关闭、不再重连）。
    """
    registered_project_id = _require_qa_task_owner(task_id, current_user.id)
    task_result = await db.execute(
        select(WritingTask).where(
            and_(
                WritingTask.id == task_id,
                WritingTask.user_id == current_user.id,
                WritingTask.project_id == registered_project_id,
            )
        )
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权访问",
        )

    if task.status != TaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="QA任务不处于running状态",
        )

    old_status = task.status
    task.status = TaskStatus.COMPLETED
    task.completed_units = task.total_units
    task.end_time = datetime.now()
    await db.commit()

    ws_manager = get_websocket_manager()
    delivered_connections = await ws_manager.send_status_change(
        task_id=task_id,
        old_status=old_status,
        new_status=TaskStatus.COMPLETED,
    )

    logger.info(
        "QA钩子推送生产status_change: task_id=%s, 送达连接数=%s",
        task_id, delivered_connections,
    )
    return ResponseModel(
        success=True,
        code=200,
        message="status_change已广播",
        data={"task_id": task_id, "delivered_connections": delivered_connections},
    )


@router.delete("/writing-tasks/{task_id}", response_model=ResponseModel[dict])
async def cleanup_qa_writing_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除当前用户由本进程QA hook创建的任务及其专用测试项目。"""
    project_id = _require_qa_task_owner(task_id, current_user.id)
    task_result = await db.execute(
        select(WritingTask).where(
            and_(
                WritingTask.id == task_id,
                WritingTask.user_id == current_user.id,
                WritingTask.project_id == project_id,
            )
        )
    )
    task = task_result.scalar_one_or_none()
    project_result = await db.execute(
        select(NovelProject).where(
            and_(
                NovelProject.id == project_id,
                NovelProject.user_id == current_user.id,
            )
        )
    )
    project = project_result.scalar_one_or_none()
    if not task or not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QA任务或项目不存在",
        )

    await db.delete(task)
    await db.flush()
    await db.delete(project)
    await db.commit()
    _qa_task_registry.pop(task_id, None)
    logger.info("QA钩子清理任务与项目: task_id=%s, project_id=%s", task_id, project_id)
    return ResponseModel(
        success=True,
        code=200,
        message="QA任务与项目已清理",
        data={"task_id": task_id, "project_id": project_id},
    )
