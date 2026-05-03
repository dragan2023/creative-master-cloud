"""创作辅助搜索模块包"""

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


from ._trigger_analyzer import SearchTriggerAnalyzer
from ._keyword_extractor import KeywordExtractor
from ._quality_evaluator import SearchResultQualityEvaluator
from ._formatter import CreativeSearchFormatter
from ._cache import CreativeSearchCache
from ._search_engine import OptimizedCreativeSearch


_creative_search = None


def get_creative_search() -> OptimizedCreativeSearch:
    """获取创作辅助搜索实例"""
    global _creative_search
    if _creative_search is None:
        _creative_search = OptimizedCreativeSearch()
    return _creative_search



__all__ = [
    "SearchTriggerAnalyzer",
    "KeywordExtractor",
    "SearchResultQualityEvaluator",
    "CreativeSearchFormatter",
    "CreativeSearchCache",
    "OptimizedCreativeSearch",
    "get_creative_search",
]
