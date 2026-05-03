"""DocumentFormatter - 格式执行主流程Mixin"""
from __future__ import annotations
from typing import Tuple

from app.core.logger import get_logger
from app.services.proofread.document_formatter._schemas import FormattingStats

logger = get_logger(__name__)


class FormatExecutionMixin:
    """格式执行主流程"""

    def __init__(self, content_type: str = "novel"):
        """
        初始化文档格式化器

        Args:
            content_type: 内容类型 ("novel", "series_script", "movie_script")
        """
        self.content_type = content_type
        self.stats = FormattingStats()
        self._compile_patterns()


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


