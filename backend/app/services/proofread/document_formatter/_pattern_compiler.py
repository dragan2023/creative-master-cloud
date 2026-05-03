"""DocumentFormatter - 模式编译（章节标题正则）Mixin"""
from __future__ import annotations
import re


class PatternCompilerMixin:
    """模式编译（章节标题正则）"""

    def _compile_patterns(self):
        """编译正则表达式模式"""
        # 章节标题标准化模式
        # 这些模式用于识别各种章节格式并提取编号和标题

        if self.content_type == "novel":
            self._compile_novel_patterns()
        elif self.content_type == "series_script":
            self._compile_series_patterns()
        elif self.content_type == "movie_script":
            self._compile_movie_patterns()
        else:
            self._compile_novel_patterns()


    def _compile_novel_patterns(self):
        """编译小说章节识别模式"""
        # 格式：(正则模式, 提取编号组索引, 提取标题组索引, 标准化类型)
        self.chapter_patterns = [
            # 标准格式：第X章 标题
            (r'^第([一二三四五六七八九十百千万零\d]+)章\s*[:：]?\s*(.*)$', 1, 2, 'standard'),
            # 括号格式：【第X章】标题
            (r'^【第([一二三四五六七八九十百千万零\d]+)章】\s*(.*)$', 1, 2, 'bracket'),
            (r'^「第([一二三四五六七八九十百千万零\d]+)章」\s*(.*)$', 1, 2, 'bracket'),
            (r'^『第([一二三四五六七八九十百千万零\d]+)章』\s*(.*)$', 1, 2, 'bracket'),
            # 英文格式：Chapter X: Title
            (r'^[Cc]hapter\s*(\d+)\s*[:：]?\s*(.*)$', 1, 2, 'english'),
            # 缩写格式：Ch. X, Chpt. X
            (r'^[Cc]h\.?\s*(\d+)\s*[:：]?\s*(.*)$', 1, 2, 'english_abbr'),
            (r'^[Cc]hpt\.?\s*(\d+)\s*[:：]?\s*(.*)$', 1, 2, 'english_abbr'),
            # 节/回格式：第X节, 第X回
            (r'^第([一二三四五六七八九十百千万零\d]+)节\s*[:：]?\s*(.*)$', 1, 2, 'section'),
            (r'^第([一二三四五六七八九十百千万零\d]+)回\s*[:：]?\s*(.*)$', 1, 2, 'episode'),
            # 卷/部格式：第X卷, 第X部
            (r'^第([一二三四五六七八九十百千万零\d]+)卷\s*[:：]?\s*(.*)$', 1, 2, 'volume'),
            (r'^第([一二三四五六七八九十百千万零\d]+)部\s*[:：]?\s*(.*)$', 1, 2, 'volume'),
            # 纯数字加点格式（需要严格验证）：1. 标题
            # 注意：此模式太容易误识别，已禁用
            # (r'^(\d+)\.\s+(.+)$', 1, 2, 'numbered'),
        ]

        # 编译模式
        self._compiled_patterns = [
            (re.compile(p, re.MULTILINE), ni, ti, nt)
            for p, ni, ti, nt in self.chapter_patterns
        ]


    def _compile_series_patterns(self):
        """编译剧集剧本分集识别模式"""
        self.chapter_patterns = [
            # 标准格式：第X集 标题
            (r'^第([一二三四五六七八九十百千万零\d]+)集\s*[:：]?\s*(.*)$', 1, 2, 'standard'),
            # 括号格式
            (r'^【第([一二三四五六七八九十百千万零\d]+)集】\s*(.*)$', 1, 2, 'bracket'),
            # 英文格式：Episode X
            (r'^[Ee]pisode\s*(\d+)\s*[:：]?\s*(.*)$', 1, 2, 'english'),
            # 缩写格式：EP X, Ep. X
            (r'^EP\s*(\d+)\s*[:：]?\s*(.*)$', 1, 2, 'english_abbr'),
            (r'^[Ee]p\.?\s*(\d+)\s*[:：]?\s*(.*)$', 1, 2, 'english_abbr'),
        ]

        self._compiled_patterns = [
            (re.compile(p, re.MULTILINE), ni, ti, nt)
            for p, ni, ti, nt in self.chapter_patterns
        ]


    def _compile_movie_patterns(self):
        """编译电影剧本场景识别模式"""
        self.chapter_patterns = [
            # 标准格式：第X场 标题
            (r'^第([一二三四五六七八九十百千万零\d]+)场\s*[:：]?\s*(.*)$', 1, 2, 'standard'),
            # 英文格式：Scene X
            (r'^[Ss]cene\s*(\d+)\s*[:：]?\s*(.*)$', 1, 2, 'english'),
            (r'^SCENE\s*(\d+)\s*[:：]?\s*(.*)$', 1, 2, 'english'),
        ]

        self._compiled_patterns = [
            (re.compile(p, re.MULTILINE), ni, ti, nt)
            for p, ni, ti, nt in self.chapter_patterns
        ]


