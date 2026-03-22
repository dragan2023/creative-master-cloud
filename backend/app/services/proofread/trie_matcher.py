"""
Trie树匹配器
高效的敏感实体匹配实现
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.core.logger import get_logger

logger = get_logger("proofread.trie_matcher")


@dataclass
class MatchResult:
    """匹配结果"""
    text: str
    start: int
    end: int
    data: Dict[str, Any]


class TrieNode:
    """Trie树节点"""

    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.is_end: bool = False
        self.data: Optional[Dict[str, Any]] = None


class TrieMatcher:
    """
    Trie树匹配器

    用于高效的敏感实体匹配
    时间复杂度：O(n)，n为文本长度

    特点：
    - 支持中文
    - 支持别名匹配
    - 返回所有匹配位置
    """

    def __init__(self):
        """初始化Trie树"""
        self.root = TrieNode()
        self._entity_count = 0

    def insert(self, word: str, data: Dict[str, Any] = None):
        """
        插入词汇

        Args:
            word: 词汇
            data: 附加数据
        """
        if not word:
            return

        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

        node.is_end = True
        node.data = data or {}
        self._entity_count += 1

    def search(self, text: str) -> List[MatchResult]:
        """
        搜索文本中所有匹配的词汇

        Args:
            text: 待搜索文本

        Returns:
            匹配结果列表
        """
        matches = []
        n = len(text)

        i = 0
        while i < n:
            node = self.root
            j = i
            last_match = None

            # 尝试从位置i开始匹配
            while j < n and text[j] in node.children:
                node = node.children[text[j]]
                j += 1

                if node.is_end:
                    # 记录最长匹配
                    last_match = MatchResult(
                        text=text[i:j],
                        start=i,
                        end=j,
                        data=node.data
                    )

            # 如果找到匹配，使用最长匹配
            if last_match:
                matches.append(last_match)
                i = j  # 跳过已匹配的部分
            else:
                i += 1

        return matches

    def search_with_overlap(self, text: str) -> List[MatchResult]:
        """
        搜索文本中所有匹配（包括重叠匹配）

        Args:
            text: 待搜索文本

        Returns:
            匹配结果列表
        """
        matches = []
        n = len(text)

        for i in range(n):
            node = self.root
            j = i

            while j < n and text[j] in node.children:
                node = node.children[text[j]]
                j += 1

                if node.is_end:
                    matches.append(MatchResult(
                        text=text[i:j],
                        start=i,
                        end=j,
                        data=node.data
                    ))

        return matches

    def contains(self, text: str) -> bool:
        """
        检查文本是否包含任何匹配词汇

        Args:
            text: 待检查文本

        Returns:
            是否包含匹配
        """
        n = len(text)

        for i in range(n):
            node = self.root
            j = i

            while j < n and text[j] in node.children:
                node = node.children[text[j]]
                j += 1

                if node.is_end:
                    return True

        return False

    def get_entity_count(self) -> int:
        """获取已插入的实体数量"""
        return self._entity_count

    @classmethod
    def build_from_entities(cls, entities: Dict[str, List]) -> 'TrieMatcher':
        """
        从实体库构建Trie树

        Args:
            entities: 实体库字典
                {
                    "locations": ["北京", "上海", ...],
                    "persons": [{"name": "成龙", "aliases": [...]}, ...],
                    "events": [{"name": "鸦片战争", ...}, ...],
                    "sensitive_words": ["敏感词1", ...]
                }

        Returns:
            TrieMatcher实例
        """
        matcher = cls()

        # 添加地名
        for location in entities.get("locations", []):
            if isinstance(location, str):
                matcher.insert(location, {
                    "type": "location",
                    "name": location
                })
            elif isinstance(location, dict):
                name = location.get("name", "")
                if name:
                    matcher.insert(name, {
                        "type": "location",
                        **location
                    })

        # 添加人名
        for person in entities.get("persons", []):
            if isinstance(person, dict):
                name = person.get("name", "")
                if name:
                    data = {
                        "type": "person",
                        **person
                    }
                    matcher.insert(name, data)

                    # 添加别名
                    for alias in person.get("aliases", []):
                        if alias:
                            matcher.insert(alias, data)

        # 添加历史事件
        for event in entities.get("events", []):
            if isinstance(event, dict):
                name = event.get("name", "")
                if name:
                    matcher.insert(name, {
                        "type": "event",
                        **event
                    })

        # 添加敏感词
        for word in entities.get("sensitive_words", []):
            if word:
                matcher.insert(word, {
                    "type": "sensitive_word",
                    "name": word
                })

        logger.info(f"构建Trie树完成，共插入 {matcher.get_entity_count()} 个实体")
        return matcher


class MultiTrieMatcher:
    """
    多Trie树匹配器

    为不同类型的实体使用独立的Trie树，提高效率
    """

    def __init__(self):
        """初始化多Trie匹配器"""
        self._matchers: Dict[str, TrieMatcher] = {}

    def add_matcher(self, name: str, matcher: TrieMatcher):
        """
        添加命名匹配器

        Args:
            name: 匹配器名称
            matcher: TrieMatcher实例
        """
        self._matchers[name] = matcher

    def search_all(self, text: str) -> Dict[str, List[MatchResult]]:
        """
        使用所有匹配器搜索

        Args:
            text: 待搜索文本

        Returns:
            {
                "location": [...],
                "person": [...],
                "event": [...],
                ...
            }
        """
        results = {}

        for name, matcher in self._matchers.items():
            matches = matcher.search(text)
            if matches:
                results[name] = matches

        return results

    def get_all_matches(self, text: str) -> List[MatchResult]:
        """
        获取所有匹配结果（合并列表）

        Args:
            text: 待搜索文本

        Returns:
            所有匹配结果列表
        """
        all_matches = []

        for matcher in self._matchers.values():
            all_matches.extend(matcher.search(text))

        # 按位置排序
        all_matches.sort(key=lambda m: m.start)

        return all_matches
