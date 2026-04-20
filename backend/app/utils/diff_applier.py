"""
Diff应用工具 - 将LLM输出的差异指令应用到完整内容
"""
import re
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def apply_diff_instructions(content: str, diff_instructions: Dict[str, Any]) -> str:
    """
    应用差异指令到内容

    Args:
        content: 当前完整内容
        diff_instructions: LLM输出的差异指令JSON

    Returns:
        修改后的完整内容
    """
    modifications = diff_instructions.get("modifications", [])

    if not modifications:
        logger.warning("No modifications found in diff instructions")
        return content

    # 按location排序,从后往前应用(避免位置偏移)
    modifications.sort(key=lambda m: m.get("location", ""), reverse=True)

    modified_content = content
    applied_count = 0
    failed_count = 0

    for mod in modifications:
        mod_type = mod.get("type")
        location = mod.get("location", "")
        original_text = mod.get("original_text", "")
        new_text = mod.get("new_text", "")

        try:
            if mod_type == "replace":
                # 精确替换
                if original_text and original_text in modified_content:
                    modified_content = modified_content.replace(
                        original_text, new_text, 1)
                    applied_count += 1
                else:
                    # 尝试模糊匹配(基于location)
                    logger.warning(
                        f"Exact match failed for replace at {location}, trying fuzzy match")
                    modified_content = _fuzzy_replace(
                        modified_content, location, original_text, new_text)
                    applied_count += 1

            elif mod_type == "insert":
                # 在指定位置插入
                modified_content = _insert_at_location(
                    modified_content, location, new_text)
                applied_count += 1

            elif mod_type == "delete":
                # 删除指定内容
                if original_text and original_text in modified_content:
                    modified_content = modified_content.replace(
                        original_text, "", 1)
                    applied_count += 1
                else:
                    logger.warning(
                        f"Failed to delete text at {location}: text not found")
                    failed_count += 1
            else:
                logger.warning(f"Unknown modification type: {mod_type}")
                failed_count += 1

        except Exception as e:
            logger.error(
                f"Error applying modification at {location}: {str(e)}")
            failed_count += 1

    logger.info(
        f"Diff applied: {applied_count} succeeded, {failed_count} failed")
    return modified_content


def _fuzzy_replace(content: str, location: str, original: str, new: str) -> str:
    """
    模糊匹配替换(基于location提示)

    Args:
        content: 完整内容
        location: 位置描述(如"第3段第2行")
        original: 原文
        new: 新内容

    Returns:
        替换后的内容
    """
    # 尝试从location提取段落号
    paragraph_match = re.search(r'第(\d+)段', location)
    if paragraph_match:
        paragraph_num = int(paragraph_match.group(1))
        paragraphs = content.split('\n\n')

        if 0 < paragraph_num <= len(paragraphs):
            target_para = paragraphs[paragraph_num - 1]
            if original in target_para:
                paragraphs[paragraph_num -
                           1] = target_para.replace(original, new, 1)
                return '\n\n'.join(paragraphs)

    # 尝试从location提取行号
    line_match = re.search(r'第(\d+)行', location)
    if line_match:
        line_num = int(line_match.group(1))
        lines = content.split('\n')

        if 0 < line_num <= len(lines):
            target_line = lines[line_num - 1]
            if original in target_line:
                lines[line_num - 1] = target_line.replace(original, new, 1)
                return '\n'.join(lines)

    # 降级策略:如果原文较短,尝试全局模糊匹配
    if len(original) < 50 and original in content:
        logger.warning(f"Using global fuzzy match for short text")
        return content.replace(original, new, 1)

    # 完全失败,返回原内容
    logger.error(f"Fuzzy replace failed for location: {location}")
    return content


def _insert_at_location(content: str, location: str, new_text: str) -> str:
    """
    在指定位置插入文本

    Args:
        content: 完整内容
        location: 位置描述(如"第3段后")
        new_text: 要插入的文本

    Returns:
        插入后的内容
    """
    # 尝试从location提取段落号
    paragraph_match = re.search(r'第(\d+)段', location)
    if paragraph_match:
        paragraph_num = int(paragraph_match.group(1))
        paragraphs = content.split('\n\n')

        # 检查是否是"段后"插入
        if '后' in location:
            if 0 < paragraph_num <= len(paragraphs):
                paragraphs.insert(paragraph_num, new_text)
                return '\n\n'.join(paragraphs)
        else:
            # 默认在段前插入
            if 0 < paragraph_num <= len(paragraphs):
                paragraphs.insert(paragraph_num - 1, new_text)
                return '\n\n'.join(paragraphs)

    # 尝试从location提取行号
    line_match = re.search(r'第(\d+)行', location)
    if line_match:
        line_num = int(line_match.group(1))
        lines = content.split('\n')

        if '后' in location:
            if 0 < line_num <= len(lines):
                lines.insert(line_num, new_text)
                return '\n'.join(lines)
        else:
            if 0 < line_num <= len(lines):
                lines.insert(line_num - 1, new_text)
                return '\n'.join(lines)

    # 降级策略:追加到末尾
    logger.warning(f"Insert at location failed: {location}, appending to end")
    return content + '\n\n' + new_text


def validate_diff_instructions(diff_instructions: Dict[str, Any]) -> bool:
    """
    验证差异指令格式

    Args:
        diff_instructions: LLM输出的差异指令JSON

    Returns:
        是否有效
    """
    if not isinstance(diff_instructions, dict):
        return False

    if "modifications" not in diff_instructions:
        return False

    modifications = diff_instructions["modifications"]
    if not isinstance(modifications, list):
        return False

    for mod in modifications:
        if not isinstance(mod, dict):
            return False
        if "type" not in mod or mod["type"] not in ["replace", "insert", "delete"]:
            return False
        if "location" not in mod:
            return False

    return True
