"""
通用生成状态持久化管理器

为所有创意生成模块提供统一的状态保存和恢复机制。

使用示例:
    # 在生成过程中保存状态
    state_manager = GenerationStateManager(db, generation_id)
    
    # 保存短视频脚本生成状态
    await state_manager.save_stage(
        stage='script_generating',
        stage_data={
            'current_script': '...',
            'progress': 0.5
        },
        session_context={
            'revision_messages': [...],
            'user_inputs': {...}
        }
    )
    
    # 恢复状态
    state = await state_manager.get_latest_state()
    if state:
        # 恢复生成
        pass
"""
from typing import Any, Dict, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.generation import Generation, GenerationStatus
from app.core.logger import get_logger

logger = get_logger(__name__)


class GenerationStateManager:
    """生成状态管理器"""

    def __init__(self, db: AsyncSession, generation_id: Optional[int] = None):
        self.db = db
        self.generation_id = generation_id
        self.generation: Optional[Generation] = None

    async def load_generation(self) -> Optional[Generation]:
        """加载生成记录"""
        if not self.generation_id:
            return None

        stmt = select(Generation).where(Generation.id == self.generation_id)
        result = await self.db.execute(stmt)
        self.generation = result.scalar_one_or_none()
        return self.generation

    async def save_stage(
        self,
        stage: str,
        stage_data: Dict[str, Any],
        session_context: Optional[Dict[str, Any]] = None,
        status: GenerationStatus = GenerationStatus.PROCESSING
    ) -> Generation:
        """
        保存当前生成阶段的状态

        Args:
            stage: 阶段标识(由各模块自定义,如'script_generating', 'outline_completed'等)
            stage_data: 该阶段的完整状态数据
            session_context: 会话上下文(修订历史、对话记录等)
            status: 生成状态

        Returns:
            更新后的Generation对象
        """
        if not self.generation:
            await self.load_generation()

        if not self.generation:
            raise ValueError(f"Generation {self.generation_id} not found")

        # 更新状态
        self.generation.current_stage = stage
        self.generation.stage_data = stage_data
        self.generation.status = status

        # 合并session_context(保留历史)
        if session_context:
            existing_context = self.generation.session_context or {}
            # 深度合并
            existing_context.update(session_context)
            self.generation.session_context = existing_context

        # 更新时间戳
        self.generation.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(self.generation)

        logger.info(
            f"[StateManager] Saved stage '{stage}' for generation {self.generation_id}"
        )

        return self.generation

    async def get_current_state(self) -> Optional[Dict[str, Any]]:
        """
        获取当前完整的生成状态

        Returns:
            包含所有状态信息的字典,或None
        """
        if not self.generation:
            await self.load_generation()

        if not self.generation:
            return None

        return {
            'id': self.generation.id,
            'module': self.generation.module.value,
            'status': self.generation.status.value,
            'current_stage': self.generation.current_stage,
            'stage_data': self.generation.stage_data,
            'session_context': self.generation.session_context,
            'output_content': self.generation.output_content,
            'input_params': self.generation.input_params,
            'revision_count': self.generation.revision_count,
            'is_finalized': self.generation.is_finalized,
            'created_at': self.generation.created_at.isoformat(),
            'updated_at': self.generation.updated_at.isoformat()
        }

    async def append_revision_message(self, message: Dict[str, Any]) -> None:
        """
        追加修订消息到会话上下文

        Args:
            message: 消息对象,如{'role': 'user', 'content': '...'}
        """
        if not self.generation:
            await self.load_generation()

        if not self.generation:
            return

        # 初始化session_context
        if not self.generation.session_context:
            self.generation.session_context = {}

        # 追加消息
        if 'revision_messages' not in self.generation.session_context:
            self.generation.session_context['revision_messages'] = []

        self.generation.session_context['revision_messages'].append({
            **message,
            'timestamp': datetime.utcnow().isoformat()
        })

        # 更新修订计数
        self.generation.revision_count = len(
            self.generation.session_context['revision_messages'])

        await self.db.commit()

    @staticmethod
    async def get_latest_generation(
        db: AsyncSession,
        user_id: int,
        module: str,
        days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        获取用户最近的生成记录

        Args:
            db: 数据库会话
            user_id: 用户ID
            module: 模块名称
            days: 查询最近N天的记录

        Returns:
            生成状态字典,或None
        """
        from datetime import datetime, timedelta
        from app.models.generation import GenerationModule

        # 转换模块名
        try:
            module_enum = GenerationModule(module)
        except ValueError:
            logger.warning(f"Invalid module: {module}")
            return None

        # 查询最近的记录
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(Generation)
            .where(
                Generation.user_id == user_id,
                Generation.module == module_enum,
                Generation.created_at >= cutoff_date
            )
            .order_by(Generation.created_at.desc())
            .limit(1)
        )

        result = await db.execute(stmt)
        generation = result.scalar_one_or_none()

        if not generation:
            return None

        return {
            'id': generation.id,
            'title': generation.title,
            'module': generation.module.value,
            'status': generation.status.value,
            'current_stage': generation.current_stage,
            'stage_data': generation.stage_data,
            'session_context': generation.session_context,
            'output_content': generation.output_content,
            'input_params': generation.input_params,
            'revision_count': generation.revision_count,
            'is_finalized': generation.is_finalized,
            'created_at': generation.created_at.isoformat(),
            'updated_at': generation.updated_at.isoformat()
        }


# 各模块的阶段标识常量
class StageIdentifiers:
    """
    各模块的阶段标识定义

    每个模块可以根据自己的流程定义阶段标识。
    以下是一些常见模块的示例:
    """

    # ==================== 小说大纲 ====================
    NOVEL_OUTLINE = {
        'global_generating': '全局大纲生成中',
        'global_completed': '全局大纲完成',
        'revising_global': '修订全局大纲中',
        'knowledge_revising': '知识库修正中',
        'units_generating': '单元概述生成中',
        'units_completed': '单元概述完成',
        'logic_checking': '逻辑检测中',
        'completed': '全部完成'
    }

    # ==================== 剧本大纲 ====================
    SCRIPT_OUTLINE = {
        'global_generating': '全局大纲生成中',
        'global_completed': '全局大纲完成',
        'revising_global': '修订全局大纲中',
        'knowledge_revising': '知识库修正中',
        'scenes_generating': '场景概述生成中',
        'scenes_completed': '场景概述完成',
        'logic_checking': '逻辑检测中',
        'completed': '全部完成'
    }

    # ==================== 短视频脚本 ====================
    SHORT_VIDEO = {
        'generating': '脚本生成中',
        'revising': '修订脚本中',
        'completed': '生成完成'
    }

    # ==================== 平面广告 ====================
    PRINT_AD = {
        'generating': '广告生成中',
        'revising': '修订广告中',
        'completed': '生成完成'
    }

    # ==================== TVC广告 ====================
    TVC = {
        'generating': 'TVC生成中',
        'revising': '修订TVC中',
        'completed': '生成完成'
    }

    # ==================== 原创IP ====================
    ORIGINAL_IP = {
        'analysis': 'IP分析中',
        'planning': '计划生成中',
        'revising': '修订计划中',
        'completed': '生成完成'
    }

    # ==================== 应用文写作 ====================
    PRACTICAL_WRITING = {
        'generating': '文档生成中',
        'revising': '修订文档中',
        'completed': '生成完成'
    }
