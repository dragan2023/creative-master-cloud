"""
简洁高效的JSON解析工具

处理LLM返回的JSON响应中常见的问题：
- 带有markdown代码块标记的响应
- 包含控制字符的内容
- 截断的JSON对象

设计原则：
1. 优先使用标准json.loads()直接解析
2. 不做中文标点预处理（中文引号、顿号等是合法Unicode字符）
3. 只处理真正需要修复的格式问题

@date: 2026-04-02
@version: v2.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from app.core.logger import get_logger

# 尝试导入 json-repair 作为终极回退
try:
    from json_repair import repair_json
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False


logger = get_logger("json_parser")


class RobustJSONParser:
    """简洁高效的JSON解析器
    
    核心原则：先尝试直接解析，只在必要时才做最小化处理
    """
    
    # 需要清理的控制字符（除了JSON允许的空白符）
    CONTROL_CHARS_TO_REMOVE = [
        '\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
        '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12',
        '\x13', '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a',
        '\x1b', '\x1c', '\x1d', '\x1e', '\x1f'
    ]
    
    @classmethod
    def parse(
        cls,
        content: str,
        default: Any = None,
        repair_truncated: bool = True
    ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """解析LLM返回的JSON响应
        
        Args:
            content: LLM返回的原始内容
            default: 解析失败时的默认返回值
            repair_truncated: 是否尝试修复截断的JSON
            
        Returns:
            Tuple[解析结果, 处理过程日志列表]
        """
        logs = []
        
        if not content:
            logs.append("输入内容为空")
            return default, logs
        
        if not isinstance(content, str):
            try:
                content = str(content)
                logs.append(f"内容类型转换: {type(content).__name__} -> str")
            except Exception as e:
                logs.append(f"内容转换失败: {e}")
                return default, logs
        
        # Step 1: 直接解析原始内容（最重要！）
        result = cls._try_direct_parse(content.strip())
        if result is not None:
            logs.append("直接解析成功")
            return result, logs
        
        # Step 2: 从markdown代码块提取
        result, extract_logs = cls._try_extract_from_markdown(content)
        if result is not None:
            logs.extend(extract_logs)
            return result, logs
        
        # Step 3: 查找JSON边界
        result, boundary_logs = cls._try_find_json_boundary(content)
        if result is not None:
            logs.extend(boundary_logs)
            return result, logs
        
        # Step 4: 清理控制字符后重试
        cleaned = cls._clean_control_characters(content)
        if cleaned != content:
            result = cls._try_direct_parse(cleaned.strip())
            if result is not None:
                logs.append("清理控制字符后解析成功")
                return result, logs
        
        # Step 5: 尝试修复截断的JSON
        if repair_truncated:
            result, repair_logs = cls._try_repair_truncated(cleaned)
            if result is not None:
                logs.extend(repair_logs)
                return result, logs
                
        # Step 6: 使用 json-repair 作为终极回退
        if HAS_JSON_REPAIR:
            result, repair_logs = cls._try_json_repair(content)
            if result is not None:
                logs.extend(repair_logs)
                return result, logs
        
        logs.append("所有解析方法均失败")
        return default, logs
    
    @classmethod
    def parse_or_default(cls, content: str, default: Any = None) -> Any:
        """解析JSON，失败时返回默认值
        
        Args:
            content: LLM返回的原始内容
            default: 解析失败时的默认返回值
            
        Returns:
            解析结果或默认值
        """
        result, _ = cls.parse(content, default=default)
        return result
    
    @classmethod
    def _try_direct_parse(cls, content: str) -> Optional[Dict[str, Any]]:
        """尝试直接解析JSON
        
        Args:
            content: 内容字符串
            
        Returns:
            解析结果或None
        """
        try:
            result = json.loads(content)
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                return {"_items": result}
            return None
        except (json.JSONDecodeError, ValueError):
            return None
    
    @classmethod
    def _try_extract_from_markdown(cls, content: str) -> Tuple[Optional[Dict], List[str]]:
        """从markdown代码块中提取JSON
        
        Args:
            content: 原始内容
            
        Returns:
            Tuple[解析结果, 处理日志]
        """
        logs = []
        
        # 匹配 ```json ... ``` 或 ``` ... ```
        patterns = [
            r'```json\s*\n(.*?)\n```',
            r'```\s*\n(.*?)\n```',
            r'```json\s*(.*?)```',
            r'```(.*?)```',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                json_str = match.strip()
                result = cls._try_direct_parse(json_str)
                if result is not None:
                    logs.append("从markdown代码块提取成功")
                    return result, logs
        
        return None, logs
    
    @classmethod
    def _try_find_json_boundary(cls, content: str) -> Tuple[Optional[Dict], List[str]]:
        """查找JSON对象边界并提取
        
        Args:
            content: 原始内容
            
        Returns:
            Tuple[解析结果, 处理日志]
        """
        logs = []
        
        # 查找第一个 { 和最后一个 }
        start = content.find('{')
        end = content.rfind('}')
        
        if start == -1 or end == -1 or end <= start:
            # 尝试查找数组
            start = content.find('[')
            end = content.rfind(']')
            if start == -1 or end == -1 or end <= start:
                return None, logs
        
        json_str = content[start:end + 1]
        result = cls._try_direct_parse(json_str)
        if result is not None:
            logs.append("查找JSON边界提取成功")
            return result, logs
        
        # 尝试清理JSON字符串
        cleaned = cls._clean_json_string(json_str)
        result = cls._try_direct_parse(cleaned)
        if result is not None:
            logs.append("清理JSON字符串后提取成功")
            return result, logs
        
        return None, logs
    
    @classmethod
    def _clean_control_characters(cls, content: str) -> str:
        """清理非法控制字符
        
        Args:
            content: 原始内容
            
        Returns:
            清理后的内容
        """
        cleaned = content
        for char in cls.CONTROL_CHARS_TO_REMOVE:
            if char in cleaned:
                cleaned = cleaned.replace(char, '')
        return cleaned
    
    @classmethod
    def _clean_json_string(cls, json_str: str) -> str:
        """清理JSON字符串中的常见问题
        
        处理：
        - JavaScript风格注释
        - 尾随逗号
        - 中文标点替换（中文引号、中文顿号、中文逗号、中文冒号）
        
        Args:
            json_str: JSON字符串
            
        Returns:
            清理后的JSON
        """
        cleaned = json_str
        
        # 移除JavaScript风格的注释
        cleaned = re.sub(r'//.*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        
        # 中文标点替换为英文标点（仅在JSON结构上下文中）
        # 注意：这里要小心处理，避免替换字符串值内部的中文标点
        # 中文引号 -> 英文引号（在JSON字符串边界）
        cleaned = cleaned.replace('“', '"').replace('”', '"')
        # 中文单引号 -> 英文双引号
        cleaned = cleaned.replace('‘', "'").replace('’', "'")
        # 特殊处理：中文顿号作为数组元素分隔符
        # LLM 可能返回 ["a"、"b"、"c"] 这种格式，需要修复为 ["a","b","c"]
        # 在数组中，中文顿号后通常跟着中文引号或英文引号
        # 正则匹配：中文顿号 + (可选空格) + (中文引号或英文引号)
        cleaned = re.sub(r'、(\s*)([\"\'\""])', r',\1\2', cleaned)
        # 中文逗号 -> 英文逗号
        cleaned = cleaned.replace('，', ',')
        # 中文冒号 -> 英文冒号
        cleaned = cleaned.replace('：', ':')
        
        # 移除尾随逗号
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        
        return cleaned
    
    @classmethod
    def _try_repair_truncated(cls, content: str) -> Tuple[Optional[Dict], List[str]]:
        """尝试修复截断的JSON
        
        Args:
            content: JSON字符串
            
        Returns:
            Tuple[修复后的结果, 处理日志]
        """
        logs = []
        
        # 查找第一个 {
        start = content.find('{')
        if start == -1:
            return None, logs
        
        json_str = content[start:]
        
        # 统计括号嵌套
        depth = 0
        in_string = False
        escape_next = False
        last_complete_pos = -1
        stack = []  # 记录括号类型
        
        for i, char in enumerate(json_str):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\' and in_string:
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    depth += 1
                    stack.append('{')
                elif char == '[':
                    depth += 1
                    stack.append('[')
                elif char == '}':
                    if stack and stack[-1] == '{':
                        stack.pop()
                        depth -= 1
                        if depth == 0:
                            last_complete_pos = i
                elif char == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()
                        depth -= 1
        
        # 如果找到完整对象
        if last_complete_pos > 0:
            complete_json = json_str[:last_complete_pos + 1]
            result = cls._try_direct_parse(complete_json)
            if result is not None:
                logs.append("提取完整JSON对象成功")
                return result, logs
        
        # 尝试手动闭合
        if depth > 0:
            repaired = json_str.rstrip()
            
            # 移除不完整的尾部
            while repaired and repaired[-1] not in '}]':
                repaired = repaired[:-1]
            
            # 添加缺失的闭合括号
            for bracket_type in reversed(stack):
                if bracket_type == '{':
                    repaired += '}'
                else:
                    repaired += ']'
            
            result = cls._try_direct_parse(repaired)
            if result is not None:
                logs.append(f"手动闭合JSON成功（添加{len(stack)}个闭合括号）")
                return result, logs
        
        logs.append("无法修复截断的JSON")
        return None, logs

    @classmethod
    def _try_json_repair(cls, content: str) -> Tuple[Optional[Dict], List[str]]:
        """使用 json-repair 库尝试修复 JSON
        
        json-repair 是专门处理 LLM 返回异常 JSON 的库，
        可以处理中文顿号分隔、中文引号等问题。
        
        Args:
            content: 原始内容
            
        Returns:
            Tuple[解析结果, 处理日志]
        """
        logs = []
        
        if not HAS_JSON_REPAIR:
            return None, logs
        
        try:
            # json-repair 可以处理各种异常情况
            # 包括中文顿号作为数组分隔符、中文引号等
            result = repair_json(content)
            
            if result is not None:
                # repair_json 可能返回字符串，需要再次解析
                if isinstance(result, str):
                    # 如果返回的是字符串，尝试解析
                    parsed = json.loads(result)
                    logs.append("json-repair 修复成功")
                    return parsed, logs
                elif isinstance(result, dict):
                    logs.append("json-repair 修复成功")
                    return result, logs
                elif isinstance(result, list):
                    logs.append("json-repair 修复成功")
                    return {"_items": result}, logs
        except Exception as e:
            logs.append(f"json-repair 修复失败: {str(e)[:50]}")
            
        return None, logs


def parse_json(
    content: str,
    default: Any = None,
    repair_truncated: bool = True
) -> Any:
    """解析LLM返回的JSON响应的便捷函数
    
    Args:
        content: LLM返回的原始内容
        default: 解析失败时的默认返回值
        repair_truncated: 是否尝试修复截断的JSON
        
    Returns:
        解析结果或默认值
    """
    result, logs = RobustJSONParser.parse(
        content,
        default=default,
        repair_truncated=repair_truncated
    )
    
    # 记录处理日志
    if logs:
        logger.debug(f"JSON解析日志: {'; '.join(logs)}")
    
    return result


def parse_json_with_validation(
    content: str,
    required_fields: List[str] = None,
    default: Any = None
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """解析JSON并验证必需字段
    
    Args:
        content: LLM返回的原始内容
        required_fields: 必需字段列表
        default: 解析失败时的默认返回值
        
    Returns:
        Tuple[解析结果, 缺失字段列表]
    """
    result = parse_json(content, default=default)
    
    if result is None:
        return None, required_fields or []
    
    if required_fields is None:
        return result, []
    
    missing_fields = [f for f in required_fields if f not in result]
    
    return result, missing_fields
