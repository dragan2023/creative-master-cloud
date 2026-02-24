"""
记忆管理器
管理短期记忆（Redis）和长期记忆（向量数据库）
"""
from typing import Optional, List, Dict, Any
import json
import uuid

from app.core.redis_client import redis_manager
from app.core.vector_store import vector_store
from app.core.config import get_settings
from app.models.base import get_local_now


class MemoryManager:
    """记忆管理器"""

    def __init__(self):
        self.settings = get_settings()

    # ==================== 短期记忆（Redis）====================

    def _get_session_key(self, session_id: str) -> str:
        """获取会话键名"""
        return f"session:{session_id}"

    async def create_session(
        self,
        user_id: int,
        module: str,
        expire_hours: int = 24
    ) -> str:
        """
        创建新会话

        Args:
            user_id: 用户ID
            module: 模块名称
            expire_hours: 过期时间（小时）

        Returns:
            会话ID
        """
        session_id = str(uuid.uuid4())
        session_key = self._get_session_key(session_id)

        session_data = {
            "user_id": user_id,
            "module": module,
            "messages": [],
            "context": {},
            "created_at": get_local_now().isoformat()
        }

        await redis_manager.set(
            session_key,
            json.dumps(session_data, ensure_ascii=False),
            expire=expire_hours * 3600
        )

        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话数据

        Args:
            session_id: 会话ID

        Returns:
            会话数据
        """
        session_key = self._get_session_key(session_id)
        data = await redis_manager.get(session_key)

        if data:
            return json.loads(data)
        return None

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """
        添加消息到会话

        Args:
            session_id: 会话ID
            role: 角色（user/assistant）
            content: 消息内容
        """
        session = await self.get_session(session_id)
        if not session:
            return

        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": get_local_now().isoformat()
        })

        session_key = self._get_session_key(session_id)
        await redis_manager.set(
            session_key,
            json.dumps(session, ensure_ascii=False)
        )

    async def get_messages(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        获取会话消息列表

        Args:
            session_id: 会话ID
            limit: 最大消息数量

        Returns:
            消息列表
        """
        session = await self.get_session(session_id)
        if not session:
            return []

        messages = session.get("messages", [])

        # 转换为 LLM 使用的格式
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages[-limit:]
        ]

    async def set_context(
        self,
        session_id: str,
        key: str,
        value: Any
    ) -> None:
        """
        设置会话上下文

        Args:
            session_id: 会话ID
            key: 键
            value: 值
        """
        session = await self.get_session(session_id)
        if not session:
            return

        session["context"][key] = value

        session_key = self._get_session_key(session_id)
        await redis_manager.set(
            session_key,
            json.dumps(session, ensure_ascii=False)
        )

    async def get_context(
        self,
        session_id: str,
        key: Optional[str] = None
    ) -> Any:
        """
        获取会话上下文

        Args:
            session_id: 会话ID
            key: 键（可选，不传则返回全部上下文）

        Returns:
            上下文值
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        context = session.get("context", {})

        if key:
            return context.get(key)
        return context

    async def delete_session(self, session_id: str) -> None:
        """
        删除会话

        Args:
            session_id: 会话ID
        """
        session_key = self._get_session_key(session_id)
        await redis_manager.delete(session_key)

    # ==================== 长期记忆（向量数据库）====================

    def _get_user_collection_name(self, user_id: int) -> str:
        """获取用户向量集合名称"""
        return f"user_{user_id}_memory"

    async def store_to_long_term_memory(
        self,
        user_id: int,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        存储到长期记忆

        Args:
            user_id: 用户ID
            content: 内容
            metadata: 元数据

        Returns:
            文档ID
        """
        collection_name = self._get_user_collection_name(user_id)

        import uuid
        doc_id = str(uuid.uuid4())

        vector_store.add_documents(
            collection_name=collection_name,
            documents=[content],
            metadatas=[metadata or {}],
            ids=[doc_id]
        )

        return doc_id

    async def search_long_term_memory(
        self,
        user_id: int,
        query: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索长期记忆

        Args:
            user_id: 用户ID
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            搜索结果列表
        """
        collection_name = self._get_user_collection_name(user_id)

        try:
            results = vector_store.query(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results
            )

            # 格式化结果
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    formatted_results.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results.get("distances") else None
                    })

            return formatted_results
        except Exception:
            # 集合不存在时返回空列表
            return []

    async def clear_long_term_memory(self, user_id: int) -> None:
        """
        清空用户的长期记忆

        Args:
            user_id: 用户ID
        """
        collection_name = self._get_user_collection_name(user_id)
        vector_store.delete_collection(collection_name)


# 全局记忆管理器实例
memory_manager = MemoryManager()


def get_memory_manager() -> MemoryManager:
    """获取记忆管理器实例"""
    return memory_manager
