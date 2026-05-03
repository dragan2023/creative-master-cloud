"""Searchresultqualityevaluator"""

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


class SearchResultQualityEvaluator:
    """
    搜索结果质量评估器

    四维评分：
    1. 相关性 (40%) - 与搜索关键词的匹配度
    2. 完整度 (25%) - 信息量和详细程度
    3. 可信度 (20%) - 来源权威性和时效性
    4. 可读性 (15%) - 内容质量
    """

    # 权威域名
    AUTHORITATIVE_DOMAINS = [
        ".gov.cn", ".edu.cn", ".org.cn",
        "baike.baidu.com", "zh.wikipedia.org",
        "people.com.cn", "xinhuanet.com",
        "zhihu.com", "douban.com"
    ]

    # 低质量信号
    LOW_QUALITY_SIGNALS = [
        "点击查看", "扫码下载", "注册查看",
        "广告", "推广", "赞助", "购买链接"
    ]

    def evaluate_result(
        self,
        result: Dict,
        query: str
    ) -> Dict[str, Any]:
        """
        评估单条搜索结果质量

        Returns:
            {
                "score": float,  # 综合分数 0-1
                "dimensions": {...},
                "passed": bool,
                "issues": List[str]
            }
        """
        issues = []

        # 1. 相关性评分
        relevance = self._score_relevance(result, query)
        if relevance < 0.3:
            issues.append("相关性较低")

        # 2. 信息完整度
        completeness = self._score_completeness(result)
        if completeness < 0.3:
            issues.append("信息量不足")

        # 3. 来源可信度
        credibility = self._score_credibility(result)

        # 4. 可读性
        readability = self._score_readability(result)
        if readability < 0.3:
            issues.append("内容质量较差")

        # 综合评分
        score = (
            relevance * 0.4 +
            completeness * 0.25 +
            credibility * 0.2 +
            readability * 0.15
        )

        # 判断是否通过
        passed = score >= 0.35 and len(issues) < 2

        return {
            "score": score,
            "dimensions": {
                "relevance": relevance,
                "completeness": completeness,
                "credibility": credibility,
                "readability": readability
            },
            "passed": passed,
            "issues": issues
        }

    def _score_relevance(self, result: Dict, query: str) -> float:
        """评分相关性"""
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        query_lower = query.lower()

        # 简单的关键词匹配
        query_terms = set(query_lower.split())
        if not query_terms:
            return 0.5

        # 标题匹配权重更高
        title_terms = set(title.split())
        title_overlap = len(query_terms & title_terms) / \
            len(query_terms) if query_terms else 0

        # 摘要匹配
        snippet_terms = set(snippet.split())
        snippet_overlap = len(query_terms & snippet_terms) / \
            len(query_terms) if query_terms else 0

        score = title_overlap * 0.6 + snippet_overlap * 0.4

        # 如果标题完全包含查询词，加分
        if query_lower in title:
            score = min(score + 0.2, 1.0)

        return score

    def _score_completeness(self, result: Dict) -> float:
        """评分信息完整度"""
        snippet = result.get("snippet", "")

        if not snippet:
            return 0.1

        # 长度评分
        length_score = min(len(snippet) / 200, 1.0)

        # 数据/数字存在加分
        has_numbers = bool(re.search(r'\d+', snippet))
        has_dates = bool(re.search(r'\d{4}年|\d{1,2}月', snippet))

        data_bonus = 0.1 * (int(has_numbers) + int(has_dates))

        return min(length_score + data_bonus, 1.0)

    def _score_credibility(self, result: Dict) -> float:
        """评分来源可信度"""
        url = result.get("url", "").lower()
        date = result.get("datePublished", "")

        score = 0.5  # 基础分

        # 域名检查
        for domain in self.AUTHORITATIVE_DOMAINS:
            if domain in url:
                score = min(score + 0.3, 1.0)
                break

        # 时间检查
        if date:
            try:
                pub_date = datetime.strptime(date[:10], "%Y-%m-%d")
                days_old = (datetime.now() - pub_date).days

                if days_old < 365:
                    score = min(score + 0.2, 1.0)
                elif days_old < 1825:
                    score = min(score + 0.1, 1.0)
            except (ValueError, TypeError) as e:
                logger.debug(f"解析日期失败: {e}")
                pass

        return score

    def _score_readability(self, result: Dict) -> float:
        """评分可读性"""
        snippet = result.get("snippet", "")

        if not snippet:
            return 0.1

        # 检查低质量信号
        noise_count = 0
        for signal in self.LOW_QUALITY_SIGNALS:
            if signal in snippet:
                noise_count += 1

        noise_penalty = noise_count * 0.2

        # 检查内容结构
        has_punctuation = any(p in snippet for p in ["。", "，", "、", "："])
        structure_bonus = 0.1 if has_punctuation else 0

        score = max(0.5 - noise_penalty + structure_bonus, 0.1)

        return min(score, 1.0)

    def filter_and_rank(
        self,
        results: List[Dict],
        query: str,
        min_score: float = 0.35
    ) -> List[Dict]:
        """过滤并排序结果"""
        evaluated = []

        for result in results:
            evaluation = self.evaluate_result(result, query)
            if evaluation["passed"]:
                result["_quality_score"] = evaluation["score"]
                result["_quality_details"] = evaluation
                evaluated.append(result)

        # 按质量分数排序
        evaluated.sort(key=lambda x: x["_quality_score"], reverse=True)

        return evaluated


# ==================== 搜索结果格式化器 ====================
