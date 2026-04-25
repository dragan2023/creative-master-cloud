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

        try:
            # 根据内容类型选择解析模式
            if content_type == "novel":
                result = self._parse_novel_chapters(content, expected_count)
            else:
                result = self._parse_script_episodes(content, expected_count)

            self.logger.info(
                f"[单元概述解析] 解析完成，预期: {expected_count}，实际: {len(result)}")

        except Exception as e:
            self.logger.error(f"[单元概述解析] 解析失败: {str(e)}")

        return result


    def _parse_novel_chapters(
        self,
        content: str,
        expected_count: int
    ) -> Dict[str, Dict[str, Any]]:
        """解析小说章节概述"""
        result = {}
        import uuid

        # 匹配章节标题和内容
        # 格式：### 第X章：[章节标题]
        chapter_pattern = r'###\s*第(\d+)章[：:]\s*(.+?)(?:\n|$)'
        matches = re.findall(chapter_pattern, content)

        for match in matches:
            chapter_num = int(match[0])
            chapter_title = match[1].strip()

            # 提取章节概要
            start_marker = f"第{chapter_num}章"
            end_marker = f"第{chapter_num + 1}章" if chapter_num < expected_count else None

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

            # v2.1: 为每个单元分配唯一ID
            unit_id = f"unit-{chapter_num}-{uuid.uuid4().hex[:8]}"

            result[str(chapter_num)] = {
                "unit_id": unit_id,
                "unit_number": chapter_num,
                "title": chapter_title,
                "summary": summary,
                "full_content": chapter_content,  # v2.1: 保存完整内容
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }

        return result


    def _parse_script_episodes(
        self,
        content: str,
        expected_count: int
    ) -> Dict[str, Dict[str, Any]]:
        """解析剧本分集/分场概述"""
        result = {}
        import uuid

        # 判断是电影类型还是剧集类型
        is_movie = "第" in content and "场" in content and "集" not in content

        if is_movie:
            pattern = r'\*\*第(\d+)场[：:]\s*(.+?)(?:\n|$)'
        else:
            pattern = r'\*\*第(\d+)集[：:]\s*(.+?)(?:\n|$)'

        matches = re.findall(pattern, content)

        for match in matches:
            unit_num = int(match[0])
            unit_title = match[1].strip()

            if is_movie:
                start_marker = f"第{unit_num}场"
            else:
                start_marker = f"第{unit_num}集"

            start_idx = content.find(start_marker)
            if start_idx == -1:
                continue

            start_idx = content.find('\n', start_idx)
            if start_idx == -1:
                continue

            next_unit = unit_num + 1
            if is_movie:
                end_marker = f"第{next_unit}场"
            else:
                end_marker = f"第{next_unit}集"

            end_idx = content.find(end_marker, start_idx)
            if end_idx == -1:
                end_idx = len(content)

            unit_content = content[start_idx:end_idx].strip()

            if is_movie:
                summary_match = re.search(
                    r'\*\*本场梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                    unit_content, re.DOTALL
                )
            else:
                summary_match = re.search(
                    r'\*\*本集梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                    unit_content, re.DOTALL
                )
            summary = summary_match.group(1).strip() if summary_match else ""

            # v2.1: 为每个单元分配唯一ID
            unit_id = f"unit-{unit_num}-{uuid.uuid4().hex[:8]}"

            result[str(unit_num)] = {
                "unit_id": unit_id,
                "unit_number": unit_num,
                "title": unit_title,
                "summary": summary,
                "full_content": unit_content,  # v2.1: 保存完整内容
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

    # ==================== 续生成辅助方法 ====================


