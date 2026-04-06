"""
提示词缓存管理模块
预留扩展：提示词模板缓存功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, Optional
from datetime import datetime


class PromptCache:
    """
    提示词缓存管理器
    
    预留扩展：可用于缓存已渲染的提示词，减少重复渲染开销
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        初始化缓存管理器
        
        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存过期时间（秒）
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
    
    def get(self, key: str) -> Optional[str]:
        """
        获取缓存的提示词
        
        Args:
            key: 缓存键
            
        Returns:
            缓存的提示词内容，如果不存在或已过期则返回None
        """
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if self._is_expired(entry["timestamp"]):
            del self._cache[key]
            return None
        
        return entry["content"]
    
    def set(self, key: str, content: str) -> None:
        """
        设置缓存
        
        Args:
            key: 缓存键
            content: 提示词内容
        """
        # 如果缓存已满，清理最旧的条目
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        self._cache[key] = {
            "content": content,
            "timestamp": datetime.now()
        }
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
    
    def _is_expired(self, timestamp: datetime) -> bool:
        """检查缓存是否过期"""
        elapsed = (datetime.now() - timestamp).total_seconds()
        return elapsed > self._ttl_seconds
    
    def _evict_oldest(self) -> None:
        """清理最旧的缓存条目"""
        if not self._cache:
            return
        
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]["timestamp"]
        )
        del self._cache[oldest_key]
    
    @property
    def size(self) -> int:
        """获取当前缓存大小"""
        return len(self._cache)


# 全局缓存实例（预留）
_prompt_cache: Optional[PromptCache] = None


def get_prompt_cache() -> PromptCache:
    """获取提示词缓存实例"""
    global _prompt_cache
    if _prompt_cache is None:
        _prompt_cache = PromptCache()
    return _prompt_cache
