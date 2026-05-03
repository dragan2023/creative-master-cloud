"""Searchtriggeranalyzer"""

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


class SearchTriggerAnalyzer:
    """
    搜索触发分析器 - 判断是否需要搜索

    通过规则分析用户输入，判断是否包含需要联网搜索的信息：
    - 地点信息（小众地名）
    - 时间/年代（历史背景）
    - 专业领域（专业知识）
    - 近期事件（时效性信息）
    """

    # 需要搜索的信号词
    SEARCH_SIGNALS = {
        # 地理相关
        "location": [
            "省", "市", "县", "区", "镇", "乡", "村",
            "街道", "路", "巷", "胡同", "广场", "公园", "景区"
        ],
        # 时间相关
        "time": [
            "年代", "时期", "朝代", "世纪", "历史",
            "古代", "近代", "现代", "当代", "民国"
        ],
        # 专业领域
        "domain": [
            "医学", "法律", "金融", "科技", "军事",
            "体育", "艺术", "建筑", "工程", "农业",
            "教育", "航天", "航海", "医学", "生物"
        ],
        # 近期事件信号
        "recent": [
            "最新", "近期", "今年", "去年", "当前",
            "现在", "目前", "近日", "2024", "2025"
        ]
    }

    # 通用知识主题（不需要搜索）
    COMMON_KNOWLEDGE = [
        "爱情", "友情", "亲情", "人生", "梦想",
        "成功", "失败", "成长", "奋斗", "幸福",
        "友谊", "家庭", "爱情故事", "感人"
    ]

    def should_search(
        self,
        input_params: Dict[str, Any],
        module: str
    ) -> Tuple[bool, str, List[str]]:
        """
        判断是否需要搜索

        Args:
            input_params: 用户输入参数
            module: 创作模块

        Returns:
            (need_search, reason, suggested_keywords)
        """
        # 提取关键文本
        topic = input_params.get("topic", "")
        theme = input_params.get("theme", "")
        setting = input_params.get("setting", "")
        synopsis = input_params.get("synopsis", "")

        combined_text = f"{topic} {theme} {setting} {synopsis}"

        # 1. 检查是否有搜索信号
        signals_found = self._detect_search_signals(combined_text)

        # 2. 检查是否是纯通用知识主题
        if self._is_pure_common_knowledge(combined_text):
            return False, "主题属于通用知识范畴，无需联网搜索", []

        # 3. 检查是否有小众/特定实体
        specific_entities = self._extract_specific_entities(combined_text)

        # 4. 综合判断
        if signals_found or specific_entities:
            keywords = self._generate_search_keywords(
                input_params, signals_found, specific_entities
            )
            reason = self._explain_search_reason(
                signals_found, specific_entities)
            return True, reason, keywords

        return False, "未检测到需要搜索的特定信息", []

    def _detect_search_signals(self, text: str) -> Dict[str, List[str]]:
        """检测搜索信号"""
        signals = {}
        for category, keywords in self.SEARCH_SIGNALS.items():
            found = [kw for kw in keywords if kw in text]
            if found:
                signals[category] = found
        return signals

    def _is_pure_common_knowledge(self, text: str) -> bool:
        """检查是否是纯通用知识主题"""
        # 如果主题只包含通用概念，且没有其他特定信息
        for kw in self.COMMON_KNOWLEDGE:
            if kw in text:
                # 移除通用词后检查是否还有实质内容
                other_info = text.replace(kw, "").strip()
                # 如果剩余内容很短，可能是纯通用主题
                if len(other_info) < 5:
                    return True
        return False

    def _extract_specific_entities(self, text: str) -> List[str]:
        """提取特定实体（小众地名、专有名词等）"""
        entities = []

        # 提取可能的小众地名（非一线城市）
        location_pattern = r'([\u4e00-\u9fa5]{2,}(?:省|市|县|区|镇|村|街道|路|巷))'
        matches = re.findall(location_pattern, text)

        # 常见大城市，不需要特别搜索
        major_cities = ["北京", "上海", "广州", "深圳", "中国"]

        for match in matches:
            # 检查是否是小众地名
            is_major = any(city in match for city in major_cities)
            if not is_major and len(match) >= 3:
                entities.append(match)

        # 提取引号内容（专有名词）
        quoted = re.findall(r'["「『『【]([^"」』』】]+)["」』』】]', text)
        entities.extend([q for q in quoted if len(q) >= 2])

        return list(set(entities))[:5]

    def _generate_search_keywords(
        self,
        input_params: Dict,
        signals: Dict[str, List[str]],
        entities: List[str]
    ) -> List[str]:
        """生成搜索关键词"""
        keywords = []
        topic = input_params.get("topic", "")
        theme = input_params.get("theme", "")

        # 1. 实体优先
        for entity in entities[:2]:
            keywords.append(f"{entity} 简介 背景")

        # 2. 地点相关
        if "location" in signals:
            # 尝试提取完整地点
            loc_match = re.search(
                r'([\u4e00-\u9fa5]{2,}(?:省|市|县|区)[\u4e00-\u9fa5]*)', topic)
            if loc_match:
                loc = loc_match.group(1)
                keywords.append(f"{loc} 历史 文化 风土人情")

        # 3. 时间相关
        if "time" in signals:
            if theme:
                keywords.append(f"{theme} 历史背景")
            for time_sig in signals["time"][:1]:
                keywords.append(f"{time_sig} 历史 背景")

        # 4. 专业领域
        if "domain" in signals:
            for domain in signals["domain"][:1]:
                keywords.append(f"{domain} 基础知识 入门")

        # 去重并限制数量
        return list(set(keywords))[:3]

    def _explain_search_reason(
        self,
        signals: Dict[str, List[str]],
        entities: List[str]
    ) -> str:
        """解释搜索原因"""
        reasons = []

        if entities:
            reasons.append(f"检测到特定实体：{', '.join(entities[:3])}")

        if "location" in signals:
            reasons.append("包含地理信息，需要了解当地背景")
        if "time" in signals:
            reasons.append("包含历史时期，需要了解时代背景")
        if "domain" in signals:
            reasons.append("包含专业领域，需要专业知识支持")
        if "recent" in signals:
            reasons.append("涉及近期信息，需要最新资料")

        return "；".join(reasons) if reasons else "检测到需要补充的信息"


# ==================== 关键词提取器 ====================
