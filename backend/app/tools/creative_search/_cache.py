"""Creativesearchcache"""

from __future__ import annotations

"""
创作辅助搜索模块

提供智能的联网搜索功能，帮助LLM获取创作所需的背景资料。
核心特性：
1. 智能触发判断 - 只在必要时搜索
2. 关键词提取 - 规则提取优先，用户指定最高优先
3. 质量评估 - 多维度评分过滤低质量结果
4. 高质量格式化 - LLM友好的结构化输出
5. 缓存机制 - 减少重复API调用

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, List, Any, Optional, Tuple
import re
import time
import hashlib
import asyncio
from datetime import datetime

from app.core.logger import get_logger

logger = get_logger(__name__)


class CreativeSearchCache:
    """搜索结果缓存"""

    def __init__(self, ttl: int = 3600):
        """
        Args:
            ttl: 缓存有效期（秒），默认1小时
        """
        self._cache: Dict[str, Dict] = {}
        self._ttl = ttl

    def get(self, query: str) -> Optional[List[Dict]]:
        """获取缓存的搜索结果"""
        cache_key = self._make_key(query)

        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if time.time() - entry["timestamp"] < self._ttl:
                return entry["results"]
            else:
                del self._cache[cache_key]

        return None

    def set(self, query: str, results: List[Dict]):
        """缓存搜索结果"""
        cache_key = self._make_key(query)
        self._cache[cache_key] = {
            "results": results,
            "timestamp": time.time()
        }

    def _make_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(query.encode()).hexdigest()

    def clear(self):
        """清空缓存"""
        self._cache.clear()


# ==================== 统一搜索入口 ====================
