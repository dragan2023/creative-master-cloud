"""
敏感实体检查器
检测文本中的敏感地名、名人、历史事件
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.services.proofread.trie_matcher import TrieMatcher, MultiTrieMatcher, MatchResult
from app.services.proofread.data.built_in_entities import get_entity_data
from app.core.logger import get_logger

logger = get_logger("proofread.sensitive_checker")


@dataclass
class SensitiveIssue:
    """敏感实体问题"""
    issue_type: str
    severity: str
    text: str
    position_start: int
    position_end: int
    description: str
    suggestion: str
    metadata: Dict[str, Any]


class SensitiveChecker:
    """
    敏感实体检查器

    功能：
    - 检测敏感地名
    - 检测敏感名人
    - 检测敏感历史事件
    - 检测敏感词

    特点：
    - 本地检测，不消耗LLM
    - 基于Trie树，高效匹配
    - 支持不同敏感等级
    """

    # 敏感等级阈值映射
    SEVERITY_THRESHOLD = {
        "strict": ["high", "medium", "low"],
        "normal": ["high", "medium"],
        "loose": ["high"]
    }

    def __init__(
        self,
        compliance_level: str = "normal"
    ):
        """
        初始化检查器

        Args:
            compliance_level: 合规检查等级 (strict/normal/loose)
        """
        self.compliance_level = compliance_level
        self._matcher: Optional[MultiTrieMatcher] = None
        self._initialized = False

    def initialize(self):
        """初始化匹配器"""
        if self._initialized:
            return

        # 加载内置实体数据
        entity_data = get_entity_data()

        # 构建多Trie匹配器
        self._matcher = MultiTrieMatcher()

        # 地名匹配器
        location_matcher = TrieMatcher.build_from_entities({
            "locations": entity_data["locations"]
        })
        self._matcher.add_matcher("location", location_matcher)

        # 人名匹配器
        person_matcher = TrieMatcher.build_from_entities({
            "persons": entity_data["persons"]
        })
        self._matcher.add_matcher("person", person_matcher)

        # 历史事件匹配器
        event_matcher = TrieMatcher.build_from_entities({
            "events": entity_data["events"]
        })
        self._matcher.add_matcher("event", event_matcher)

        # 敏感词匹配器
        word_matcher = TrieMatcher.build_from_entities({
            "sensitive_words": entity_data["sensitive_words"]
        })
        self._matcher.add_matcher("sensitive_word", word_matcher)

        self._initialized = True
        logger.info(
            f"敏感实体检查器初始化完成，合规等级: {self.compliance_level}"
        )

    def check(self, text: str) -> List[SensitiveIssue]:
        """
        检查文本中的敏感实体

        Args:
            text: 待检查文本

        Returns:
            敏感问题列表
        """
        if not self._initialized:
            self.initialize()

        issues = []
        threshold = self.SEVERITY_THRESHOLD.get(
            self.compliance_level,
            self.SEVERITY_THRESHOLD["normal"]
        )

        # 执行匹配
        matches = self._matcher.search_all(text)

        # 处理地名匹配
        for match in matches.get("location", []):
            issue = self._create_location_issue(match, threshold)
            if issue:
                issues.append(issue)

        # 处理人名匹配
        for match in matches.get("person", []):
            issue = self._create_person_issue(match, threshold)
            if issue:
                issues.append(issue)

        # 处理历史事件匹配
        for match in matches.get("event", []):
            issue = self._create_event_issue(match, threshold)
            if issue:
                issues.append(issue)

        # 处理敏感词匹配
        for match in matches.get("sensitive_word", []):
            issue = self._create_sensitive_word_issue(match, threshold)
            if issue:
                issues.append(issue)

        logger.debug(f"检测完成，发现 {len(issues)} 个敏感实体")
        return issues

    def _create_location_issue(
        self,
        match: MatchResult,
        threshold: List[str]
    ) -> Optional[SensitiveIssue]:
        """创建地名问题"""
        data = match.data
        severity = data.get("severity", "medium")

        # 检查是否在阈值范围内
        if severity not in threshold:
            return None

        return SensitiveIssue(
            issue_type="sensitive_location",
            severity=severity,
            text=match.text,
            position_start=match.start,
            position_end=match.end,
            description=f"检测到中国地名「{match.text}」，请确认是否需要使用虚构地名替代",
            suggestion="建议使用虚构地名或避免涉及具体地理位置",
            metadata={
                "location_name": match.text,
                "category": data.get("category", "unknown")
            }
        )

    def _create_person_issue(
        self,
        match: MatchResult,
        threshold: List[str]
    ) -> Optional[SensitiveIssue]:
        """创建人名问题"""
        data = match.data
        severity = data.get("severity", "medium")

        # 检查是否在阈值范围内
        if severity not in threshold:
            return None

        category = data.get("category", "unknown")
        category_cn = {
            "actors": "演员",
            "directors": "导演",
            "singers": "歌手",
            "writers": "作家",
            "politicians": "政治人物",
            "athletes": "运动员",
            "entrepreneurs": "企业家",
            "scientists": "科学家"
        }.get(category, category)

        return SensitiveIssue(
            issue_type="sensitive_person",
            severity=severity,
            text=match.text,
            position_start=match.start,
            position_end=match.end,
            description=f"检测到知名{category_cn}「{match.text}」，请确认是否为虚构人物",
            suggestion="建议使用虚构人物名或确保不涉及真实人物隐私",
            metadata={
                "person_name": data.get("name", match.text),
                "category": category,
                "aliases": data.get("aliases", [])
            }
        )

    def _create_event_issue(
        self,
        match: MatchResult,
        threshold: List[str]
    ) -> Optional[SensitiveIssue]:
        """创建历史事件问题"""
        data = match.data
        severity = data.get("severity", "medium")

        # 检查是否在阈值范围内
        if severity not in threshold:
            return None

        period = data.get("period", "")
        description = data.get("description", "")

        return SensitiveIssue(
            issue_type="sensitive_event",
            severity=severity,
            text=match.text,
            position_start=match.start,
            position_end=match.end,
            description=f"检测到历史事件「{match.text}」({period})，请确认内容表述是否恰当",
            suggestion="建议核实历史事实，避免不当描述",
            metadata={
                "event_name": match.text,
                "period": period,
                "description": description
            }
        )

    def _create_sensitive_word_issue(
        self,
        match: MatchResult,
        threshold: List[str]
    ) -> Optional[SensitiveIssue]:
        """创建敏感词问题"""
        data = match.data
        severity = data.get("severity", "high")

        # 敏感词通常是高危，直接返回
        return SensitiveIssue(
            issue_type="sensitive_word",
            severity="high",
            text=match.text,
            position_start=match.start,
            position_end=match.end,
            description=f"检测到敏感内容「{match.text}」",
            suggestion="建议修改或删除相关内容",
            metadata={
                "word": match.text
            }
        )

    def check_chapter(
        self,
        chapter_id: int,
        chapter_title: str,
        content: str
    ) -> List[Dict[str, Any]]:
        """
        检查章节内容

        Args:
            chapter_id: 章节ID
            chapter_title: 章节标题
            content: 章节内容

        Returns:
            问题字典列表
        """
        issues = self.check(content)

        return [
            {
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "original_text": issue.text,
                "position_start": issue.position_start,
                "position_end": issue.position_end,
                "description": issue.description,
                "suggestion": issue.suggestion,
                "metadata": issue.metadata
            }
            for issue in issues
        ]

    def update_compliance_level(self, level: str):
        """
        更新合规检查等级

        Args:
            level: 新的检查等级
        """
        if level in self.SEVERITY_THRESHOLD:
            self.compliance_level = level
            logger.info(f"合规检查等级已更新为: {level}")
        else:
            logger.warning(f"无效的合规检查等级: {level}")
