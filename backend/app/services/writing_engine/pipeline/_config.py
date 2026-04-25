"""
写作流水线 - 模型配置加载 Mixin

@date: 2026-04-24
@version: v1.0.0
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.writing_task import WritingTask
from app.agents.writing.agent_config import AgentConfig, AgentModelConfig
from app.agents.writing.base_agent import AgentRole
from ._base import PipelineBase

logger = get_logger("writing_engine.pipeline")


class PipelineConfigMixin(PipelineBase):
    """模型配置加载 Mixin"""

    async def _reload_api_keys(self, db: AsyncSession) -> None:
        """从数据库重新加载API Key

        续传时根据config_id从数据库重新加载API Key，确保续传后能正常调用LLM。

        Args:
            db: 数据库会话
        """
        from app.models.writing_model_config import WritingModelConfig as WMC
        from app.core.security import api_key_encryption

        if not self.config:
            return

        for role_str, model_config in self.config.configs.items():
            try:
                # 如果有config_id，从数据库重新加载API Key
                if model_config.config_id:
                    result = await db.execute(
                        select(WMC).where(
                            WMC.id == model_config.config_id).limit(1)
                    )
                    saved_config = result.scalar_one_or_none()
                    if saved_config:
                        api_key = api_key_encryption.decrypt(
                            saved_config.encrypted_key)
                        # 更新配置中的API Key
                        role = AgentRole(role_str)
                        self.config.update_config(role, AgentModelConfig(
                            model_id=saved_config.model_id,
                            provider=saved_config.provider,
                            api_base=saved_config.api_base,
                            api_key=api_key,
                            temperature=model_config.temperature,
                            max_tokens=model_config.max_tokens,
                            config_id=saved_config.id
                        ))
                        logger.info(
                            f"从数据库重新加载API Key: role={role_str}, config_id={saved_config.id}")
                    else:
                        logger.warning(
                            f"未找到模型配置: role={role_str}, config_id={model_config.config_id}")
            except Exception as e:
                logger.warning(f"重新加载API Key失败: role={role_str}, error={e}")

    async def _auto_load_default_config(self, db: AsyncSession) -> None:
        """自动加载用户的默认模型配置

        当续传时 task.config 中没有 agent_configs 时，尝试自动加载用户的默认模型配置。

        Args:
            db: 数据库会话
        """
        from app.models.writing_model_config import WritingModelConfig as WMC
        from app.core.security import api_key_encryption

        if not self.task:
            return

        try:
            # 查询用户的第一个活跃模型配置
            result = await db.execute(
                select(WMC).where(
                    WMC.user_id == self.task.user_id,
                    WMC.is_active == True
                ).order_by(WMC.updated_at.desc()).limit(1)
            )
            default_config = result.scalar_one_or_none()

            if default_config:
                api_key = api_key_encryption.decrypt(
                    default_config.encrypted_key)
                # 为所有可配置角色设置同一模型
                configurable_roles = [
                    AgentRole.ORCHESTRATOR, AgentRole.STRUCTURAL, AgentRole.WRITER,
                    AgentRole.LOGIC_EDITOR, AgentRole.STYLE_EDITOR, AgentRole.COMPLIANCE,
                    AgentRole.KNOWLEDGE
                ]
                for role in configurable_roles:
                    self.config.update_config(role, AgentModelConfig(
                        model_id=default_config.model_id,
                        provider=default_config.provider,
                        api_base=default_config.api_base,
                        api_key=api_key,
                        temperature=0.7,
                        max_tokens=4096,
                        config_id=default_config.id
                    ))
                logger.info(
                    f"[续传] 自动加载用户默认模型配置: user_id={self.task.user_id}, config_id={default_config.id}, model={default_config.model_id}")
            else:
                logger.error(f"[续传] 用户没有可用的模型配置: user_id={self.task.user_id}")
        except Exception as e:
            logger.error(f"[续传] 自动加载默认模型配置失败: {e}")
