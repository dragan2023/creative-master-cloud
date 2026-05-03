"""Optimizedcreativesearch"""

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

from ._trigger_analyzer import SearchTriggerAnalyzer
from ._keyword_extractor import KeywordExtractor
from ._quality_evaluator import SearchResultQualityEvaluator
from ._formatter import CreativeSearchFormatter
from ._cache import CreativeSearchCache

logger = get_logger(__name__)


class OptimizedCreativeSearch:
    """
    优化后的创作辅助搜索 - 统一入口

    整合所有组件，提供一站式搜索服务
    """

    def __init__(self):
        self.trigger_analyzer = SearchTriggerAnalyzer()
        self.keyword_extractor = KeywordExtractor()
        self.quality_evaluator = SearchResultQualityEvaluator()
        self.formatter = CreativeSearchFormatter()
        self.cache = CreativeSearchCache()
        self.logger = get_logger("creative_search")

    async def search(
        self,
        input_params: Dict[str, Any],
        module: str,
        user_keywords: Optional[List[str]] = None,
        force_search: bool = False,
        search_depth: str = "normal",
        user_id: Optional[int] = None,
        db=None
    ) -> Dict[str, Any]:
        """
        执行智能搜索

        Args:
            input_params: 用户输入参数
            module: 创作模块
            user_keywords: 用户指定的关键词
            force_search: 是否强制搜索
            search_depth: 搜索深度 (quick/normal/deep)
            user_id: 用户ID（用于获取API Key）
            db: 数据库会话

        Returns:
            {
                "searched": bool,
                "reason": str,
                "keywords": List[str],
                "results": List[Dict],
                "formatted_context": str,
                "cached": bool
            }
        """
        # 1. 触发判断（除非强制搜索）
        if not force_search:
            need_search, reason, suggested_keywords = self.trigger_analyzer.should_search(
                input_params, module
            )
            if not need_search:
                return {
                    "searched": False,
                    "reason": reason,
                    "keywords": [],
                    "results": [],
                    "formatted_context": "",
                    "cached": False
                }
        else:
            reason = "用户强制搜索"
            suggested_keywords = []

        # 2. 关键词提取
        keywords = self.keyword_extractor.extract_keywords(
            input_params, module, user_keywords or suggested_keywords
        )

        if not keywords:
            return {
                "searched": False,
                "reason": "无法提取有效搜索关键词",
                "keywords": [],
                "results": [],
                "formatted_context": "",
                "cached": False
            }

        # 3. 检查缓存
        cache_key = " ".join(sorted(keywords))
        cached_results = self.cache.get(cache_key)

        if cached_results:
            self.logger.info(f"使用缓存结果: {cache_key}")
            formatted = self.formatter.format_for_llm(
                cached_results, cache_key)
            return {
                "searched": True,
                "reason": reason,
                "keywords": keywords,
                "results": cached_results,
                "formatted_context": formatted,
                "cached": True
            }

        # 4. 执行搜索
        all_results = await self._execute_search(keywords, search_depth, user_id, db)

        # 5. 质量过滤和排序
        filtered_results = self.quality_evaluator.filter_and_rank(
            all_results, cache_key
        )

        # 6. 缓存结果
        if filtered_results:
            self.cache.set(cache_key, filtered_results)

        # 7. 格式化
        formatted = self.formatter.format_for_llm(filtered_results, cache_key)

        self.logger.info(
            f"搜索完成: keywords={keywords}, results={len(filtered_results)}")

        return {
            "searched": True,
            "reason": reason,
            "keywords": keywords,
            "results": filtered_results,
            "formatted_context": formatted,
            "cached": False
        }

    async def _execute_search(
        self,
        keywords: List[str],
        search_depth: str,
        user_id: Optional[int] = None,
        db=None
    ) -> List[Dict]:
        """执行搜索"""
        from app.tools.web_search import search_with_fallback

        # 根据深度确定结果数量
        num_results = {"quick": 2, "normal": 3, "deep": 5}.get(search_depth, 3)

        all_results = []
        seen_urls = set()

        # 创建获取用户 API Key 的回调函数
        async def get_user_search_key(provider: str) -> Optional[str]:
            """获取用户搜索API Key"""
            if not user_id or not db:
                return None
            try:
                from app.models import UserAPIKey
                from sqlalchemy import select
                result = await db.execute(
                    select(UserAPIKey).where(
                        UserAPIKey.user_id == user_id,
                        UserAPIKey.provider == provider,
                        UserAPIKey.is_valid == True
                    ).order_by(UserAPIKey.is_default.desc()).limit(1)
                )
                api_key_record = result.scalar_one_or_none()
                if api_key_record:
                    from app.core.security import api_key_encryption
                    return api_key_encryption.decrypt(api_key_record.encrypted_key)
            except Exception as e:
                self.logger.warning(f"获取用户{provider} API Key失败: {str(e)}")
            return None

        for keyword in keywords:
            try:
                # 使用降级策略搜索（博查AI → 百度搜索）
                results, engine_used = await search_with_fallback(
                    query=keyword,
                    num_results=num_results,
                    get_user_api_key=get_user_search_key
                )

                if results:
                    self.logger.info(
                        f"搜索成功: keyword={keyword}, engine={engine_used}, results={len(results)}")
                    for result in results:
                        # 过滤错误结果
                        if "error" in result:
                            continue
                        url = result.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_results.append(result)
                        elif not url:  # 没有URL的结果也添加
                            all_results.append(result)

            except Exception as e:
                self.logger.warning(f"搜索关键词 '{keyword}' 失败: {str(e)}")
                continue

        return all_results

    async def _search_single(
        self,
        keyword: str,
        num_results: int,
        user_id: Optional[int] = None,
        db=None
    ) -> List[Dict]:
        """搜索单个关键词（已弃用，保留兼容）"""
        from app.tools.web_search import search_with_fallback

        try:
            # 创建获取用户 API Key 的回调函数
            async def get_user_search_key(provider: str) -> Optional[str]:
                """获取用户搜索API Key"""
                if not user_id or not db:
                    return None
                try:
                    from app.models import UserAPIKey
                    from sqlalchemy import select
                    result = await db.execute(
                        select(UserAPIKey).where(
                            UserAPIKey.user_id == user_id,
                            UserAPIKey.provider == provider,
                            UserAPIKey.is_valid == True
                        ).order_by(UserAPIKey.is_default.desc()).limit(1)
                    )
                    api_key_record = result.scalar_one_or_none()
                    if api_key_record:
                        from app.core.security import api_key_encryption
                        return api_key_encryption.decrypt(api_key_record.encrypted_key)
                except Exception as e:
                    self.logger.warning(f"获取用户{provider} API Key失败: {str(e)}")
                return None

            # 使用降级策略搜索（博查AI → 百度搜索）
            results, engine_used = await search_with_fallback(
                query=keyword,
                num_results=num_results,
                get_user_api_key=get_user_search_key
            )

            self.logger.info(
                f"搜索完成: keyword={keyword}, engine={engine_used}, results={len(results)}")
            return results

        except Exception as e:
            self.logger.error(f"搜索异常: {str(e)}")
            return []


# ==================== 全局实例 ====================

_creative_search: Optional[OptimizedCreativeSearch] = None
