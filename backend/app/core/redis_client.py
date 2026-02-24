"""
Redis 连接配置
用于缓存和会话管理
"""
import redis.asyncio as redis
from typing import Optional

from app.core.config import get_settings


class RedisManager:
    """Redis 连接管理器"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def get_client(self) -> redis.Redis:
        """获取 Redis 客户端（延迟初始化）"""
        if self._client is None:
            settings = get_settings()
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._client
    
    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None
    
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
        client = await self.get_client()
        if expire:
            return await client.setex(key, expire, value)
        return await client.set(key, value)
    
    async def get(self, key: str) -> Optional[str]:
        """
        获取值
        
        Args:
            key: 键
        
        Returns:
            值或 None
        """
        client = await self.get_client()
        return await client.get(key)
    
    async def delete(self, key: str) -> int:
        """
        删除键
        
        Args:
            key: 键
        
        Returns:
            删除的键数量
        """
        client = await self.get_client()
        return await client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """
        检查键是否存在
        
        Args:
            key: 键
        
        Returns:
            是否存在
        """
        client = await self.get_client()
        return await client.exists(key) > 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        设置过期时间
        
        Args:
            key: 键
            seconds: 秒数
        
        Returns:
            是否成功
        """
        client = await self.get_client()
        return await client.expire(key, seconds)


# 全局 Redis 管理器实例
redis_manager = RedisManager()


async def get_redis() -> redis.Redis:
    """获取 Redis 客户端"""
    return await redis_manager.get_client()
