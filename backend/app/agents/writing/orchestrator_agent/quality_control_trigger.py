"""
单元质控触发器 - 实时质控机制

在单元生成完成后异步触发质控检测和自动修正。

@date: 2026-04-20
@version: v2.0.0
@author: AI Assistant
"""
import asyncio
from typing import Callable, Optional, Dict, Any
from datetime import datetime

from app.core.logger import get_logger

logger = get_logger("quality_control_trigger")


async def trigger_unit_quality_control(
    project_id: int,
    unit_index: int,
    content: str,
    user_id: Optional[int] = None,
    ws_send_func: Optional[Callable] = None
):
    """
    异步触发单元质控检测

    此函数在单元生成完成后被调用,在后台执行质控检测,不阻塞主流程。
    使用独立的数据库会话,避免会话生命周期问题。

    Args:
        project_id: 项目ID
        unit_index: 单元序号
        content: 单元内容
        user_id: 用户ID
        ws_send_func: WebSocket消息发送函数
    """
    from app.core.database import async_session_maker

    # 创建独立的数据库会话
    async with async_session_maker() as db:
        try:
            logger.info(
                f"[质控触发] 开始质控: project_id={project_id}, "
                f"unit_index={unit_index}, content_length={len(content)}"
            )

            # 发送质控开始消息
            if ws_send_func:
                logger.info(f"[质控触发] 发送质控开始消息: unit={unit_index}")
                try:
                    await ws_send_func("unit_quality_control", {
                        "unit_index": unit_index,
                        "status": "running",
                        "message": f"第{unit_index}单元质控检测中..."
                    })
                except Exception as ws_err:
                    logger.warning(f"[质控触发] 发送开始消息失败: {ws_err}")
            else:
                logger.warning(
                    f"[质控触发] ws_send_func为None,无法发送消息: unit={unit_index}")

            # 导入必要的模块
            from app.api.v1.endpoints.novel_writer.quality_control_v2 import (
                analyze_single_unit_quality,
                UnitQualityControlRequest
            )
            from app.models import User
            from sqlalchemy import select
            from app.models import User as UserModel

            # 构建请求
            request = UnitQualityControlRequest(
                project_id=project_id,
                unit_index=unit_index,
                content=content,
                dimensions=[
                    "unit_structure",
                    "unit_character",
                    "unit_consistency",
                    "unit_timeline_space",
                    "unit_ooc"
                ],
                depth="standard",
                auto_fix=True,
                auto_fix_threshold=0.8
            )

            # 获取用户对象
            user_query = select(UserModel).where(UserModel.id == user_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()

            if not user:
                logger.warning(f"[质控触发] 用户 {user_id} 不存在,跳过质控")
                return

            # 调用质控API
            result = await analyze_single_unit_quality(
                project_id=project_id,
                unit_index=unit_index,
                request=request,
                current_user=user,
                db=db
            )

            # 处理结果
            if result.success:
                qc_data = result.data
                logger.info(
                    f"[质控触发] 质控完成: unit={unit_index}, "
                    f"score={qc_data.get('score')}, "
                    f"issues={qc_data.get('issues_count')}, "
                    f"fixed={qc_data.get('fixed_count')}"
                )

                # 发送质控完成消息
                if ws_send_func:
                    try:
                        await ws_send_func("unit_quality_control", {
                            "unit_index": unit_index,
                            "status": "completed",
                            "score": qc_data.get('score', 0),
                            "issues_count": qc_data.get('issues_count', 0),
                            "fixed_count": qc_data.get('fixed_count', 0),
                            "message": f"质控完成: 得分{qc_data.get('score', 0):.1f}, 发现{qc_data.get('issues_count', 0)}个问题, 修正{qc_data.get('fixed_count', 0)}个",
                            "report": qc_data.get('report'),  # 添加完整报告
                            "issues": qc_data.get('issues'),  # 添加问题列表
                            # 添加修正列表
                            "fixes_applied": qc_data.get('fixes_applied'),
                            # 修正前内容
                            "original_content": qc_data.get('original_content'),
                            # 修正后内容
                            "fixed_content": qc_data.get('fixed_content')
                        })
                        logger.info(f"[质控触发] 质控完成消息已发送: unit={unit_index}")
                    except Exception as ws_err:
                        logger.warning(f"[质控触发] 发送完成消息失败: {ws_err}")
            else:
                logger.error(f"[质控触发] 质控失败: {result.message}")

                # 发送质控失败消息
                if ws_send_func:
                    try:
                        await ws_send_func("unit_quality_control", {
                            "unit_index": unit_index,
                            "status": "failed",
                            "message": f"质控失败: {result.message}"
                        })
                    except Exception as ws_err:
                        logger.warning(f"[质控触发] 发送失败消息失败: {ws_err}")

            # 提交数据库更改
            await db.commit()

        except Exception as e:
            logger.error(f"[质控触发] 异常: {e}", exc_info=True)
            await db.rollback()

            # 发送错误消息
            if ws_send_func:
                try:
                    await ws_send_func("unit_quality_control", {
                        "unit_index": unit_index,
                        "status": "failed",
                        "message": f"质控异常: {str(e)}"
                    })
                except Exception as ws_err:
                    logger.warning(f"[质控触发] 发送异常消息失败: {ws_err}")
