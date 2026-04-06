"""
MCP 缓存管理模块
实现多级缓存架构：L1 内存缓存 + L2 Redis 缓存

缓存策略：
- 热点数据: TTL = 30分钟
- 趋势数据: TTL = 1小时
- 静态资源: TTL = 24小时

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, Optional
import time
import json
from collections import OrderedDict
from threading import Lock

from app.core.config import get_settings
from app.core.logger import get_logger


class LRUCache:
    """
    LRU (Least Recently Used) 内存缓存

    特点：
    - 线程安全
    - 自动过期清理
    - 容量限制
    """

    def __init__(self, capacity: int = 100, default_ttl: int = 1800):
        """
        初始化 LRU 缓存

        Args:
            capacity: 最大容量
            default_ttl: 默认过期时间（秒）
        """
        self.capacity = capacity
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            item = self._cache[key]

            # 检查是否过期
            if time.time() > item.get("expires_at", 0):
                del self._cache[key]
                self._misses += 1
                return None

            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            self._hits += 1
            return item.get("data")

    def set(self, key: str, data: Dict[str, Any], ttl: int = None):
        """设置缓存"""
        with self._lock:
            expires_at = time.time() + (ttl or self.default_ttl)

            # 如果已存在，先删除
            if key in self._cache:
                del self._cache[key]

            # 检查容量
            while len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)

            self._cache[key] = {
                "data": data,
                "expires_at": expires_at,
                "created_at": time.time()
            }

    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def clear_expired(self) -> int:
        """清理过期缓存"""
        count = 0
        current_time = time.time()

        with self._lock:
            expired_keys = [
                key for key, item in self._cache.items()
                if current_time > item.get("expires_at", 0)
            ]

            for key in expired_keys:
                del self._cache[key]
                count += 1

        return count

    def clear_pattern(self, pattern: str) -> int:
        """清除匹配模式的缓存"""
        count = 0
        # 简单的前缀匹配
        prefix = pattern.rstrip("*")

        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if key.startswith(prefix)
            ]

            for key in keys_to_delete:
                del self._cache[key]
                count += 1

        return count

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "capacity": self.capacity,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.2%}",
                "default_ttl": self.default_ttl
            }


class MCPCache:
    """
    MCP 多级缓存管理器

    架构：
    L1: 内存缓存（LRU） - 快速访问，进程内共享
    L2: Redis 缓存 - 持久化，跨进程共享
    """

    # 不同数据类型的 TTL 配置
    TTL_CONFIG = {
        "trending": 1800,      # 热点数据：30分钟
        "trends": 3600,        # 趋势数据：1小时
        "models": 86400,       # 模型数据：24小时
        "default": 1800        # 默认：30分钟
    }

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger("mcp_cache")

        # L1 内存缓存
        self._memory_cache = LRUCache(
            capacity=100,
            default_ttl=self.settings.MCP_CACHE_TTL
        )

        # Redis 客户端（延迟初始化）
        self._redis_client = None

        # 统计
        self._l1_hits = 0
        self._l2_hits = 0
        self._l3_requests = 0

    def _get_redis_client(self):
        """延迟初始化 Redis 客户端"""
        if self._redis_client is None:
            try:
                from app.core.redis_client import get_redis
                # get_redis 是异步函数，这里使用同步方式获取
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果事件循环正在运行，标记为需要异步初始化
                        self._redis_client = False
                    else:
                        self._redis_client = loop.run_until_complete(
                            get_redis())
                except RuntimeError:
                    # 没有事件循环，创建一个新的
                    self._redis_client = asyncio.run(get_redis())
            except Exception as e:
                self.logger.warning(f"Redis 客户端初始化失败: {str(e)}")
                self._redis_client = False  # 标记为不可用

        return self._redis_client if self._redis_client is not False else None

    def _get_ttl(self, data_type: str = "default") -> int:
        """获取数据类型的 TTL"""
        return self.TTL_CONFIG.get(data_type, self.TTL_CONFIG["default"])

    def _build_redis_key(self, key: str) -> str:
        """构建 Redis 键"""
        return f"mcp:{key}"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存（多级查询）

        查询顺序：L1 内存 -> L2 Redis -> None
        """
        if not self.settings.MCP_CACHE_ENABLED:
            return None

        # L1: 内存缓存
        data = self._memory_cache.get(key)
        if data is not None:
            self._l1_hits += 1
            self.logger.debug(f"L1 缓存命中: {key}")
            return data

        # L2: Redis 缓存
        redis = self._get_redis_client()
        if redis:
            try:
                redis_key = self._build_redis_key(key)
                cached = redis.get(redis_key)
                if cached:
                    data = json.loads(cached)
                    # 回填 L1 缓存
                    self._memory_cache.set(key, data)
                    self._l2_hits += 1
                    self.logger.debug(f"L2 缓存命中: {key}")
                    return data
            except Exception as e:
                self.logger.warning(f"Redis 读取失败: {str(e)}")

        self._l3_requests += 1
        return None

    def set(
        self,
        key: str,
        data: Dict[str, Any],
        ttl: int = None,
        data_type: str = "default"
    ):
        """
        设置缓存（多级写入）

        Args:
            key: 缓存键
            data: 缓存数据
            ttl: 过期时间（秒）
            data_type: 数据类型，用于自动选择 TTL
        """
        if not self.settings.MCP_CACHE_ENABLED:
            return

        ttl = ttl or self._get_ttl(data_type)

        # L1: 内存缓存
        self._memory_cache.set(key, data, ttl)

        # L2: Redis 缓存
        redis = self._get_redis_client()
        if redis:
            try:
                redis_key = self._build_redis_key(key)
                redis.setex(
                    redis_key,
                    ttl,
                    json.dumps(data, ensure_ascii=False)
                )
                self.logger.debug(f"已缓存: {key}, TTL: {ttl}s")
            except Exception as e:
                self.logger.warning(f"Redis 写入失败: {str(e)}")

    def delete(self, key: str) -> bool:
        """删除缓存"""
        # L1
        self._memory_cache.delete(key)

        # L2
        redis = self._get_redis_client()
        if redis:
            try:
                redis_key = self._build_redis_key(key)
                redis.delete(redis_key)
            except Exception as e:
                self.logger.warning(f"Redis 删除失败: {str(e)}")

        return True

    def clear_pattern(self, pattern: str):
        """清除匹配模式的缓存"""
        # L1
        l1_count = self._memory_cache.clear_pattern(pattern)

        # L2
        redis = self._get_redis_client()
        l2_count = 0
        if redis:
            try:
                redis_pattern = self._build_redis_key(pattern)
                keys = redis.keys(redis_pattern)
                if keys:
                    redis.delete(*keys)
                    l2_count = len(keys)
            except Exception as e:
                self.logger.warning(f"Redis 模式清除失败: {str(e)}")

        self.logger.info(f"已清除缓存: L1={l1_count}, L2={l2_count}")

    def clear_all(self):
        """清除所有 MCP 缓存"""
        # L1
        self._memory_cache.clear()

        # L2
        redis = self._get_redis_client()
        if redis:
            try:
                keys = redis.keys("mcp:*")
                if keys:
                    redis.delete(*keys)
                    self.logger.info(f"已清除 {len(keys)} 个 Redis 缓存")
            except Exception as e:
                self.logger.warning(f"Redis 清除失败: {str(e)}")

        self.logger.info("所有 MCP 缓存已清除")

    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        return self._memory_cache.clear_expired()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self._l1_hits + self._l2_hits + self._l3_requests

        return {
            "enabled": self.settings.MCP_CACHE_ENABLED,
            "l1_memory": self._memory_cache.get_stats(),
            "l2_redis": {
                "available": self._get_redis_client() is not None
            },
            "statistics": {
                "l1_hits": self._l1_hits,
                "l2_hits": self._l2_hits,
                "l3_requests": self._l3_requests,
                "total_requests": total_requests,
                "l1_hit_rate": f"{self._l1_hits / max(1, total_requests):.2%}",
                "l2_hit_rate": f"{self._l2_hits / max(1, total_requests):.2%}",
                "overall_hit_rate": f"{(self._l1_hits + self._l2_hits) / max(1, total_requests):.2%}"
            },
            "ttl_config": self.TTL_CONFIG
        }


# 全局缓存实例
_mcp_cache: Optional[MCPCache] = None


def get_mcp_cache() -> MCPCache:
    """获取 MCP 缓存实例"""
    global _mcp_cache
    if _mcp_cache is None:
        _mcp_cache = MCPCache()
    return _mcp_cache
