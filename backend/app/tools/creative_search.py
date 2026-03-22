"""
创作辅助搜索模块

提供智能的联网搜索功能，帮助LLM获取创作所需的背景资料。
核心特性：
1. 智能触发判断 - 只在必要时搜索
2. 关键词提取 - 规则提取优先，用户指定最高优先
3. 质量评估 - 多维度评分过滤低质量结果
4. 高质量格式化 - LLM友好的结构化输出
5. 缓存机制 - 减少重复API调用
"""
from typing import Dict, List, Any, Optional, Tuple
import re
import time
import hashlib
import asyncio
from datetime import datetime

from app.core.logger import get_logger

logger = get_logger(__name__)


# ==================== 搜索触发分析器 ====================

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

        elif module == "script":
            scenes = input_params.get("scenes", "")
            if scenes:
                keywords.append(f"{scenes[:15]} 场景")

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
            except:
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
                    ).order_by(UserAPIKey.is_default.desc())
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
                        ).order_by(UserAPIKey.is_default.desc())
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


def get_creative_search() -> OptimizedCreativeSearch:
    """获取创作辅助搜索实例"""
    global _creative_search
    if _creative_search is None:
        _creative_search = OptimizedCreativeSearch()
    return _creative_search
