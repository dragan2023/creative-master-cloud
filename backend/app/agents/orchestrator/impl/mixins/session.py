"""Agent编排器 - 会话管理与SSE工具Mixin"""
from typing import Dict
from typing import List
from typing import Any
import json
import re


class SessionMixin:
    """会话管理与SSE工具"""

    async def create_session(
        self,
        user_id: int,
        module: str
    ) -> str:
        """
        创建新会话

        Args:
            user_id: 用户ID
            module: 模块名称

        Returns:
            会话ID
        """
        return await self.memory_manager.create_session(
            user_id=user_id,
            module=module
        )


    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        获取会话消息

        Args:
            session_id: 会话ID
            limit: 最大消息数

        Returns:
            消息列表
        """
        return await self.memory_manager.get_messages(session_id, limit)


    def _format_sse(self, event: str, data: Dict[str, Any]) -> str:
        """
        格式化为 SSE 格式

        Args:
            event: 事件类型
            data: 数据

        Returns:
            SSE 格式字符串
        """
        data_str = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {data_str}\n\n"


