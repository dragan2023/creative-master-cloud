"""
Redis 连接配置
用于缓存和会话管理
支持 Redis 不可用时自动降级到内存存储

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import redis.asyncio as redis
from typing import Optional, Dict
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class MemoryStorage:
    """
    内存存储（Redis 不可用时的后备方案）
    注意：仅适用于单进程开发环境，多进程环境下会话无法共享
    """

    def __init__(self):
        self._store: Dict[str, str] = {}
        self._expires: Dict[str, int] = {}  # 存储过期时间戳

    async def set(self, key: str, value: str, expire: int = None) -> bool:
        """设置键值"""
        import time
        self._store[key] = value
        if expire:
            self._expires[key] = int(time.time()) + expire
        elif key in self._expires:
            del self._expires[key]
        return True

    async def get(self, key: str) -> Optional[str]:
        """获取值"""
        import time
        # 检查是否过期
        if key in self._expires:
            if int(time.time()) > self._expires[key]:
                del self._store[key]
                del self._expires[key]
                return None
        return self._store.get(key)

    async def delete(self, key: str) -> int:
        """删除键"""
        if key in self._store:
            del self._store[key]
            if key in self._expires:
                del self._expires[key]
            return 1
        return 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await self.get(key) is not None

    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        import time
        if key in self._store:
            self._expires[key] = int(time.time()) + seconds
            return True
        return False

    async def close(self) -> None:
        """关闭连接（内存存储无需操作）"""
        pass


class RedisManager:
    """Redis 连接管理器（支持降级到内存存储）"""

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._memory_storage: Optional[MemoryStorage] = None
        self._use_memory: bool = False
        self._connection_checked: bool = False

    async def _check_redis_connection(self) -> bool:
        """检查 Redis 连接是否可用"""
        if self._connection_checked:
            return not self._use_memory

        try:
            settings = get_settings()
            redis_url = settings.REDIS_URL

            # 检查是否显式禁用 Redis（使用 memory:// 协议）
            if redis_url.startswith("memory://"):
                logger.info("Redis 已禁用，使用内存存储（配置: memory://）")
                self._use_memory = True
                self._memory_storage = MemoryStorage()
                self._connection_checked = True
                return False

            client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # 测试连接
            await client.ping()
            self._client = client
            self._use_memory = False
            self._connection_checked = True
            logger.info(f"Redis 连接成功: {redis_url}")
            return True
        except Exception as e:
            logger.warning(f"Redis 连接失败，使用内存存储: {e}")
            self._use_memory = True
            self._memory_storage = MemoryStorage()
            self._connection_checked = True
            return False

    async def get_client(self) -> redis.Redis:
        """获取 Redis 客户端（延迟初始化）"""
        await self._check_redis_connection()
        if self._use_memory:
            return self._memory_storage
        return self._client

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None
        if self._memory_storage:
            await self._memory_storage.close()
            self._memory_storage = None

    async def set(self, key: str, value: str, expire: int = None) -> bool:
        """
        设置键值

        Args:
            key: 键
            value: 值
            expire: 过期时间（秒）

        Returns:
            是否成功
        """
        await self._check_redis_connection()
        if self._use_memory:
            return await self._memory_storage.set(key, value, expire)

        if expire:
            return await self._client.setex(key, expire, value)
        return await self._client.set(key, value)

    async def get(self, key: str) -> Optional[str]:
        """
        获取值

        Args:
            key: 键

        Returns:
            值或 None
        """
        await self._check_redis_connection()
        if self._use_memory:
            return await self._memory_storage.get(key)
        return await self._client.get(key)

    async def delete(self, key: str) -> int:
        """
        删除键

        Args:
            key: 键

        Returns:
            删除的键数量
        """
        await self._check_redis_connection()
        if self._use_memory:
            return await self._memory_storage.delete(key)
        return await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        """
        检查键是否存在

        Args:
            key: 键

        Returns:
            是否存在
        """
        await self._check_redis_connection()
        if self._use_memory:
            return await self._memory_storage.exists(key)
        return await self._client.exists(key) > 0

    async def expire(self, key: str, seconds: int) -> bool:
        """
        设置过期时间

        Args:
            key: 键
            seconds: 秒数

        Returns:
            是否成功
        """
        await self._check_redis_connection()
        if self._use_memory:
            return await self._memory_storage.expire(key, seconds)
        return await self._client.expire(key, seconds)

    def is_available(self) -> bool:
        """
        检查 Redis 是否可用（同步方法）

        Returns:
            是否使用 Redis（False 表示使用内存存储）
        """
        # 如果还没有检查过连接，返回 True 让异步方法去检查
        # 如果已经检查过，返回是否使用 Redis
        if not self._connection_checked:
            return True  # 让调用者使用异步方法
        return not self._use_memory


# 全局 Redis 管理器实例
redis_manager = RedisManager()


async def get_redis() -> redis.Redis:
    """获取 Redis 客户端"""
    return await redis_manager.get_client()
