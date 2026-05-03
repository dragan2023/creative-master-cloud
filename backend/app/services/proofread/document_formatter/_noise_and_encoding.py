"""DocumentFormatter - 干扰内容清理与编码修复Mixin"""
from __future__ import annotations
import re


class NoiseAndEncodingMixin:
    """干扰内容清理与编码修复"""

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

    TOC_PATTERNS = [
        # 常见目录标题
        r'^目\s*录\s*$',
        r'^目\s*次\s*$',
        r'^Contents?\s*$',
        r'^章\s*节\s*目\s*录\s*$',
        # 目录项模式（连续的章节列表，后面没有内容）
        # 这个在后面单独处理
    ]

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


