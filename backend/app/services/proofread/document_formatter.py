"""
文档格式化器
在章节识别之前对文档进行预处理，确保识别的一致性和准确性

核心功能：
1. 统一章节标题格式 - 标准化各种章节表示法
2. 删除重复章节标题 - 移除嵌套重复和格式不同的重复
3. 清理干扰内容 - 移除序言、目录、版权信息等
4. 修复识别问题 - 处理特殊字符、编码、分隔符等
5. 验证和日志 - 记录处理过程和结果

使用方式：
    formatter = DocumentFormatter(content_type="novel")
    formatted_content, stats = formatter.format(content)

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from app.core.logger import get_logger

logger = get_logger("proofread.document_formatter")


@dataclass
class FormattingStats:
    """格式化统计信息"""
    original_lines: int = 0
    formatted_lines: int = 0
    original_chapters: int = 0
    formatted_chapters: int = 0
    duplicate_titles_removed: int = 0
    noise_content_removed: int = 0
    titles_normalized: int = 0
    encoding_fixes: int = 0
    markdown_headers_processed: int = 0
    steps_completed: List[str] = field(default_factory=list)


class DocumentFormatter:
    """
    文档格式化器

    在章节识别之前对文档进行预处理，解决以下问题：
    1. 章节标题格式不统一
    2. 重复章节标题
    3. 干扰性内容（序言、目录、版权等）
    4. 特殊字符和编码问题
    5. Markdown标题层级问题
    """

    # 中文数字映射
    CHINESE_NUMS = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '百': 100, '千': 1000, '万': 10000
    }

    # 阿拉伯数字到中文数字的映射（1-100）
    NUM_TO_CHINESE = {
        1: '一', 2: '二', 3: '三', 4: '四', 5: '五',
        6: '六', 7: '七', 8: '八', 9: '九', 10: '十',
        11: '十一', 12: '十二', 13: '十三', 14: '十四', 15: '十五',
        16: '十六', 17: '十七', 18: '十八', 19: '十九', 20: '二十',
        21: '二十一', 22: '二十二', 23: '二十三', 24: '二十四', 25: '二十五',
        26: '二十六', 27: '二十七', 28: '二十八', 29: '二十九', 30: '三十',
        31: '三十一', 32: '三十二', 33: '三十三', 34: '三十四', 35: '三十五',
        36: '三十六', 37: '三十七', 38: '三十八', 39: '三十九', 40: '四十',
        41: '四十一', 42: '四十二', 43: '四十三', 44: '四十四', 45: '四十五',
        46: '四十六', 47: '四十七', 48: '四十八', 49: '四十九', 50: '五十',
        51: '五十一', 52: '五十二', 53: '五十三', 54: '五十四', 55: '五十五',
        56: '五十六', 57: '五十七', 58: '五十八', 59: '五十九', 60: '六十',
        61: '六十一', 62: '六十二', 63: '六十三', 64: '六十四', 65: '六十五',
        66: '六十六', 67: '六十七', 68: '六十八', 69: '六十九', 70: '七十',
        71: '七十一', 72: '七十二', 73: '七十三', 74: '七十四', 75: '七十五',
        76: '七十六', 77: '七十七', 78: '七十八', 79: '七十九', 80: '八十',
        81: '八十一', 82: '八十二', 83: '八十三', 84: '八十四', 85: '八十五',
        86: '八十六', 87: '八十七', 88: '八十八', 89: '八十九', 90: '九十',
        91: '九十一', 92: '九十二', 93: '九十三', 94: '九十四', 95: '九十五',
        96: '九十六', 97: '九十七', 98: '九十八', 99: '九十九', 100: '一百',
    }

    # 干扰性内容模式（需要移除）
    NOISE_PATTERNS = [
        # 免责声明
        r"免责声明[：:][\s\S]{0,300}(?=\n\n|\Z)",
        r"声明[：:][\s\S]{0,200}(?=\n\n|\Z)",
        # 版权信息
        r"版权所有[，,][\s\S]{0,150}(?=\n\n|\Z)",
        r"著作权[：:][\s\S]{0,150}(?=\n\n|\Z)",
        r"[\(（]c[\)）]\s*\d{4}[\s\S]{0,100}(?=\n\n|\Z)",
        r"Copyright[\s\S]{0,150}(?=\n\n|\Z)",
        # 作者简介
        r"作者简介[：:][\s\S]{0,400}(?=\n\n|\Z)",
        r"关于作者[：:][\s\S]{0,400}(?=\n\n|\Z)",
        # 通用无意义声明
        r"本文.*?仅供参考[\s\S]{0,100}",
        r"转载请注明出处[\s\S]{0,100}",
        r"未经授权.*?禁止转载",
        r"所有权利保留",
        # 页眉页脚标记
        r"第\s*\d+\s*页\s*(共|/)\s*\d+\s*页",
        r"Page\s*\d+\s*(of|/)\s*\d+",
        # 网站水印
        r"本文来自[\s\S]{0,50}网",
        r"更多精彩.*?请访问",
        r"最新章节.*?请到",
        # 广告内容
        r"广告[：:][\s\S]{0,100}(?=\n\n|\Z)",
        r"推广[：:][\s\S]{0,100}(?=\n\n|\Z)",
    ]

    # 目录模式（需要识别并移除）
    TOC_PATTERNS = [
        # 常见目录标题
        r'^目\s*录\s*$',
        r'^目\s*次\s*$',
        r'^Contents?\s*$',
        r'^章\s*节\s*目\s*录\s*$',
        # 目录项模式（连续的章节列表，后面没有内容）
        # 这个在后面单独处理
    ]

    # 非章节关键词（用于过滤误识别）
    # 注意：不包含 '第一', '第二' 等，因为它们是章节编号的一部分
    NON_CHAPTER_KEYWORDS = {
        '首先', '其次', '再次', '然后', '最后',
        '注意', '提示', '说明', '备注', '附录', '目录', '前言', '序言',
        '简介', '概述', '摘要', '引言', '后记', '结语', '尾声',
        '步骤', '方法', '技巧', '要点', '重点', '总结',
        # 列表项指示词（需要更严格的上下文验证）
        '第一步', '第二步', '第三步', '第四步', '第五步',
        '第一种', '第二种', '第三种', '第四种', '第五种',
    }

    # 小节标题模式（章节内部的子标题，需要过滤）
    # 这些模式匹配常见的章节内部小节标题格式
    SECTION_TITLE_PATTERNS = [
        # 中文数字小节：一、二、三、等（单独一行，后面跟标点）
        r'^([一二三四五六七八九十]+)[、．.]\s*(.*)$',
        # 带括号的小节：（一）、（二）、等
        r'^[（(]([一二三四五六七八九十]+)[）)]\s*(.*)$',
        # 数字小节：1. 2. 3. 等（需要验证上下文）
        r'^(\d+)[、．.]\s*(.*)$',
    ]

    # 扩展的小节标题模式（更多格式）
    EXTENDED_SECTION_PATTERNS = [
        # 第X部分、第X节（非章节单位）
        r'^第([一二三四五六七八九十百千万零\d]+)[部分节](?![章回集场])\s*[:：]?\s*(.*)$',
        # 带圈数字：①②③等
        r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*(.*)$',
        # 罗马数字：I. II. III.等
        r'^([IVXLCDM]+)[\.．]\s*(.*)$',
    ]

    def __init__(self, content_type: str = "novel"):
        """
        初始化文档格式化器

        Args:
            content_type: 内容类型 ("novel", "series_script", "movie_script")
        """
        self.content_type = content_type
        self.stats = FormattingStats()
        self._compile_patterns()

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

    def format(self, content: str) -> Tuple[str, FormattingStats]:
        """
        格式化文档内容

        Args:
            content: 原始文档内容

        Returns:
            (格式化后的内容, 格式化统计信息)
        """
        self.stats = FormattingStats()
        self.stats.original_lines = len(content.split('\n'))

        logger.info(f"开始文档格式化，原始行数: {self.stats.original_lines}")

        # Step 1: 编码修复
        content = self._fix_encoding(content)
        self.stats.steps_completed.append('encoding_fix')

        # Step 2: 清理干扰内容
        content = self._remove_noise_content(content)
        self.stats.steps_completed.append('noise_removal')

        # Step 3: 处理Markdown标题
        content = self._process_markdown_headers(content)
        self.stats.steps_completed.append('markdown_headers')

        # Step 3.5: 标记并处理章节内部的小节标题
        # 这些小节标题会干扰章节识别，需要先标记或转换
        content = self._process_section_titles(content)
        self.stats.steps_completed.append('section_titles')

        # Step 4: 统一章节标题格式
        content, chapter_info = self._normalize_chapter_titles(content)
        self.stats.original_chapters = len(chapter_info)
        self.stats.steps_completed.append('title_normalization')

        # Step 5: 删除重复章节标题
        content = self._remove_duplicate_titles(content, chapter_info)
        self.stats.steps_completed.append('duplicate_removal')

        # Step 6: 清理多余空白
        content = self._cleanup_whitespace(content)
        self.stats.steps_completed.append('whitespace_cleanup')

        # Step 7: 验证格式化结果
        content = self._validate_and_fix(content)
        self.stats.steps_completed.append('validation')

        self.stats.formatted_lines = len(content.split('\n'))
        self.stats.formatted_chapters = self._count_chapters(content)

        logger.info(
            f"文档格式化完成: "
            f"行数 {self.stats.original_lines} -> {self.stats.formatted_lines}, "
            f"章节 {self.stats.original_chapters} -> {self.stats.formatted_chapters}, "
            f"移除重复标题 {self.stats.duplicate_titles_removed}个, "
            f"移除干扰内容 {self.stats.noise_content_removed}处, "
            f"标准化标题 {self.stats.titles_normalized}个"
        )

        return content, self.stats

    def _fix_encoding(self, content: str) -> str:
        """修复编码问题"""
        original_len = len(content)

        # 替换常见的乱码字符
        replacements = {
            '\ufeff': '',  # BOM
            '\u200b': '',  # 零宽空格
            '\u200c': '',  # 零宽非连接符
            '\u200d': '',  # 零宽连接符
            '\u200e': '',  # 从左到右标记
            '\u200f': '',  # 从右到左标记
            '\u2028': '\n',  # 行分隔符
            '\u2029': '\n\n',  # 段落分隔符
            '\u00a0': ' ',  # 不换行空格
            '\u3000': ' ',  # 全角空格
            '\r\n': '\n',  # Windows换行
            '\r': '\n',  # 旧Mac换行
        }

        for old, new in replacements.items():
            if old in content:
                content = content.replace(old, new)
                self.stats.encoding_fixes += 1

        if len(content) != original_len:
            logger.debug(f"编码修复: {original_len} -> {len(content)} 字符")

        return content

    def _remove_noise_content(self, content: str) -> str:
        """移除干扰性内容"""
        original_len = len(content)

        for pattern in self.NOISE_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                content = re.sub(pattern, '', content,
                                 flags=re.IGNORECASE | re.DOTALL)
                self.stats.noise_content_removed += len(matches)

        # 移除目录区域
        content = self._remove_table_of_contents(content)

        if len(content) != original_len:
            logger.debug(f"干扰内容移除: {original_len} -> {len(content)} 字符")

        return content

    def _remove_table_of_contents(self, content: str) -> str:
        """移除目录区域"""
        lines = content.split('\n')
        result_lines = []
        in_toc = False
        toc_start_line = -1
        consecutive_chapter_refs = 0

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 检测目录开始
            for pattern in self.TOC_PATTERNS:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    in_toc = True
                    toc_start_line = i
                    logger.debug(f"检测到目录开始于第{i+1}行")
                    break

            if in_toc:
                # 检测目录结束条件
                # 1. 遇到真正的章节标题（带内容）
                # 2. 连续空白行
                # 3. 遇到正文开始标记

                # 检查是否为目录项（只有章节标题，没有内容）
                is_toc_entry = False
                for pattern, _, _, _ in self._compiled_patterns:
                    if pattern.match(line_stripped):
                        # 检查下一行是否有内容
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if not next_line or len(next_line) < 20:
                                # 下一行为空或很短，可能是目录项
                                is_toc_entry = True
                                consecutive_chapter_refs += 1
                        break

                # 如果连续遇到多个章节引用，保持在目录模式
                if is_toc_entry:
                    continue

                # 如果遇到非章节内容，可能是正文开始
                if line_stripped and not is_toc_entry:
                    # 检查是否为正文开始
                    if len(line_stripped) > 50 or consecutive_chapter_refs > 3:
                        # 可能是正文开始，退出目录模式
                        in_toc = False
                        logger.debug(f"目录结束于第{i+1}行，共跳过{i - toc_start_line}行")
                        result_lines.append(line)
                    else:
                        consecutive_chapter_refs = 0
            else:
                result_lines.append(line)

        return '\n'.join(result_lines)

    def _process_markdown_headers(self, content: str) -> str:
        """处理Markdown标题"""
        lines = content.split('\n')
        result_lines = []

        for line in lines:
            # 检测Markdown标题
            match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()

                # 一级和二级标题转换为章节格式
                if level <= 2:
                    # 检查标题是否已经包含章节编号
                    has_chapter_num = bool(
                        re.search(r'第[一二三四五六七八九十百千万零\d]+[章节回集场]', title) or
                        re.search(r'[Cc]hapter\s*\d+', title) or
                        re.search(r'[Ee]pisode\s*\d+', title) or
                        re.search(r'[Ss]cene\s*\d+', title)
                    )

                    if not has_chapter_num:
                        # 尝试从标题中提取数字
                        num_match = re.search(r'(\d+)', title)
                        if num_match:
                            num = int(num_match.group(1))
                            # 转换为标准格式
                            unit = self._get_unit_name()
                            chinese_num = self._number_to_chinese(num)
                            title = f"第{chinese_num}{unit} {title}"
                            self.stats.markdown_headers_processed += 1

                    result_lines.append(title)
                else:
                    # 三级及以下标题保留原样
                    result_lines.append(line)
            else:
                result_lines.append(line)

        return '\n'.join(result_lines)

    def _process_section_titles(self, content: str) -> str:
        """
        处理章节内部的小节标题

        小节标题（如"一、"、"二、"、"三、"、"1."、"2."等）经常被误识别为章节标题。
        这个方法将这些小节标题转换为特殊格式，避免干扰章节识别。

        处理策略：
        1. 识别小节标题模式（中文数字+顿号、括号数字、阿拉伯数字等）
        2. 通过上下文验证确认是否为小节标题
        3. 将小节标题转换为【小节】标记格式
        4. 保留原始内容，但避免被章节识别器误识别
        """
        lines = content.split('\n')
        result_lines = []
        section_count = 0

        # 编译小节标题模式
        section_patterns = [
            # 中文数字小节：一、二、三、等（高优先级）
            (re.compile(r'^([一二三四五六七八九十]+)[、．.]\s*(.+)$'),
             'chinese_num', 'high'),
            # 带括号的小节：（一）、（二）、等（高优先级）
            (re.compile(r'^[（(]([一二三四五六七八九十]+)[）)]\s*(.+)$'),
             'bracket_num', 'high'),
            # 数字小节：1. 2. 3. 等（需要更严格的验证）
            (re.compile(r'^(\d{1,2})[、．.]\s*(.+)$'), 'digit_num', 'medium'),
            # 带括号的数字：（1）、（2）、等
            (re.compile(r'^[（(](\d{1,2})[）)]\s*(.+)$'),
             'bracket_digit', 'medium'),
            # 带圈数字：①②③等
            (re.compile(r'^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮])\s*(.*)$'),
             'circle_num', 'medium'),
        ]

        # 扩展模式（需要更严格的上下文验证）
        extended_patterns = [
            # 第X部分、第X节（非章节单位）
            (re.compile(
                r'^第([一二三四五六七八九十百千万零\d]+)[部分节]\s*[:：]?\s*(.*)$'), 'part_section', 'low'),
        ]

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            converted = False

            # 跳过空行和已经是章节标题的行
            if not line_stripped or self._is_chapter_title(line_stripped):
                result_lines.append(line)
                continue

            # 检查基本小节模式
            for pattern, pattern_type, priority in section_patterns:
                match = pattern.match(line_stripped)
                if match:
                    section_num = match.group(1)
                    section_title = match.group(2).strip() if len(
                        match.groups()) > 1 else ""

                    # 根据优先级进行不同的验证
                    if priority == 'high':
                        # 高优先级模式：基本验证即可
                        if self._is_section_title(section_num, section_title, line_stripped):
                            converted_line = f"【小节】{section_num}、{section_title}" if section_title else f"【小节】{section_num}"
                            result_lines.append(converted_line)
                            section_count += 1
                            converted = True
                            logger.debug(
                                f"转换小节标题(高优先级): {line_stripped} -> {converted_line}")
                            break
                    elif priority == 'medium':
                        # 中优先级模式：需要更严格的上下文验证
                        if self._is_section_title_with_context(section_num, section_title, line_stripped, lines, i):
                            converted_line = f"【小节】{section_num}、{section_title}" if section_title else f"【小节】{section_num}"
                            result_lines.append(converted_line)
                            section_count += 1
                            converted = True
                            logger.debug(
                                f"转换小节标题(中优先级): {line_stripped} -> {converted_line}")
                            break

            # 如果基本模式没有匹配，检查扩展模式
            if not converted:
                for pattern, pattern_type, priority in extended_patterns:
                    match = pattern.match(line_stripped)
                    if match:
                        section_num = match.group(1)
                        section_title = match.group(2).strip() if len(
                            match.groups()) > 1 else ""

                        # 扩展模式需要严格的上下文验证
                        if self._is_section_title_with_context(section_num, section_title, line_stripped, lines, i):
                            converted_line = f"【小节】{section_num}、{section_title}" if section_title else f"【小节】{section_num}"
                            result_lines.append(converted_line)
                            section_count += 1
                            converted = True
                            logger.debug(
                                f"转换小节标题(扩展模式): {line_stripped} -> {converted_line}")
                            break

            if not converted:
                result_lines.append(line)

        if section_count > 0:
            logger.info(f"处理了 {section_count} 个小节标题")

        return '\n'.join(result_lines)

    def _is_chapter_title(self, line: str) -> bool:
        """
        检查是否为章节标题

        Args:
            line: 行内容

        Returns:
            是否为章节标题
        """
        # 检查是否匹配章节标题模式
        for pattern, _, _, _ in self._compiled_patterns:
            if pattern.match(line):
                return True
        return False

    def _is_section_title_with_context(
        self,
        section_num: str,
        section_title: str,
        original_line: str,
        lines: List[str],
        current_index: int
    ) -> bool:
        """
        带上下文验证的小节标题判断

        用于数字小节等需要更严格验证的模式。

        Args:
            section_num: 小节编号
            section_title: 小节标题
            original_line: 原始行内容
            lines: 所有行
            current_index: 当前行索引

        Returns:
            是否为小节标题
        """
        # 首先进行基本验证
        if not self._is_section_title(section_num, section_title, original_line):
            return False

        # 上下文验证：检查是否在章节标题之后
        # 小节标题通常出现在章节标题之后，而不是文档开头
        found_chapter_before = False
        check_range = min(30, current_index)  # 检查前30行

        for j in range(current_index - 1, max(-1, current_index - check_range - 1), -1):
            if j < 0 or j >= len(lines):
                continue
            check_line = lines[j].strip()
            if not check_line:
                continue
            if self._is_chapter_title(check_line):
                found_chapter_before = True
                break
            # 如果遇到另一个【小节】标记，也说明在章节内
            if check_line.startswith('【小节】'):
                found_chapter_before = True
                break

        # 如果在章节标题之后出现，更可能是小节
        if not found_chapter_before:
            # 如果没有找到前置章节标题，检查是否在文档开头
            # 文档开头的数字列表更可能是目录或列表项
            if current_index < 10:  # 前10行
                return False

        # 检查编号是否连续（可选的额外验证）
        # 如果前后有其他数字小节，更可能是真正的小节

        return True

    def _is_section_title(self, section_num: str, section_title: str, original_line: str) -> bool:
        """
        验证是否为章节内部的小节标题

        Args:
            section_num: 小节编号（中文数字或阿拉伯数字）
            section_title: 小节标题
            original_line: 原始行内容

        Returns:
            是否为小节标题（True=是小节标题，应该被转换）
        """
        # 1. 如果标题包含"章"、"集"、"场"等章节关键词，可能是章节标题，不转换
        chapter_keywords = ['章', '集', '场', 'Chapter', 'Episode', 'Scene']
        for keyword in chapter_keywords:
            if keyword in original_line:
                return False

        # 2. 如果标题长度过长（超过30字），可能是正文，不转换
        if len(original_line) > 30:
            return False

        # 3. 如果标题以句号结尾，可能是正文句子，不转换
        if section_title.endswith(('。', '？', '！', '.', '?', '!')):
            return False

        # 4. 检查是否为非章节关键词
        for keyword in self.NON_CHAPTER_KEYWORDS:
            if keyword in section_title or keyword in original_line:
                return False

        # 5. 新增：检查标题是否过短（只有编号没有标题）
        # 如果只有编号没有标题内容，可能是列表项而非小节标题
        if not section_title.strip():
            # 只有编号的情况需要更严格的验证
            # 中文数字编号单独出现时，通常是小节标题
            # 但需要确保不是章节标题的一部分
            if section_num in ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']:
                return True  # 中文数字单独出现，可能是小节
            return False

        # 6. 新增：检查标题内容是否像正文
        # 如果标题包含多个句子（有多个句号），可能是正文
        if section_title.count('。') > 1:
            return False

        # 7. 新增：检查编号是否合理
        # 如果编号超过20，可能不是小节标题
        try:
            num = int(section_num) if section_num.isdigit(
            ) else self._chinese_to_number(section_num)
            if num > 20:  # 小节编号通常不会超过20
                return False
        except (ValueError, IndexError) as e:
            logger.warning(f"解析小节编号失败: {e}")
            pass

        return True

    def _get_unit_name(self) -> str:
        """获取内容类型对应的单位名称"""
        if self.content_type == "novel":
            return "章"
        elif self.content_type == "series_script":
            return "集"
        elif self.content_type == "movie_script":
            return "场"
        return "章"

    def _number_to_chinese(self, num: int) -> str:
        """将数字转换为中文"""
        if num in self.NUM_TO_CHINESE:
            return self.NUM_TO_CHINESE[num]

        # 对于大于100的数字，动态生成
        if num <= 0:
            return "零"

        result = ""
        if num >= 10000:
            result += self.NUM_TO_CHINESE.get(num //
                                              10000, str(num // 10000)) + "万"
            num %= 10000
        if num >= 1000:
            result += self.NUM_TO_CHINESE.get(num //
                                              1000, str(num // 1000)) + "千"
            num %= 1000
        if num >= 100:
            result += self.NUM_TO_CHINESE.get(num //
                                              100, str(num // 100)) + "百"
            num %= 100
        if num >= 10:
            if num >= 20:
                result += self.NUM_TO_CHINESE.get(num // 10, str(num // 10))
            result += "十"
            num %= 10
        if num > 0:
            result += self.NUM_TO_CHINESE.get(num, str(num))

        return result

    def _chinese_to_number(self, chinese_str: str) -> int:
        """将中文数字转换为阿拉伯数字"""
        if not chinese_str:
            return 0

        if chinese_str.isdigit():
            return int(chinese_str)

        if len(chinese_str) == 1 and chinese_str in self.CHINESE_NUMS:
            return self.CHINESE_NUMS[chinese_str]

        result = 0
        temp = 0

        for char in chinese_str:
            if char in self.CHINESE_NUMS:
                num = self.CHINESE_NUMS[char]
                if num >= 10:
                    if temp == 0:
                        temp = 1
                    result += temp * num
                    temp = 0
                else:
                    temp = num

        result += temp
        return result if result > 0 else 0

    def _normalize_chapter_titles(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        统一章节标题格式

        Returns:
            (格式化后的内容, 章节信息列表)
        """
        lines = content.split('\n')
        result_lines = []
        chapter_info = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            normalized = False

            for pattern, num_group, title_group, norm_type in self._compiled_patterns:
                match = pattern.match(line_stripped)
                if match:
                    groups = match.groups()
                    number_str = groups[num_group -
                                        1] if num_group <= len(groups) else ''
                    title = groups[title_group -
                                   1] if title_group <= len(groups) else ''

                    # 验证是否为有效章节标题
                    if not self._is_valid_chapter_title(title, line_stripped):
                        continue

                    # 转换章节编号
                    if number_str.isdigit():
                        number = int(number_str)
                    else:
                        number = self._chinese_to_number(number_str)

                    if number <= 0:
                        continue

                    # 标准化为统一格式
                    unit = self._get_unit_name()
                    chinese_num = self._number_to_chinese(number)

                    # 清理标题
                    title = title.strip()
                    # 移除标题中可能存在的编号前缀
                    title = re.sub(
                        r'^[\d一二三四五六七八九十百千万零]+[\.、\s:：]+', '', title)
                    title = re.sub(
                        r'^第[一二三四五六七八九十百千万零\d]+[章节回集场][\s:：]*', '', title)
                    title = title.strip()

                    # 生成标准化标题
                    if title:
                        normalized_title = f"第{chinese_num}{unit} {title}"
                    else:
                        normalized_title = f"第{chinese_num}{unit}"

                    result_lines.append(normalized_title)
                    chapter_info.append({
                        'line_index': i,
                        'number': number,
                        'original_title': line_stripped,
                        'normalized_title': normalized_title,
                        'title': title
                    })

                    self.stats.titles_normalized += 1
                    normalized = True
                    break

            if not normalized:
                result_lines.append(line)

        return '\n'.join(result_lines), chapter_info

    def _is_valid_chapter_title(self, title: str, original_line: str) -> bool:
        """验证是否为有效的章节标题"""
        # 检查非章节关键词
        for keyword in self.NON_CHAPTER_KEYWORDS:
            if keyword in title or keyword in original_line:
                return False

        # 检查标题长度
        if len(original_line) > 100:
            return False

        # 检查是否以句号结尾
        if title.endswith(('。', '？', '！', '.', '?', '!')):
            return False

        # 检查是否为纯数字
        if title.isdigit():
            return False

        return True

    def _remove_duplicate_titles(self, content: str, chapter_info: List[Dict[str, Any]]) -> str:
        """移除重复的章节标题"""
        if not chapter_info:
            return content

        lines = content.split('\n')

        # 检测重复：相同编号的章节标题在很近的距离内出现
        seen_numbers = {}  # number -> (line_index, title)
        lines_to_remove = set()

        for info in chapter_info:
            number = info['number']
            line_idx = info['line_index']
            title = info.get('title', '')

            if number in seen_numbers:
                prev_line_idx, prev_title = seen_numbers[number]

                # 如果两个相同编号的章节标题距离很近（< 5行），可能是重复
                if line_idx - prev_line_idx < 5:
                    # 保留标题更完整的那个
                    if len(title) > len(prev_title):
                        lines_to_remove.add(prev_line_idx)
                        seen_numbers[number] = (line_idx, title)
                    else:
                        lines_to_remove.add(line_idx)
                    self.stats.duplicate_titles_removed += 1
                    logger.debug(
                        f"移除重复章节标题: 第{number}章 "
                        f"(行{prev_line_idx + 1} vs 行{line_idx + 1})"
                    )
                else:
                    # 距离较远，可能是分卷或其他情况，保留
                    seen_numbers[number] = (line_idx, title)
            else:
                seen_numbers[number] = (line_idx, title)

        # 构建结果
        result_lines = [
            line for i, line in enumerate(lines)
            if i not in lines_to_remove
        ]

        return '\n'.join(result_lines)

    def _cleanup_whitespace(self, content: str) -> str:
        """清理多余空白"""
        # 移除行尾空白
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)

        # 限制连续空行为最多2个
        content = re.sub(r'\n{3,}', '\n\n', content)

        # 移除行首多余空格（保留缩进）
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            # 保留最多4个空格的缩进
            stripped = line.lstrip()
            indent_len = min(len(line) - len(stripped), 4)
            cleaned_lines.append(' ' * indent_len + stripped)

        return '\n'.join(cleaned_lines)

    def _validate_and_fix(self, content: str) -> str:
        """验证格式化结果并修复问题"""
        lines = content.split('\n')

        # 检测章节编号连续性
        chapter_numbers = []
        for line in lines:
            for pattern, _, _, _ in self._compiled_patterns:
                match = pattern.match(line.strip())
                if match:
                    number_str = match.groups()[0]
                    if number_str.isdigit():
                        chapter_numbers.append(int(number_str))
                    else:
                        chapter_numbers.append(
                            self._chinese_to_number(number_str))
                    break

        if chapter_numbers:
            sorted_numbers = sorted(chapter_numbers)
            expected = list(range(1, max(sorted_numbers) + 1))
            missing = set(expected) - set(sorted_numbers)

            if missing:
                logger.warning(f"检测到章节编号不连续，缺失: {sorted(missing)[:10]}...")

        return content

    def _count_chapters(self, content: str) -> int:
        """统计章节数量"""
        count = 0
        for pattern, _, _, _ in self._compiled_patterns:
            matches = pattern.findall(content)
            count = max(count, len(matches))
        return count


def format_document(content: str, content_type: str = "novel") -> Tuple[str, FormattingStats]:
    """
    格式化文档的便捷函数

    Args:
        content: 文档内容
        content_type: 内容类型

    Returns:
        (格式化后的内容, 格式化统计信息)
    """
    formatter = DocumentFormatter(content_type=content_type)
    return formatter.format(content)
