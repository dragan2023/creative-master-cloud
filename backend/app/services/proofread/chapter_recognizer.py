"""
章节识别器
识别文档中的章节标题（小说章节、剧本分集、电影场景）

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from app.core.logger import get_logger

logger = get_logger("shared.chapter_recognizer")


@dataclass
class ChapterMatch:
    """章节匹配结果"""
    number: int
    title: Optional[str]
    original_line: str
    start_pos: int
    end_pos: int
    confidence: float = 1.0


class ChapterRecognizer:
    """
    章节识别器

    支持识别：
    - 小说章节：第X章、Chapter X、第X节
    - 剧本分集：第X集、Episode X
    - 电影场景：第X场、Scene X
    """

    # 中文数字映射
    CHINESE_NUMBERS = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '百': 100, '千': 1000, '万': 10000
    }

    # 章节模式
    PATTERNS = {
        "novel": [
            # 第X章、第X节
            r'第\s*([零一二三四五六七八九十百千万\d]+)\s*[章节回]\s*[：:\s]*(.*?)(?:\n|$)',
            # Chapter X
            r'[Cc]hapter\s*(\d+)\s*[：:\s]*(.*?)(?:\n|$)',
            # 数字编号章节
            r'^(\d+)\s*[\.、]\s*(.+?)(?:\n|$)',
        ],
        "series_script": [
            # 第X集
            r'第\s*([零一二三四五六七八九十百千万\d]+)\s*集\s*[：:\s]*(.*?)(?:\n|$)',
            # Episode X
            r'[Ee]pisode\s*(\d+)\s*[：:\s]*(.*?)(?:\n|$)',
        ],
        "movie_script": [
            # 第X场
            r'第\s*([零一二三四五六七八九十百千万\d]+)\s*场\s*[：:\s]*(.*?)(?:\n|$)',
            # Scene X
            r'[Ss]cene\s*(\d+)\s*[：:\s]*(.*?)(?:\n|$)',
        ]
    }

    def __init__(self, content_type: str = "novel"):
        """
        初始化识别器

        Args:
            content_type: 内容类型 (novel/series_script/movie_script)
        """
        self.content_type = content_type

    def recognize(self, content: str) -> List[ChapterMatch]:
        """
        识别内容中的章节

        Args:
            content: 文档内容

        Returns:
            章节匹配列表
        """
        patterns = self.PATTERNS.get(self.content_type, self.PATTERNS["novel"])
        matches = []
        seen_numbers = set()

        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                number_str = match.group(1)
                title = match.group(2).strip() if len(
                    match.groups()) > 1 else None

                # 转换数字
                if number_str.isdigit():
                    number = int(number_str)
                else:
                    number = self._chinese_to_number(number_str)

                if number is None or number in seen_numbers:
                    continue

                seen_numbers.add(number)
                matches.append(ChapterMatch(
                    number=number,
                    title=title,
                    original_line=match.group(0).strip(),
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=1.0
                ))

        # 按章节号排序
        matches.sort(key=lambda x: x.number)
        return matches

    def _chinese_to_number(self, chinese: str) -> Optional[int]:
        """
        将中文数字转换为阿拉伯数字

        Args:
            chinese: 中文数字字符串

        Returns:
            阿拉伯数字，转换失败返回 None
        """
        if not chinese:
            return None

        # 纯数字
        if chinese.isdigit():
            return int(chinese)

        # 简单中文数字
        if chinese in self.CHINESE_NUMBERS:
            return self.CHINESE_NUMBERS[chinese]

        # 复合中文数字
        result = 0
        temp = 0

        for char in chinese:
            if char not in self.CHINESE_NUMBERS:
                continue

            num = self.CHINESE_NUMBERS[char]

            if num >= 10:
                if temp == 0:
                    temp = 1
                result += temp * num
                temp = 0
            else:
                temp = temp * 10 + num if temp else num

        result += temp
        return result if result > 0 else None


def count_chapters(content: str, content_type: str = "novel") -> int:
    """
    统计内容中的章节数

    Args:
        content: 文档内容
        content_type: 内容类型

    Returns:
        章节数量
    """
    recognizer = ChapterRecognizer(content_type)
    matches = recognizer.recognize(content)
    return len(matches)


def recognize_chapters(content: str, content_type: str = "novel") -> List[Dict[str, Any]]:
    """
    识别内容中的章节

    Args:
        content: 文档内容
        content_type: 内容类型

    Returns:
        章节列表，每个元素包含 number, title, original_line, confidence
    """
    recognizer = ChapterRecognizer(content_type)
    matches = recognizer.recognize(content)

    return [
        {
            "number": m.number,
            "title": m.title,
            "original_line": m.original_line,
            "confidence": m.confidence
        }
        for m in matches
    ]
