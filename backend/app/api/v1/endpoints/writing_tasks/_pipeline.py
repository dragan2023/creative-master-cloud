"""
写作任务 API - 后台Pipeline启动函数

@date: 2026-04-24
@version: v3.1.0 (从writing_tasks.py拆分)
"""
from datetime import datetime

from sqlalchemy import select

from app.core.logger import get_logger
from app.models.writing_task import WritingTask, TaskStatus
from app.services.writing_engine.task_lifecycle import transition_task
from app.services.writing_engine.websocket_manager import get_websocket_manager

logger = get_logger("writing_tasks")


async def _start_pipeline(task_id: int, project_id: int, config: dict):
    """
    启动写作Pipeline（后台任务）

    创建Pipeline实例并启动写作任务。Pipeline自己管理数据库会话生命周期。
    """
    from app.services.writing_engine.pipeline import WritingPipeline
    from app.agents.writing.agent_config import AgentConfig
    from app.core.database import async_session_maker

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
            logger.warning(
                f"[配置解析] task_id={task_id}, agents配置为空，尝试自动加载用户默认模型配置")
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
                logger.error(
                    f"[配置解析] task_id={task_id}, user_id={task.user_id}, 无可用模型配置，任务将失败")
                raise ValueError(f"用户未配置默认模型配置: user_id={task.user_id}")

            # 为所有可配置角色统一设置
            all_roles = ["orchestrator", "structural", "writer", "style_editor",
                         "logic_editor", "compliance", "knowledge", "assembler"]
            for role_str in all_roles:
                agents_config[role_str] = {
                    "config_id": default_config.id, "temperature": 0.7}  # 不再设置max_tokens
            logger.info(
                f"[配置解析] 自动使用默认模型配置: id={default_config.id}, name={default_config.name}")

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
                        api_key = api_key_encryption.decrypt(
                            saved_config.encrypted_key)
                        agent_config.update_config(role, AgentModelConfig(
                            model_id=saved_config.model_id,
                            provider=saved_config.provider,
                            api_base=saved_config.api_base,
                            api_key=api_key,
                            temperature=role_config.get("temperature", 0.7),
                            max_tokens=role_config.get("max_tokens", 32000),
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
                        skipped_roles.append(
                            {"role": role_str, "reason": f"config_id={role_config.get('config_id')}未找到"})
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
                        max_tokens=role_config.get("max_tokens", 32000)
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
                skipped_roles.append(
                    {"role": role_str, "reason": f"无效的role值: {e}"})
                logger.warning(
                    f"[配置解析] task_id={task_id}, 无效的role值: role={role_str}, error={e}")
            except Exception as e:
                skipped_roles.append(
                    {"role": role_str, "reason": f"解析异常: {e}"})
                logger.warning(
                    f"[配置解析] task_id={task_id}, 解析Agent配置失败: role={role_str}, error={e}")

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
                task_config["agent_configs"] = agent_config.to_dict().get(
                    "configs", {})
                task.config = task_config
                await db.commit()
                logger.info(
                    f"[配置解析] task_id={task_id}, 已将agent_configs保存到任务配置中")
        except Exception as e:
            logger.warning(
                f"[配置解析] task_id={task_id}, 保存agent_configs到任务配置失败: {e}")

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
                    await transition_task(
                        task, TaskStatus.FAILED, get_websocket_manager(),
                        reason=str(e),
                    )
                    await db.commit()
        except Exception as db_error:
            logger.error(
                f"更新任务失败状态也失败了: task_id={task_id}, error={str(db_error)}")


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
            logger.warning(
                f"写作Pipeline续传失败: task_id={task_id} (可能任务状态不正确或任务不存在)")

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
                            max_tokens=cfg.get("max_tokens", 32000)
                        ))
                    except Exception as e:
                        logger.warning(
                            f"[继续生成] 恢复Agent配置失败: role={role_str}, error={e}")

            # 保持 pending，实际执行器会通过状态机推进至 running。
            task.start_time = task.start_time or datetime.now()
            await db.commit()

        # 创建Pipeline实例
        pipeline = WritingPipeline(task_id=task_id, config=agent_config)
        pipeline.set_ws_manager(get_websocket_manager())

        # 使用continue模式启动
        success = await pipeline.continue_from(start_from, unit_count)

        if success:
            logger.info(
                f"写作Pipeline继续生成完成: task_id={task_id}, start_from={start_from}, unit_count={unit_count}")
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
                    await transition_task(
                        task, TaskStatus.FAILED, get_websocket_manager(),
                        reason=str(e),
                    )
                    await db.commit()
        except Exception as db_error:
            logger.error(
                f"更新任务失败状态也失败了: task_id={task_id}, error={str(db_error)}")
