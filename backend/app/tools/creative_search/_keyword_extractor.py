"""Keywordextractor"""

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


class KeywordExtractor:
    """
    搜索关键词提取器

    提取优先级：用户指定 > 规则提取 > 返回空
    """

    # 停用词（不需要搜索的通用词）
    STOP_WORDS = {
        "故事", "小说", "文章", "内容", "东西", "事情",
        "一个", "一些", "什么", "怎么", "如何", "为什么",
        "的人", "的时候", "什么的", "怎样的"
    }

    def extract_keywords(
        self,
        input_params: Dict[str, Any],
        module: str,
        user_keywords: Optional[List[str]] = None
    ) -> List[str]:
        """
        提取搜索关键词

        Args:
            input_params: 用户输入参数
            module: 创作模块
            user_keywords: 用户指定的关键词

        Returns:
            关键词列表
        """
        # 1. 用户指定优先
        if user_keywords:
            return self._optimize_keywords(user_keywords)

        # 2. 规则提取
        keywords = self._extract_by_rules(input_params, module)

        # 3. 优化
        if keywords:
            keywords = self._optimize_keywords(keywords)

        return keywords

    def _extract_by_rules(self, input_params: Dict, module: str) -> List[str]:
        """基于规则提取关键词"""
        keywords = []

        topic = input_params.get("topic", "")
        theme = input_params.get("theme", "")
        setting = input_params.get("setting", "")

        # 1. 地点提取
        locations = self._extract_locations(topic + " " + setting)
        for loc in locations:
            keywords.append(f"{loc} 历史 文化")

        # 2. 时间/年代提取
        time_periods = self._extract_time_periods(topic + " " + theme)
        for period in time_periods:
            keywords.append(f"{period} 背景")

        # 3. 专业领域提取
        domains = self._extract_domains(topic + " " + theme)
        for domain in domains:
            keywords.append(f"{domain} 知识")

        # 4. 模块特定提取
        module_keywords = self._extract_by_module(input_params, module)
        keywords.extend(module_keywords)

        return list(set(keywords))

    def _extract_locations(self, text: str) -> List[str]:
        """提取地点名称"""
        locations = []

        patterns = [
            r'([\u4e00-\u9fa5]{2,}(?:省|市|县|区|镇|乡|村))',
            r'([\u4e00-\u9fa5]{2,}(?:街道|路|巷|胡同|广场|公园))',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 3 and match not in self.STOP_WORDS:
                    locations.append(match)

        return list(set(locations))[:2]

    def _extract_time_periods(self, text: str) -> List[str]:
        """提取时间/年代"""
        periods = []

        patterns = [
            r'(\d{4}年代?)',
            r'(\d{4}年)',
            r'(明清|民国|抗战|解放|改革开放)',
            r'(古代|近代|现代|当代)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            periods.extend(matches)

        return list(set(periods))[:2]

    def _extract_domains(self, text: str) -> List[str]:
        """提取专业领域"""
        domains = []

        domain_keywords = [
            "医学", "法律", "金融", "科技", "军事",
            "体育", "艺术", "建筑", "工程", "农业",
            "教育", "航天", "航海", "生物", "化学"
        ]

        for domain in domain_keywords:
            if domain in text:
                domains.append(domain)

        return domains[:2]

    def _extract_by_module(self, input_params: Dict, module: str) -> List[str]:
        """模块特定关键词提取"""
        keywords = []

        if module == "novel":
            synopsis = input_params.get("synopsis", "")
            if synopsis and len(synopsis) > 10:
                # 提取前20个字符作为背景搜索
                keywords.append(f"{synopsis[:20]} 背景")

        # [DEPRECATED] script 模块已移除，此分支不再触发
        # 保留用于兼容历史数据
        elif module == "script":
            pass

        return keywords

    def _optimize_keywords(self, keywords: List[str]) -> List[str]:
        """优化关键词"""
        optimized = []

        for kw in keywords:
            # 移除停用词
            for stop_word in self.STOP_WORDS:
                kw = kw.replace(stop_word, "")

            kw = kw.strip()

            # 过滤太短的关键词
            if len(kw) >= 3:
                optimized.append(kw)

        return list(set(optimized))[:3]


# ==================== 搜索结果质量评估器 ====================
