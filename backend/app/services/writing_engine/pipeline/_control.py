"""
写作流水线 - 中断/续传/继续生成 Mixin

@date: 2026-04-29
@version: v1.2.0 - 幽灵状态即时检测（后端重启即判定为INTERRUPTED）
"""
import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.writing_task import WritingTask, TaskStatus
from app.services.writing_engine.task_lifecycle import transition_task

from app.agents.writing.orchestrator_agent import OrchestratorAgent
from app.agents.writing.base_agent import AgentContext, AgentResult
from app.agents.writing.agent_config import AgentConfig
from ._execute import PipelineExecuteMixin

logger = get_logger("writing_engine.pipeline")


class PipelineControlMixin(PipelineExecuteMixin):
    """中断/续传/继续生成 Mixin"""

    async def interrupt(self) -> bool:
        """中断当前任务

        向Orchestrator发送中断信号，Orchestrator会在下一个检查点检测到中断并更新状态。

        Returns:
            bool: 是否成功触发中断
        """
        if not self._orchestrator:
            logger.warning(f"Orchestrator未初始化，无法中断: task_id={self.task_id}")
            # 尝试直接更新任务状态
            await self._update_task_status_interrupted()
            return False

        # 检查任务状态（使用task属性或从数据库加载）
        task_status = None
        if self.task:
            task_status = self.task.status
        else:
            # 尝试从数据库加载任务状态
            from sqlalchemy import select
            from app.core.database import async_session_maker
            async with async_session_maker() as db:
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                task = result.scalar_one_or_none()
                if task:
                    task_status = task.status
                    self.task = task

        if task_status != TaskStatus.RUNNING:
            logger.warning(
                f"任务不在运行状态，无法中断: task_id={self.task_id}, status={task_status}")
            return False

        try:
            # 发送中断信号给Orchestrator
            await self._orchestrator.interrupt()
            logger.info(f"中断信号已发送到Orchestrator: task_id={self.task_id}")

            # 发送WebSocket通知
            if self._ws_manager:
                try:
                    await self._ws_manager.send_status_change(
                        task_id=self.task_id,
                        old_status=TaskStatus.RUNNING,
                        new_status=TaskStatus.INTERRUPTED
                    )
                except Exception as ws_error:
                    logger.warning(
                        f"发送中断WebSocket通知失败: task_id={self.task_id}, error={ws_error}")

            return True
        except Exception as e:
            logger.error(f"发送中断信号失败: task_id={self.task_id}, error={str(e)}")
            # 尝试直接更新任务状态
            await self._update_task_status_interrupted()
            return False

    async def _update_task_status_interrupted(self) -> None:
        """直接更新任务状态为中断（降级处理）"""
        try:
            from sqlalchemy import update
            from app.core.database import async_session_maker
            async with async_session_maker() as db:
                task = (await db.execute(
                    select(WritingTask).where(WritingTask.id == self.task_id)
                )).scalar_one_or_none()
                if not task:
                    return
                await transition_task(
                    task, TaskStatus.INTERRUPTED, self._ws_manager,
                    reason="任务执行被中断",
                )
                await db.commit()
                logger.info(f"已直接更新任务状态为中断: task_id={self.task_id}")
        except Exception as e:
            logger.error(f"更新任务状态失败: task_id={self.task_id}, error={e}")

    async def resume(self) -> bool:
        """从检查点续传任务

        注意：resume需要在_execute中或有自己的数据库会话中调用

        Returns:
            bool: 是否成功触发续传
        """
        # 如果任务未加载，先尝试加载
        if not self.task:
            logger.info(f"任务未加载，尝试加载任务: task_id={self.task_id}")
            from app.core.database import async_session_maker

            async with async_session_maker() as db:
                self.db = db
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return False

                # 验证任务状态（含幽灵状态检测）
                if self.task.status == TaskStatus.RUNNING:
                    # 检查内存中是否有活跃的Pipeline
                    if self.task.id in type(self)._active_pipelines:
                        logger.warning(
                            f"任务正在运行中，无法续传: task_id={self.task.id}, status={self.task.status}")
                        return False
                    else:
                        # 内存中没有活跃Pipeline，说明是幽灵状态（后端已重启）
                        logger.warning(
                            f"检测到幽灵状态RUNNING，自动转为INTERRUPTED: task_id={self.task.id}")
                        # 更新状态为INTERRUPTED
                        await transition_task(
                            self.task, TaskStatus.INTERRUPTED, self._ws_manager,
                            reason="server_restarted",
                        )
                        await db.commit()

                if self.task.status not in (
                    TaskStatus.PENDING, TaskStatus.INTERRUPTED, TaskStatus.FAILED,
                ):
                    logger.warning(
                        f"任务不在可续传状态: task_id={self.task.id}, status={self.task.status}")
                    return False

                # 保存任务信息后关闭会话（后续会在_resume_execute中创建新会话）
                self.db = None

            logger.info(
                f"任务已加载: task_id={self.task.id}, status={self.task.status}")
        else:
            # 任务已加载，验证状态（含幽灵状态检测）
            if self.task.status == TaskStatus.RUNNING:
                # 检查内存中是否有活跃的Pipeline
                if self.task.id in type(self)._active_pipelines:
                    logger.warning(
                        f"任务正在运行中，无法续传: task_id={self.task.id}, status={self.task.status}")
                    return False
                else:
                    # 内存中没有活跃Pipeline，说明是幽灵状态（后端已重启）
                    logger.warning(
                        f"检测到幽灵状态RUNNING，自动转为INTERRUPTED: task_id={self.task.id}")
                    # 需要在数据库会话中更新状态
                    from app.core.database import async_session_maker
                    async with async_session_maker() as db:
                        await transition_task(
                            self.task, TaskStatus.INTERRUPTED, self._ws_manager,
                            reason="server_restarted",
                        )
                        await db.commit()

            if self.task.status not in (
                TaskStatus.PENDING, TaskStatus.INTERRUPTED, TaskStatus.FAILED,
            ):
                logger.warning(
                    f"任务不在可续传状态: task_id={self.task.id}, status={self.task.status}")
                return False

        # 注册到活跃列表
        type(self)._active_pipelines[self.task.id] = self

        # 启动续传任务（在_resume_execute中创建新的数据库会话）
        context = await self._build_context()
        self._execution_task = asyncio.create_task(
            self._resume_execute(context))

        logger.info(f"续传任务已启动: task_id={self.task.id}")
        return True

    async def continue_from(self, start_from: int, unit_count: int) -> bool:
        """从指定位置继续生成

        与resume不同，continue_from是在任务完成后追加新单元。

        Args:
            start_from: 起始单元索引
            unit_count: 要生成的单元数

        Returns:
            bool: 是否成功触发
        """
        # 如果任务未加载，先尝试加载
        if not self.task:
            logger.info(f"任务未加载，尝试加载任务: task_id={self.task_id}")
            from app.core.database import async_session_maker
            async with async_session_maker() as db:
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return False

        # 注册到活跃列表
        type(self)._active_pipelines[self.task.id] = self

        # 启动继续生成任务
        self._execution_task = asyncio.create_task(
            self._continue_execute(start_from, unit_count)
        )

        logger.info(
            f"继续生成任务已启动: task_id={self.task.id}, start_from={start_from}, unit_count={unit_count}")
        return True

    async def _continue_execute(self, start_from: int, unit_count: int) -> None:
        """执行继续生成任务（内部方法）

        Args:
            start_from: 起始单元索引
            unit_count: 要生成的单元数
        """
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            self.db = db
            try:
                # 加载任务对象
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return

                # 从任务记录恢复模型配置
                if self.task.config:
                    task_config_data = self.task.config if isinstance(
                        self.task.config, dict) else {}
                    agent_configs = task_config_data.get("agent_configs", {})
                    if agent_configs:
                        self.config = AgentConfig.from_dict(
                            {"configs": agent_configs})
                        await self._reload_api_keys(db)
                    else:
                        await self._auto_load_default_config(db)
                else:
                    await self._auto_load_default_config(db)

                # 创建OrchestratorAgent
                self._orchestrator = OrchestratorAgent(
                    db=db, config=self.config)

                if self._stats_interceptor:
                    self._orchestrator.set_stats_interceptor(
                        self._stats_interceptor)

                if self._ws_manager:
                    self._orchestrator.set_ws_manager(self._ws_manager)

                # 更新状态为运行中
                await transition_task(
                    self.task, TaskStatus.RUNNING, self._ws_manager,
                )
                await db.commit()

                # 构建上下文，设置继续生成的参数
                context = await self._build_context()
                # 覆盖上下文中的起始位置和数量
                context.config["start_from"] = start_from
                context.config["unit_count"] = unit_count
                context.config["total_units"] = self.task.total_units

                # 执行Orchestrator（使用continue模式）
                self._result = await self._orchestrator.continue_from(context, start_from, unit_count)

                # 处理执行结果
                if self._result.success:
                    await transition_task(
                        self.task, TaskStatus.COMPLETED, self._ws_manager,
                    )
                    self.task.completed_units = self.task.total_units
                    logger.info(f"继续生成任务完成: task_id={self.task.id}")
                else:
                    await transition_task(
                        self.task, TaskStatus.FAILED, self._ws_manager,
                        reason=self._result.errors[0] if self._result.errors else "未知错误",
                    )
                    logger.error(
                        f"继续生成任务失败: task_id={self.task.id}, error={self.task.error_message}")

                await db.commit()

            except asyncio.CancelledError:
                if self.task:
                    logger.info(f"继续生成任务被中断: task_id={self.task.id}")
                    await transition_task(
                        self.task, TaskStatus.INTERRUPTED, self._ws_manager,
                        reason="任务执行被取消",
                    )
                    try:
                        await db.commit()
                    except Exception:
                        logger.warning("继续生成任务中断时数据库提交失败,连接可能已关闭")

            except Exception as e:
                logger.exception(
                    f"继续生成任务执行异常: task_id={self.task_id}, error={str(e)}")
                if self.task:
                    await transition_task(
                        self.task, TaskStatus.FAILED, self._ws_manager,
                        reason=str(e),
                    )
                    await db.commit()

            finally:
                type(self).remove_active_pipeline(self.task_id)
                self.db = None

    async def _resume_execute(self, context: AgentContext) -> None:
        """执行续传任务（内部方法）

        在自己的数据库会话中执行续传任务。

        Args:
            context: 执行上下文
        """
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            self.db = db
            try:
                # 加载任务对象
                from sqlalchemy import select
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return

                # 从任务记录恢复模型配置
                if self.task.config:
                    task_config_data = self.task.config if isinstance(
                        self.task.config, dict) else {}
                    logger.info(
                        f"[续传] task.config 存在，类型: {type(self.task.config)}, keys: {list(task_config_data.keys()) if task_config_data else 'empty'}")
                    # 提取 agent_configs 部分
                    agent_configs = task_config_data.get("agent_configs", {})
                    logger.info(
                        f"[续传] agent_configs: {list(agent_configs.keys()) if agent_configs else 'empty'}")
                    if agent_configs:
                        self.config = AgentConfig.from_dict(
                            {"configs": agent_configs})
                        logger.info(
                            f"从任务记录恢复模型配置: task_id={self.task_id}, agents={list(agent_configs.keys())}")
                        # 从数据库重新加载API Key
                        await self._reload_api_keys(db)
                    else:
                        # 兼容旧格式：整个 config 就是 agent_configs
                        if any(k in task_config_data for k in ["writer", "structural", "editor", "stylist", "compliance"]):
                            self.config = AgentConfig.from_dict(
                                {"configs": task_config_data})
                            logger.info(
                                f"从任务记录恢复模型配置(兼容格式): task_id={self.task_id}")
                            # 从数据库重新加载API Key
                            await self._reload_api_keys(db)
                        else:
                            logger.warning(
                                f"[续传] 未找到 agent_configs 且不匹配兼容格式，尝试自动加载用户默认模型配置")
                            # 尝试自动加载用户默认模型配置
                            await self._auto_load_default_config(db)
                else:
                    logger.warning(f"[续传] task.config 为空，尝试自动加载用户默认模型配置")
                    await self._auto_load_default_config(db)

                # 创建OrchestratorAgent
                self._orchestrator = OrchestratorAgent(
                    db=db, config=self.config)

                if self._stats_interceptor:
                    self._orchestrator.set_stats_interceptor(
                        self._stats_interceptor)

                # 设置WebSocket管理器
                if self._ws_manager:
                    self._orchestrator.set_ws_manager(self._ws_manager)

                # 更新状态
                await transition_task(
                    self.task, TaskStatus.RUNNING, self._ws_manager,
                )
                await db.commit()

                # 调用Orchestrator的resume方法
                self._result = await self._orchestrator.resume(context)

                # 处理执行结果
                if self._result.success:
                    await transition_task(
                        self.task, TaskStatus.COMPLETED, self._ws_manager,
                    )
                    logger.info(f"续传任务完成: task_id={self.task.id}")
                else:
                    await transition_task(
                        self.task, TaskStatus.FAILED, self._ws_manager,
                        reason=self._result.errors[0] if self._result.errors else "未知错误",
                    )
                    logger.error(
                        f"续传任务失败: task_id={self.task.id}, error={self.task.error_message}")

                await db.commit()

            except asyncio.CancelledError:
                if self.task:
                    logger.info(f"续传任务被中断: task_id={self.task.id}")
                    await transition_task(
                        self.task, TaskStatus.INTERRUPTED, self._ws_manager,
                        reason="任务执行被取消",
                    )
                    try:
                        await db.commit()
                    except Exception:
                        logger.warning("续传任务中断时数据库提交失败,连接可能已关闭")
                else:
                    logger.info(f"续传任务被中断: task_id={self.task_id}")

            except Exception as e:
                logger.exception(
                    f"续传任务执行异常: task_id={self.task_id}, error={str(e)}")
                if self.task:
                    await transition_task(
                        self.task, TaskStatus.FAILED, self._ws_manager,
                        reason=str(e),
                    )
                    await db.commit()

            finally:
                type(self).remove_active_pipeline(self.task_id)
                self.db = None
