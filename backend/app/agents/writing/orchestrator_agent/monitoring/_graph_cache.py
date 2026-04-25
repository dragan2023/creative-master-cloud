"""
monitoring/_graph_cache.py - 图谱缓存管理器

包含 GraphCache 类，使用LRU策略缓存已加载的图谱实例。

@date: 2026-04-24
@version: v3.0.0
"""
import os
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from app.core.logger import get_logger


class GraphCache:
    """知识图谱缓存管理器

    使用LRU策略缓存已加载的图谱实例，避免重复I/O和解析开销。
    特别优化：对全局图谱使用长期缓存，单元图谱使用LRU淘汰。

    Attributes:
        max_unit_cache_size: 单元图谱最大缓存数量
        _global_cache: 全局图谱缓存（持久缓存）
        _unit_cache: 单元图谱缓存（LRU淘汰）
    """

    def __init__(self, max_unit_cache_size: int = 30):
        """
        初始化图谱缓存

        Args:
            max_unit_cache_size: 单元图谱最大缓存数量，默认30个
        """
        self.max_unit_cache_size = max_unit_cache_size
        self._global_cache: Dict[str, Tuple["NovelKnowledgeGraph", float]] = {}
        self._unit_cache: OrderedDict[str, Tuple["NovelKnowledgeGraph", float]] = OrderedDict()
        self._logger = get_logger("graph_cache")
        self._hit_count = 0
        self._miss_count = 0

    def get_or_load(self, graph_path: str, is_global: bool = False) -> Optional["NovelKnowledgeGraph"]:
        """获取或加载图谱

        优先从缓存获取，缓存未命中则加载并缓存。

        Args:
            graph_path: 图谱文件路径
            is_global: 是否为全局图谱

        Returns:
            图谱实例，加载失败返回None
        """
        from app.tools.novel_graph_rag import NovelKnowledgeGraph

        cache = self._global_cache if is_global else self._unit_cache

        if graph_path in cache:
            self._hit_count += 1
            graph, _ = cache[graph_path]
            if not is_global and isinstance(cache, OrderedDict):
                cache.move_to_end(graph_path)
            self._logger.debug(f"图谱缓存命中: {os.path.basename(graph_path)}")
            return graph

        self._miss_count += 1
        if not os.path.exists(graph_path):
            self._logger.debug(f"图谱文件不存在: {graph_path}")
            return None

        graph = NovelKnowledgeGraph(persist_path=graph_path)
        if not graph.load():
            return None

        if is_global:
            self._global_cache[graph_path] = (graph, time.time())
            self._logger.debug(f"全局图谱已缓存: {os.path.basename(graph_path)}")
        else:
            if len(self._unit_cache) >= self.max_unit_cache_size:
                oldest_path = next(iter(self._unit_cache))
                del self._unit_cache[oldest_path]
                self._logger.debug(f"LRU淘汰图谱: {os.path.basename(oldest_path)}")
            self._unit_cache[graph_path] = (graph, time.time())
            self._logger.debug(f"单元图谱已缓存: {os.path.basename(graph_path)}")

        return graph

    def invalidate(self, graph_path: str) -> None:
        """使指定图谱缓存失效"""
        if graph_path in self._global_cache:
            del self._global_cache[graph_path]
            self._logger.debug(f"全局图谱缓存已失效: {os.path.basename(graph_path)}")
        if graph_path in self._unit_cache:
            del self._unit_cache[graph_path]
            self._logger.debug(f"单元图谱缓存已失效: {os.path.basename(graph_path)}")

    def invalidate_all(self) -> None:
        """使所有缓存失效"""
        self._global_cache.clear()
        self._unit_cache.clear()
        self._logger.info("所有图谱缓存已清除")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0
        return {
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": f"{hit_rate:.1%}",
            "global_cache_size": len(self._global_cache),
            "unit_cache_size": len(self._unit_cache)
        }
