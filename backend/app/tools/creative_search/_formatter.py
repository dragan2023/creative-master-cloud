"""Creativesearchformatter"""

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


class CreativeSearchFormatter:
    """
    创作辅助搜索结果格式化器

    将搜索结果转换为LLM友好的结构化格式
    """

    # 广告/噪声关键词
    NOISE_PATTERNS = [
        r'点击查看.*', r'扫码关注.*', r'下载APP.*',
        r'广告.*', r'推广.*', r'赞助.*',
        r'相关推荐.*', r'猜你喜欢.*'
    ]

    def preprocess_result(self, result: Dict, query: str) -> Dict:
        """预处理单条搜索结果"""
        title = result.get("title", "")
        snippet = result.get("snippet", "")

        # 1. 内容清洗
        clean_title = self._clean_content(title)
        clean_snippet = self._clean_content(snippet)

        # 2. 关键信息提取
        entities = self._extract_entities(clean_snippet)
        summary = self._generate_summary(clean_title, clean_snippet)

        # 3. 相关性评分
        relevance_score = self._calculate_relevance(
            title=clean_title,
            snippet=clean_snippet,
            query=query
        )

        return {
            "title": clean_title,
            "snippet": clean_snippet[:500],
            "entities": entities,
            "summary": summary,
            "relevance_score": relevance_score,
            "url": result.get("url", ""),
            "date": result.get("datePublished", "")
        }

    def _clean_content(self, text: str) -> str:
        """清洗内容"""
        clean = text
        for pattern in self.NOISE_PATTERNS:
            clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)
        return clean.strip()

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """提取关键实体"""
        entities = {}

        # 地点
        loc_match = re.findall(r'([\u4e00-\u9fa5]{2,}(?:省|市|县|区|镇))', text)
        if loc_match:
            entities["location"] = list(set(loc_match))[:3]

        # 时间
        time_match = re.findall(
            r'(\d{4}年|\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2})', text)
        if time_match:
            entities["date"] = list(set(time_match))[:3]

        # 数字
        num_match = re.findall(r'(\d+(?:\.\d+)?(?:%|万|亿|公里|米|年|人|次))', text)
        if num_match:
            entities["number"] = list(set(num_match))[:3]

        return entities

    def _generate_summary(self, title: str, snippet: str) -> str:
        """生成一句话摘要"""
        if len(snippet) <= 50:
            return snippet

        # 提取第一句
        sentences = re.split(r'[。！？\.\!\?]', snippet)
        if sentences:
            return sentences[0][:50] + "..."
        return snippet[:50] + "..."

    def _calculate_relevance(self, title: str, snippet: str, query: str) -> float:
        """计算相关性评分"""
        score = 0.0
        query_terms = set(query.lower().split())

        if not query_terms:
            return 0.5

        # 标题匹配
        title_terms = set(title.lower().split())
        title_overlap = len(query_terms & title_terms) / len(query_terms)
        score += title_overlap * 0.6

        # 摘要匹配
        snippet_terms = set(snippet.lower().split())
        snippet_overlap = len(query_terms & snippet_terms) / len(query_terms)
        score += snippet_overlap * 0.4

        return min(score, 1.0)

    def format_for_llm(
        self,
        results: List[Dict],
        query: str,
        max_results: int = 5,
        max_context_length: int = 2000
    ) -> str:
        """
        格式化为LLM友好的上下文
        """
        if not results:
            return ""

        # 预处理并排序
        processed = [self.preprocess_result(r, query) for r in results]
        processed.sort(key=lambda x: x["relevance_score"], reverse=True)
        processed = processed[:max_results]

        # 构建格式化输出
        parts = []
        parts.append("## 📚 创作参考资料（联网搜索结果）\n")
        parts.append("> **使用说明**：以下资料来自联网搜索，包含与您创作主题相关的背景信息。")
        parts.append("> 请参考这些信息进行创作，但不要直接复制。重要信息请标注来源。\n")

        total_length = 0
        for i, result in enumerate(processed, 1):
            entry_length = len(result["snippet"]) + 200
            if total_length + entry_length > max_context_length:
                break

            parts.append(f"### [{i}] {result['title']}")

            # 核心摘要
            if result["summary"]:
                parts.append(f"📌 **摘要**：{result['summary']}")

            # 关键实体
            entities = result.get("entities", {})
            if entities:
                entity_parts = []
                if entities.get("location"):
                    entity_parts.append(
                        f"📍 地点：{', '.join(entities['location'])}")
                if entities.get("date"):
                    entity_parts.append(f"📅 时间：{', '.join(entities['date'])}")
                if entities.get("number"):
                    entity_parts.append(
                        f"📊 数据：{', '.join(entities['number'])}")
                if entity_parts:
                    parts.append("\n".join(entity_parts))

            # 详细内容
            parts.append(f"\n📝 **详细内容**：\n{result['snippet']}")

            # 来源标注
            source_info = f"🔗 来源：{result['url']}"
            if result["date"]:
                source_info += f" ({result['date']})"
            parts.append(source_info)
            parts.append("")

            total_length += entry_length

        # 添加使用指引
        parts.append("---")
        parts.append("\n**💡 创作指引**：")
        parts.append("1. 以上资料可作为创作的背景知识参考")
        parts.append("2. 地理、历史、文化等信息可自然融入创作")
        parts.append("3. 如有冲突信息，以权威来源为准")
        parts.append("4. 创作内容应为原创，资料仅供参考")

        return "\n".join(parts)


# ==================== 搜索缓存 ====================
