"""大纲生成器 - 大纲解析与格式化工具Mixin"""
from typing import Dict
from typing import List
from typing import Any
from datetime import datetime
import re
import os
from app.core.config import get_settings


class ParserMixin:
    """大纲解析与格式化工具"""

    def parse_unit_summaries(
        self,
        content: str,
        expected_count: int,
        content_type: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        解析单元概述内容

        Args:
            content: LLM生成的原始内容
            expected_count: 预期单元数量
            content_type: 内容类型 (novel/script)

        Returns:
            解析后的单元概述字典
        """
        result = {}
        content_len = len(content) if content else 0
        self.logger.info(
            f"[单元概述解析] 开始解析, content_type={content_type}, 内容长度={content_len}")

        try:
            # 根据内容类型选择解析模式
            if content_type == "novel":
                result = self._parse_novel_chapters(content, expected_count)
            else:
                result = self._parse_script_episodes(content, expected_count, content_type)

            self.logger.info(
                f"[单元概述解析] 解析完成，预期: {expected_count}，实际: {len(result)}")

            # v3.4诊断日志: 解析结果为0但有内容时，记录原始内容样本
            if len(result) == 0 and content_len > 0:
                sample = content[:500].replace('\n', '\\n')
                self.logger.warning(
                    f"[单元概述解析] ⚠️ 解析结果为零！内容长度={content_len}字符，"
                    f"前500字符样本: {sample}"
                )

        except Exception as e:
            self.logger.error(f"[单元概述解析] 解析失败: {str(e)}")

        return result


    def _parse_novel_chapters(
        self,
        content: str,
        expected_count: int
    ) -> Dict[str, Dict[str, Any]]:
        """解析小说章节概述（v3.4: 多格式回退解析）"""
        result = {}
        import uuid

        # ==================== 多层回退正则以适应不同标题风格 ====================
        # 优先匹配标准格式，失败后依次尝试宽松格式
        chapter_patterns = [
            # 第0层: 标准格式 ### 第N章：[标题] 或 ### 第N章: [标题]
            (r'###\s*第(\d+)章[：:]\s*(.+?)(?:\n|$)', 'standard_colon'),
            # 第1层: 空格分隔 ### 第N章 [标题]
            (r'###\s*第(\d+)章\s+(.+?)(?:\n|$)', 'standard_space'),
            # 第2层: 无前缀 第N章[：:][标题]
            (r'(?:^|\n)\s*第(\d+)章[：:]\s*(.+?)(?:\n|$)', 'no_prefix_colon'),
            # 第3层: 无前缀+空格 第N章 [标题]
            (r'(?:^|\n)\s*第(\d+)章\s+(.+?)(?:\n|$)', 'no_prefix_space'),
            # 第4层: ### 第N回：[标题]（古典章回体使用"回"代替"章"）
            (r'###\s*第(\d+)回[：:]\s*(.+?)(?:\n|$)', 'classical_hui'),
            # 第5层: 中文数字 ### 第[一二三四五六七八九十百千]+章[：:]
            (r'###\s*第([一二三四五六七八九十百千\d]+)章[：:]\s*(.+?)(?:\n|$)', 'chinese_numeral'),
        ]

        matches = []
        matched_layer = None

        for pattern, layer_name in chapter_patterns:
            raw_matches = re.findall(pattern, content, re.MULTILINE)
            if raw_matches:
                matches = raw_matches
                matched_layer = layer_name
                self.logger.info(
                    f"[单元概述解析] 使用'{layer_name}'模式匹配到{len(matches)}个章节")
                break

        # 诊断日志: 所有模式均未匹配
        if not matches:
            self.logger.warning(
                f"[单元概述解析] ⚠️ 所有正则模式均未匹配到章节！"
                f" 内容长度={len(content)}字符"
            )
            return result

        for match in matches:
            # 处理中文数字转换
            raw_num = match[0]
            if matched_layer == 'chinese_numeral' and not raw_num.isdigit():
                chapter_num = self._chinese_to_arabic(raw_num)
            else:
                chapter_num = int(raw_num)
            chapter_title = match[1].strip()

            # [2026-05-05 诊断] 打印原始标题内容
            self.logger.info(
                f"[单元概述解析] 第{chapter_num}章原始title行(前100字): [{chapter_title[:100]}]"
            )

            # [2026-05-05] 修复：处理标题与梗概合并到同一行的情况
            # LLM可能输出"第N章：标题 本章梗概：摘要内容"——将标题和摘要放在同一行
            summary_from_title = ""
            title_cleaned = chapter_title
            merged_pattern = re.search(
                r'^(.*?)\s+(?:\*\*)?(?:本章)?梗概(?:\*\*)?[：:]\s*(.+)$',
                chapter_title
            )
            if merged_pattern:
                title_cleaned = merged_pattern.group(1).strip()
                summary_from_title = merged_pattern.group(2).strip()
                self.logger.info(
                    f"[单元概述解析] 第{chapter_num}章标题与梗概在同一行，已分离: "
                    f"title={title_cleaned[:30]}, summary_len={len(summary_from_title)}"
                )
            elif '梗概' in chapter_title:
                # 回退：简单字符串拆分（正则未匹配时使用）
                idx = chapter_title.find('梗概')
                start = idx
                while start > 0 and chapter_title[start-1] in ('*', '本', '章', '回'):
                    start -= 1
                if start > 0 and chapter_title[start-1] in (' ', '	'):
                    start -= 1
                title_cleaned = chapter_title[:start].strip().rstrip('：:').strip()
                colon_pos = max(chapter_title.find('：', idx), chapter_title.find(':', idx))
                if colon_pos >= 0 and colon_pos < len(chapter_title) - 1:
                    summary_from_title = chapter_title[colon_pos+1:].strip()
                    self.logger.info(
                        f"[单元概述解析] 第{chapter_num}章标题与梗概在同一行(回退拆分)，已分离: "
                        f"title={title_cleaned[:30]}, summary_len={len(summary_from_title)}"
                    )

            # 提取章节概要
            # v3.4: 兼容古典章回体(回)的start_marker
            if matched_layer == 'classical_hui':
                unit_char = '回'
                end_char = '回'
            else:
                unit_char = '章'
                end_char = '章'
            start_marker = f"第{chapter_num}{unit_char}"
            end_marker = f"第{chapter_num + 1}{end_char}" if chapter_num < expected_count else None

            start_idx = content.find(start_marker)
            if start_idx == -1:
                continue

            start_idx = content.find('\n', start_idx)
            if start_idx == -1:
                continue

            if end_marker:
                end_idx = content.find(end_marker, start_idx)
                if end_idx == -1:
                    end_idx = len(content)
            else:
                end_idx = len(content)

            chapter_content = content[start_idx:end_idx].strip()

            # 提取概要
            summary_match = re.search(
                r'\*\*本章梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                chapter_content, re.DOTALL
            )
            summary = summary_match.group(1).strip() if summary_match else ""

            # [2026-05-05] 如果从标题行提取到了摘要，与chapter_content中的摘要合并处理
            if summary_from_title:
                if not summary:
                    summary = summary_from_title
                elif len(summary_from_title) > len(summary):
                    # 两者都有时，优先使用更长的（更完整的）
                    summary = summary_from_title

            # v2.1: 为每个单元分配唯一ID
            unit_id = f"unit-{chapter_num}-{uuid.uuid4().hex[:8]}"

            result[str(chapter_num)] = {
                "unit_id": unit_id,
                "unit_number": chapter_num,
                "title": title_cleaned,  # [2026-05-05] 使用清理后的标题
                "summary": summary,
                "full_content": chapter_content,  # v2.1: 保存完整内容
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }

        return result


    def _parse_script_episodes(
        self,
        content: str,
        expected_count: int,
        content_type: str = "series_script"
    ) -> Dict[str, Dict[str, Any]]:
        """解析剧本分集/分场概述（v5.1: 多层回退解析）

        支持格式：
        - ### 第N集：标题 / ### 第N集: 标题 (markdown heading)
        - **第N集：标题** (bold)
        - 第N集：标题 (plain text)
        - ### 第N场：标题 / **第N场：标题** (电影)
        """
        result = {}
        import uuid

        # ==================== 根据content_type确定单元标签 ====================
        is_movie = content_type in ("movie_script", "movie_outline")
        unit_char = "场" if is_movie else "集"

        # ==================== 多层回退正则以适应不同标题风格 ====================
        episode_patterns = [
            # 第0层: ### 第N集/场：标题 (markdown heading+冒号)
            (rf'###\s*第(\d+){unit_char}[：:]\s*(.+?)(?:\n|$)', 'heading_colon'),
            # 第1层: ### 第N集/场 [标题] (markdown heading+空格)
            (rf'###\s*第(\d+){unit_char}\s+(.+?)(?:\n|$)', 'heading_space'),
            # 第2层: **第N集/场：标题** (bold+冒号)
            (rf'\*\*第(\d+){unit_char}[：:]\s*(.+?)\*\*', 'bold_colon'),
            # 第3层: 无前缀 第N集/场：标题 (plain text+冒号)
            (rf'(?:^|\n)\s*第(\d+){unit_char}[：:]\s*(.+?)(?:\n|$)', 'plain_colon'),
            # 第4层: 无前缀+空格 第N集/场 标题 (plain text+空格)
            (rf'(?:^|\n)\s*第(\d+){unit_char}\s+(.+?)(?:\n|$)', 'plain_space'),
        ]

        matches = []
        matched_layer = None

        for pattern, layer_name in episode_patterns:
            raw_matches = re.findall(pattern, content, re.MULTILINE)
            if raw_matches:
                matches = raw_matches
                matched_layer = layer_name
                self.logger.info(
                    f"[单元概述解析] 使用'{layer_name}'模式匹配到{len(matches)}个{unit_char}")
                break

        # 诊断日志: 所有模式均未匹配
        if not matches:
            self.logger.warning(
                f"[单元概述解析] ⚠️ 所有正则模式均未匹配到{unit_char}！"
                f" 内容长度={len(content)}字符, content_type={content_type}"
            )
            return result

        for match in matches:
            unit_num = int(match[0])
            unit_title = match[1].strip()

            # [2026-05-05 诊断] 打印原始标题内容
            self.logger.info(
                f"[单元概述解析] 第{unit_num}{unit_char}原始title行(前100字): [{unit_title[:100]}]"
            )

            # [2026-05-05] 修复：处理标题与梗概合并到同一行的情况
            summary_from_title = ""
            title_cleaned = unit_title
            merged_pattern = re.search(
                r'^(.*?)\s+(?:\*\*)?(?:本集|本场|本章)?梗概(?:\*\*)?[：:]\s*(.+)$',
                unit_title
            )
            if merged_pattern:
                title_cleaned = merged_pattern.group(1).strip()
                summary_from_title = merged_pattern.group(2).strip()
                self.logger.info(
                    f"[单元概述解析] 第{unit_num}{unit_char}标题与梗概在同一行，已分离"
                )
            elif '梗概' in unit_title:
                # 回退：简单字符串拆分（正则未匹配时使用）
                idx = unit_title.find('梗概')
                start = idx
                while start > 0 and unit_title[start-1] in ('*', '本', '章', '集', '场'):
                    start -= 1
                if start > 0 and unit_title[start-1] in (' ', '	'):
                    start -= 1
                title_cleaned = unit_title[:start].strip().rstrip('：:').strip()
                colon_pos = max(unit_title.find('：', idx), unit_title.find(':', idx))
                if colon_pos >= 0 and colon_pos < len(unit_title) - 1:
                    summary_from_title = unit_title[colon_pos+1:].strip()
                    self.logger.info(
                        f"[单元概述解析] 第{unit_num}{unit_char}标题与梗概在同一行(回退拆分)，已分离"
                    )

            # 定位内容边界
            start_marker = f"第{unit_num}{unit_char}"
            start_idx = content.find(start_marker)
            if start_idx == -1:
                continue

            start_idx = content.find('\n', start_idx)
            if start_idx == -1:
                continue

            next_unit = unit_num + 1
            end_marker = f"第{next_unit}{unit_char}" if next_unit <= expected_count else None

            if end_marker:
                end_idx = content.find(end_marker, start_idx)
                if end_idx == -1:
                    end_idx = len(content)
            else:
                end_idx = len(content)

            unit_content = content[start_idx:end_idx].strip()

            # 提取梗概（兼容本集/本章/本场梗概等多种变体）
            summary_match = re.search(
                rf'\*\*(?:本{unit_char}|本章)梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|\n-\s|\n###|$)',
                unit_content, re.DOTALL
            )
            # 回退：无bold标记 本集/本章梗概：
            if not summary_match:
                summary_match = re.search(
                    rf'(?:本{unit_char}|本章)梗概[：:]\s*(.+?)(?:\n\n|\n\*\*|\n-\s|\n###|$)',
                    unit_content, re.DOTALL
                )
            # 再回退：仅匹配 梗概：
            if not summary_match:
                summary_match = re.search(
                    r'梗概[：:]\s*(.+?)(?:\n\n|\n\*\*|\n-\s|\n###|$)',
                    unit_content, re.DOTALL
                )
            summary = summary_match.group(1).strip() if summary_match else ""

            # [2026-05-05] 如果从标题行提取到了摘要，与unit_content中的摘要合并处理
            if summary_from_title:
                if not summary:
                    summary = summary_from_title
                elif len(summary_from_title) > len(summary):
                    summary = summary_from_title

            # v2.1: 为每个单元分配唯一ID
            unit_id = f"unit-{unit_num}-{uuid.uuid4().hex[:8]}"

            result[str(unit_num)] = {
                "unit_id": unit_id,
                "unit_number": unit_num,
                "title": title_cleaned,
                "summary": summary,
                "full_content": unit_content,
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }

        return result

    # ==================== 截断检测与接续生成模块 ====================


    def get_expected_unit_count(
        self,
        global_outline: str,
        user_input_count: int = None,
        content_type: str = "novel"
    ) -> int:
        """
        获取预期单元数量(用于截断检测)

        优先级:
        1. 从全局大纲解析的实际单元数(最高)
        2. 用户输入的参数值(次之)
        3. 默认值(最低)

        Args:
            global_outline: 全局大纲内容
            user_input_count: 用户输入的单元数量
            content_type: 内容类型(novel/script)

        Returns:
            预期单元数量
        """
        # 1. 优先从全局大纲解析
        outline_count = self._parse_unit_count_from_outline(
            global_outline, content_type)
        if outline_count and outline_count > 0:
            self.logger.info(
                f"[截断检测] 从全局大纲解析到{outline_count}个单元,使用此值作为expected_count")
            return outline_count

        # 2. 回退到用户输入
        if user_input_count and user_input_count > 0:
            self.logger.info(f"[截断检测] 全局大纲未解析到单元数,使用用户输入:{user_input_count}")
            return user_input_count

        # 3. 使用默认值
        default_count = 50 if content_type == "novel" else 24
        self.logger.warning(f"[截断检测] 无法获取单元数量,使用默认值:{default_count}")
        return default_count


    def _parse_unit_count_from_outline(
        self,
        outline: str,
        content_type: str
    ) -> int:
        """
        从全局大纲内容中解析单元数量

        匹配模式:
        - "共X章" / "总计X章" / "一共X章"
        - "共X集" / "总计X集"
        - "共X场" / "总计X场"
        - "Chapter 1-100" / "第1章至第100章"

        Args:
            outline: 全局大纲内容
            content_type: 内容类型

        Returns:
            解析出的单元数量,失败返回0
        """
        if content_type == "novel":
            patterns = [
                r'共\s*([一二三四五六七八九十百千万\d]+)\s*章',
                r'总计\s*([一二三四五六七八九十百千万\d]+)\s*章',
                r'一共\s*([一二三四五六七八九十百千万\d]+)\s*章',
                r'第\s*1\s*章\s*(?:至|到|~|-)\s*第\s*([一二三四五六七八九十百千万\d]+)\s*章',
            ]
        else:  # script
            patterns = [
                r'共\s*([一二三四五六七八九十百千万\d]+)\s*集',
                r'总计\s*([一二三四五六七八九十百千万\d]+)\s*集',
                r'一共\s*([一二三四五六七八九十百千万\d]+)\s*集',
                r'共\s*([一二三四五六七八九十百千万\d]+)\s*场',
                r'总计\s*([一二三四五六七八九十百千万\d]+)\s*场',
            ]

        for pattern in patterns:
            match = re.search(pattern, outline)
            if match:
                # 获取匹配的数字(可能是第1个或第2个捕获组)
                count_str = match.group(1)
                if match.lastindex == 2:
                    count_str = match.group(2)

                # 中文数字转阿拉伯数字
                if count_str and not count_str.isdigit():
                    count = self._chinese_to_number(count_str)
                else:
                    count = int(count_str) if count_str else 0

                if count > 0:
                    return count

        return 0


    def detect_truncated_units(
        self,
        content: str,
        parsed: Dict[str, Dict[str, Any]],
        expected_count: int,
        content_type: str
    ) -> Dict[str, Any]:
        """
        检测单元概述是否被截断

        Args:
            content: LLM生成的原始内容
            parsed: 解析后的单元概述字典
            expected_count: 预期单元数量
            content_type: 内容类型

        Returns:
            {
                "has_truncation": bool,
                "truncated_units": List[int],  # 被截断的单元号列表
                "missing_units": List[int],     # 完全缺失的单元号列表
                "truncation_details": Dict      # 每个截断单元的详细信息
            }
        """
        result = {
            "has_truncation": False,
            "truncated_units": [],
            "missing_units": [],
            "truncation_details": {}
        }

        try:
            # 1. 数量完整性检测
            parsed_count = len(parsed)
            if parsed_count < expected_count:
                # 检测缺失的单元号
                parsed_units = set(int(k) for k in parsed.keys())
                all_expected_units = set(range(1, expected_count + 1))
                missing_units = sorted(all_expected_units - parsed_units)

                result["missing_units"] = missing_units
                result["has_truncation"] = True

                self.logger.info(
                    f"[截断检测] 数量不完整: 预期{expected_count}个, 实际{parsed_count}个, "
                    f"缺失{len(missing_units)}个单元: {missing_units[:10]}..."
                )

            # 2. 结构完整性检测(检查每个已解析的单元)
            for unit_num_str, unit_data in parsed.items():
                unit_num = int(unit_num_str)
                full_content = unit_data.get("full_content", "")

                # 检测内容是否完整
                is_truncated = self._check_unit_completeness(
                    full_content, content_type, unit_num
                )

                if is_truncated:
                    result["truncated_units"].append(unit_num)
                    result["has_truncation"] = True
                    result["truncation_details"][unit_num] = {
                        "type": "incomplete_structure",
                        "reason": "内容结构不完整(可能因token限制被截断)"
                    }
                    self.logger.warning(
                        f"[截断检测] 第{unit_num}单元结构不完整,可能被截断"
                    )

            if not result["has_truncation"]:
                self.logger.info(
                    f"[截断检测] 完整性检查通过: {parsed_count}/{expected_count}个单元")

        except Exception as e:
            self.logger.error(f"[截断检测] 检测失败: {str(e)}")

        return result


    def _check_unit_completeness(
        self,
        unit_content: str,
        content_type: str,
        unit_num: int
    ) -> bool:
        """
        检查单个单元的内容完整性

        Args:
            unit_content: 单元的完整内容
            content_type: 内容类型
            unit_num: 单元号

        Returns:
            True表示不完整(被截断),False表示完整
        """
        if not unit_content or len(unit_content.strip()) < 50:
            return True

        # 1. 检查结尾是否为完整标点
        stripped = unit_content.rstrip()
        if not stripped:
            return True

        last_char = stripped[-1]
        complete_punctuation = {'。', '！', '？', '”', '）', ']', '}', '…', '\n'}

        if last_char not in complete_punctuation:
            # 结尾不是完整标点,可能被截断
            self.logger.debug(
                f"[完整性检测] 第{unit_num}单元结尾字符'{last_char}'不是完整标点"
            )
            return True

        # 2. 检查必要字段是否存在
        if content_type == "novel":
            # 小说章节应包含"本章梗概"标记
            if "**本章梗概**" not in unit_content and "本章梗概：" not in unit_content:
                self.logger.debug(f"[完整性检测] 第{unit_num}单元缺少'本章梗概'字段")
                return True
        else:
            # 剧本应包含"本集梗概"或"本场梗概"
            if "**本集梗概**" not in unit_content and "本集梗概：" not in unit_content:
                if "**本场梗概**" not in unit_content and "本场梗概：" not in unit_content:
                    self.logger.debug(f"[完整性检测] 第{unit_num}单元缺少梗概字段")
                    return True

        # 3. 检查是否突然中断(最后一句是否完整)
        lines = unit_content.split('\n')
        if lines:
            last_line = lines[-1].strip()
            # 如果最后一行超过50字符且没有标点,可能不完整
            if len(last_line) > 50 and not any(p in last_line for p in {'。', '！', '？', '…'}):
                self.logger.debug(f"[完整性检测] 第{unit_num}单元最后一行过长且无标点")
                return True

        return False


    def save_outline_to_file(
        self,
        content: str,
        file_type: str,  # global_outline/unit_summaries
        project_id: int,
        user_id: int
    ) -> str:
        """
        保存大纲内容到文件

        Args:
            content: 大纲内容
            file_type: 文件类型
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            文件路径
        """
        settings = get_settings()
        upload_dir = settings.get_upload_dir()

        # 创建大纲目录
        outline_dir = os.path.join(upload_dir, "outlines")
        os.makedirs(outline_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{file_type}_{project_id}_{timestamp}.md"
        file_path = os.path.join(outline_dir, filename)

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        self.logger.info(f"[大纲保存] 文件已保存: {file_path}")

        return file_path

    @staticmethod
    def _chinese_to_arabic(chinese_num: str) -> int:
        """
        将中文数字字符串转换为阿拉伯整数

        支持: 一~九、十~九十、百~九百、千~九千、万
        例如: "一" -> 1, "十" -> 10, "二十五" -> 25, "一百二十三" -> 123

        Args:
            chinese_num: 中文数字字符串

        Returns:
            阿拉伯整数
        """
        if not chinese_num:
            return 1
        if chinese_num.isdigit():
            return int(chinese_num)

        cn_num_map = {
            '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
            '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
            '两': 2,
        }
        cn_unit_map = {
            '十': 10, '百': 100, '千': 1000, '万': 10000,
        }

        result = 0
        section = 0  # 当前节(万以下)

        for char in chinese_num:
            if char in cn_num_map:
                section = cn_num_map[char]
            elif char in cn_unit_map:
                unit = cn_unit_map[char]
                if section == 0:
                    section = 1
                if unit >= 10000:
                    result = (result + section) * unit
                    section = 0
                else:
                    section *= unit
                    if unit >= 10:
                        result += section
                        section = 0
            else:
                # 无法识别的字符，跳过
                pass

        result += section
        return result if result > 0 else 1

    # ==================== 续生成辅助方法 ====================


