"""
通用类型适配器

为提示词构建等上下游模块提供安全的数据类型转换能力。
支持 JSON 字符串解析、非 dict/list 值降级包装，确保下游 .get() 调用永不崩溃。

@date: 2026-05-22
@version: v1.0.0
"""

import json
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger

logger = get_logger("type_adapter")


def safe_json_dict(value: Any, key_name: str = "unknown") -> Dict[str, Any]:
    """将任意值安全转换为 dict。

    转换策略（按优先级）：
    1. 已是 dict → 原样返回
    2. JSON 字符串 → 解析后返回（仅当解析结果为 dict 时）
    3. 其他非空字符串 → 包装为 {"_raw_text": value}，记录 WARNING
    4. None / 空 → 返回 {}

    Args:
        value: 待转换的值
        key_name: 用于日志定位的字段名

    Returns:
        安全的 dict，保证 .get() 不会崩溃
    """
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        # 尝试 JSON 解析
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                logger.info(
                    f"[safe_json_dict] {key_name} 从 JSON 字符串成功解析为 dict"
                )
                return parsed
            # JSON 解析成功但不是 dict（如 list/number）
            logger.warning(
                f"[safe_json_dict] {key_name} JSON 解析结果不是 dict (type={type(parsed).__name__})，降级包装"
            )
            return {"_raw_json": stripped}
        except (json.JSONDecodeError, TypeError):
            pass
        # 非 JSON 字符串：降级包装
        logger.warning(
            f"[safe_json_dict] {key_name} 是非 JSON 字符串，已降级包装为 '_raw_text' (len={len(stripped)})"
        )
        return {"_raw_text": stripped}

    if value is None:
        return {}

    # 其他类型（int, float, list 等）
    logger.warning(
        f"[safe_json_dict] {key_name} 类型异常: {type(value).__name__}，返回空字典"
    )
    return {}


def safe_json_list(value: Any, key_name: str = "unknown") -> List[Any]:
    """将任意值安全转换为 list。

    转换策略（按优先级）：
    1. 已是 list → 原样返回
    2. JSON 数组字符串 → 解析后返回
    3. dict → 包装为单元素列表 [value]
    4. 其他非空值 → 包装为单元素列表 [value]
    5. None / 空字符串 → 返回 []

    Args:
        value: 待转换的值
        key_name: 用于日志定位的字段名

    Returns:
        安全的 list
    """
    if isinstance(value, list):
        return value

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        # 尝试 JSON 解析
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                logger.info(
                    f"[safe_json_list] {key_name} 从 JSON 字符串成功解析为 list"
                )
                return parsed
            # JSON 解析成功但不是 list
            logger.warning(
                f"[safe_json_list] {key_name} JSON 解析结果不是 list (type={type(parsed).__name__})，降级包装"
            )
            return [parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        # 非 JSON 字符串：包装为单元素列表
        logger.warning(
            f"[safe_json_list] {key_name} 是非 JSON 字符串，已降级包装为单元素列表 (len={len(stripped)})"
        )
        return [stripped]

    if value is None:
        return []

    # dict 或 其他类型：包装为单元素列表
    logger.warning(
        f"[safe_json_list] {key_name} 类型异常: {type(value).__name__}，已包装为单元素列表"
    )
    return [value]
