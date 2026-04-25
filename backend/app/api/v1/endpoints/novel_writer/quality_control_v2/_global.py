"""质量管控 v2.0 - 全局大纲质控端点 + 导入大纲自动质控修正"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
from fastapi import Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_user_from_query_or_header
from app.models import User
from app.schemas.common import ResponseModel

from ..utils import router, logger
from ._common import (
    GlobalOutlineQCRequest, GlobalOutlineReviseRequest,
    ImportedOutlineAutoReviseRequest,
    get_qc_subscriber, _qc_subscriber, publish_qc_progress
)


@router.post("/quality-control/global-outline/{project_id}")
async def analyze_global_outline_quality(
    project_id: int,
    request: GlobalOutlineQCRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    对全局大纲执行质量检测(用户手动触发)

    注意:
    - project_id=0 表示两阶段大纲模式的全局大纲阶段(无项目)
    - project_id>0 表示普通模式或单元概述阶段(有项目)

    LLM分析可能需要10-20分钟,前端需设置足够超时时间(1200000ms)

    v1.1新增: 支持SSE实时进度推送
    """
    try:
        # v1.1新增: 生成task_id用于SSE推送
        task_id = f"qc_{current_user.id}_{uuid.uuid4().hex[:8]}"

        logger.info(
            f"[全局大纲质控API] 开始检测: project_id={project_id}, "
            f"user_id={current_user.id}, dimensions={request.dimensions}, task_id={task_id}"
        )

        # 1. 获取全局大纲内容
        global_outline_content = None
        project = None  # 初始化project变量,避免作用域问题

        if project_id == 0:
            # 两阶段大纲模式: 全局大纲内容由前端传递
            logger.info("[全局大纲质控API] 两阶段模式,使用前端传递的内容")
            global_outline_content = request.existing_outline or ''
        else:
            # 普通模式: 从数据库获取项目
            from sqlalchemy import select
            from app.models import NovelProject

            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                logger.error(f"[全局大纲质控API] 项目不存在: {project_id}")
                return ResponseModel(
                    success=False,
                    message=f"项目不存在: {project_id}"
                )

            global_outline_content = getattr(
                project, 'global_outline_content', None) or ''
            logger.info(f"[全局大纲质控API] 从数据库获取项目: {project_id}")

        if not global_outline_content:
            logger.error("[全局大纲质控API] 全局大纲内容为空")
            return ResponseModel(
                success=False,
                message="全局大纲内容为空,请先生成全局大纲"
            )

        logger.info(f"[全局大纲质控API] 大纲内容长度: {len(global_outline_content)} 字")

        # 3. 调用质控分析
        from app.services.outline_generator import get_outline_generator
        outline_generator = get_outline_generator(db)

        quality_report = await outline_generator.analyze_global_outline_quality(
            global_outline_content=global_outline_content,
            project=project,  # 两阶段模式下为None,普通模式下为项目对象
            user_id=current_user.id,
            dimensions=request.dimensions,
            depth=request.depth,
            task_id=task_id  # v1.1新增: 传递task_id以支持SSE推送
        )

        # 4. 保存质控报告到项目(仅普通模式)
        if project is not None:
            project.global_outline_quality_report = quality_report
            await db.commit()
            logger.info(f"[全局大纲质控API] 已保存质控报告到项目: {project_id}")
        else:
            logger.info("[全局大纲质控API] 两阶段模式,跳过数据库保存")

        logger.info(
            f"[全局大纲质控API] 检测完成: project_id={project_id}, "
            f"overall_score={quality_report.get('overall_score', 0)}"
        )

        return ResponseModel(
            success=True,
            message="质量检测完成",
            data=quality_report,
            task_id=task_id  # v1.1新增: 返回task_id供前端订阅SSE
        )

    except Exception as e:
        logger.error(f"[全局大纲质控API] 检测失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"质量检测失败: {str(e)}"
        )


@router.post("/quality-control/global-outline/{project_id}/revise")
async def revise_global_outline(
    project_id: int,
    request: GlobalOutlineReviseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据质控报告修正全局大纲

    注意: LLM修正可能需要10-20分钟,前端需设置足够超时时间(1200000ms)
    修正后直接更新 project.global_outline_content 字段
    """
    try:
        logger.info(
            f"[全局大纲修正API] 开始修正: project_id={project_id}, "
            f"user_id={current_user.id}, issues_count={len(request.issues_to_fix)}"
        )

        # 1. 获取项目和大纲内容
        project = None
        original_outline = None

        if project_id == 0:
            # 两阶段大纲模式: 从质控报告中获取原始大纲
            logger.info("[全局大纲修正API] 两阶段模式,从质控报告获取原始大纲")
            original_outline = request.quality_report.get(
                'original_outline', '')
            if not original_outline:
                return ResponseModel(
                    success=False,
                    message="质控报告中缺少原始大纲内容"
                )
        else:
            # 普通模式: 从数据库获取项目
            from sqlalchemy import select
            from app.models import NovelProject

            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                return ResponseModel(
                    success=False,
                    message=f"项目不存在: {project_id}"
                )

            original_outline = getattr(
                project, 'global_outline_content', None) or ''

        if not original_outline:
            return ResponseModel(
                success=False,
                message="全局大纲内容为空"
            )

        # 3. 调用修正方法
        from app.services.outline_generator import get_outline_generator
        outline_generator = get_outline_generator(db)

        revision_result = await outline_generator.revise_global_outline_by_quality(
            original_outline=original_outline,
            quality_report=request.quality_report,
            issues_to_fix=request.issues_to_fix,
            project=project,  # 两阶段模式下为None
            user_id=current_user.id
        )

        if not revision_result.get("success"):
            return ResponseModel(
                success=False,
                message=f"修正失败: {revision_result.get('error', '未知错误')}"
            )

        # 4. 保存修正后的大纲
        revised_content = revision_result.get("revised_content")

        if project is not None:
            # 普通模式: 保存到数据库
            project.global_outline_content = revised_content
            project.global_outline_quality_report = {
                **request.quality_report,
                "revised": True,
                "revised_at": datetime.now().isoformat(),
                "revised_issues": request.issues_to_fix
            }
            await db.commit()
            logger.info(f"[全局大纲修正API] 已保存修正内容到项目: {project_id}")
        else:
            # 两阶段模式: 返回修正内容,由前端处理
            logger.info("[全局大纲修正API] 两阶段模式,返回修正内容给前端")

        logger.info(
            f"[全局大纲修正API] 修正完成: project_id={project_id}, "
            f"original_length={len(original_outline)}, "
            f"revised_length={len(revised_content)}"
        )

        return ResponseModel(
            success=True,
            message="全局大纲修正完成",
            data={
                "revised_content": revised_content,
                "changes": revision_result.get("changes", []),
                "original_length": len(original_outline),
                "revised_length": len(revised_content)
            }
        )

    except Exception as e:
        logger.error(f"[全局大纲修正API] 修正失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"修正失败: {str(e)}"
        )


@router.post("/quality-control/imported-outline/auto-revise", response_model=ResponseModel)
async def auto_revise_imported_outline(
    request: ImportedOutlineAutoReviseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    对导入的大纲自动执行质控修正（v2.3新增）

    用于"导入已有大纲"场景，用户点击"重新检测"按钮时调用。
    自动执行质量检测并修正所有问题。
    """
    try:
        logger.info(
            f"[导入大纲自动质控] 用户 {current_user.id} 请求自动质控修正, "
            f"内容长度: {len(request.outline_content)}"
        )

        if not request.outline_content or len(request.outline_content.strip()) < 100:
            return ResponseModel(
                success=False,
                message="大纲内容过短，无法进行质量检测"
            )

        # 获取大纲生成器
        from app.services.outline_generator import get_outline_generator
        outline_generator = get_outline_generator(db)

        # 执行自动质控修正
        qc_result = await outline_generator._auto_qc_and_revise(
            content=request.outline_content,
            user_id=current_user.id,
            llm_provider=None,  # 会在方法内部获取
            dimensions=request.dimensions,
            depth=request.depth
        )

        if qc_result.get("success"):
            revised_content = qc_result.get("revised_content")
            issues_fixed = qc_result.get("issues_fixed", 0)
            qc_report = qc_result.get("qc_report")

            # 更新质控报告标记
            if qc_report:
                qc_report["source"] = "imported_outline"
                qc_report["auto_applied"] = True
                qc_report["applied_at"] = datetime.now().isoformat()

            logger.info(
                f"[导入大纲自动质控] 完成，修正 {issues_fixed} 个问题"
            )

            return ResponseModel(
                success=True,
                message=f"质量检测完成，已修正 {issues_fixed} 个问题" if issues_fixed > 0 else "质量检测完成，未发现需要修正的问题",
                data={
                    "revised_content": revised_content,
                    "issues_fixed": issues_fixed,
                    "qc_report": qc_report,
                    "original_length": len(request.outline_content),
                    "revised_length": len(revised_content) if revised_content else len(request.outline_content)
                }
            )
        else:
            error_msg = qc_result.get("error", "未知错误")
            logger.warning(f"[导入大纲自动质控] 执行失败: {error_msg}")
            return ResponseModel(
                success=False,
                message=f"质量检测失败: {error_msg}",
                data={
                    "qc_report": qc_result.get("qc_report")
                }
            )

    except Exception as e:
        logger.error(f"[导入大纲自动质控] 执行失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"质量检测失败: {str(e)}"
        )


# ==================== SSE事件端点 ====================

async def event_generator(task_id: str, queue: asyncio.Queue):
    """
    SSE事件生成器

    格式:
    event: progress
    data: {"dimension": "global_structure", "status": "started", "progress": 0}
    """
    try:
        # 发送连接成功事件
        yield f"event: connected\ndata: {json.dumps({'task_id': task_id, 'message': 'SSE连接成功'})}\n\n"

        # 持续推送进度事件
        while True:
            try:
                # 等待新事件(超时30秒发送心跳)
                event = await asyncio.wait_for(queue.get(), timeout=30.0)

                # 检查是否为结束事件
                if event.get("type") == "completed" or event.get("type") == "error":
                    # 发送最后的事件
                    yield f"event: {event.get('type', 'progress')}\ndata: {json.dumps(event)}\n\n"
                    logger.info(
                        f"[SSE推送] 任务结束: task_id={task_id}, type={event.get('type')}")
                    break

                # 推送进度事件
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"

            except asyncio.TimeoutError:
                # 发送心跳保活
                yield f": heartbeat\n\n"

    except Exception as e:
        logger.error(f"[SSE推送] 事件生成器异常: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    finally:
        # 清理订阅
        _qc_subscriber.unsubscribe(task_id, queue)
        logger.info(f"[SSE推送] 连接关闭: task_id={task_id}")


@router.get("/quality-control/global-outline/{task_id}/events")
async def subscribe_qc_progress(
    task_id: str,
    current_user: User = Depends(
        get_current_user_from_query_or_header)  # 支持Query参数认证（SSE场景）
):
    """
    SSE端点: 订阅全局大纲质控进度

    使用方式:
    const eventSource = new EventSource(`/api/v1/novel-writer/quality-control/global-outline/${taskId}/events?token=xxx`)

    事件类型:
    - connected: 连接成功
    - progress: 进度更新
    - completed: 完成
    - error: 错误
    """
    logger.info(
        f"[SSE端点] 订阅质控进度: task_id={task_id}, user_id={current_user.id}")

    # 创建订阅队列
    queue = _qc_subscriber.subscribe(task_id)

    # 返回SSE流
    return StreamingResponse(
        event_generator(task_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
            "Access-Control-Allow-Origin": "*"
        }
    )
