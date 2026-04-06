"""
用户行为追踪服务模块

封装用户行为记录的操作。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_action import UserAction, ActionType
from app.core.logger import get_logger

logger = get_logger("user_action_service")


class UserActionService:
    """用户行为追踪服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def track_action(
        self,
        user_id: int,
        generation_id: int,
        module: str,
        action: str,
        content_snippet: Optional[str] = None,
    ):
        """记录用户行为"""
        # 将字符串 action 转换为 ActionType 枚举
        try:
            action_enum = ActionType(action)
        except ValueError:
            # 如果传入的 action 不是有效的枚举值，默认为 COPY
            logger.warning(f"无效的行为类型: {action}，使用默认值 COPY")
            action_enum = ActionType.COPY
        
        action_obj = UserAction(
            user_id=user_id,
            generation_id=generation_id,
            module=module,
            action=action_enum,
            content_snippet=content_snippet,
        )
        self.db.add(action_obj)
        await self.db.commit()
        await self.db.refresh(action_obj)
        logger.debug(f"记录用户行为: user={user_id}, action={action}, module={module}")
        return action_obj
