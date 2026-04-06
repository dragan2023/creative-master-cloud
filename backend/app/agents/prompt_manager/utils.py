"""
提示词管理器辅助函数模块
包含变量提取、模块列表等辅助函数

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import re
from typing import List

from app.agents.prompt_manager.templates import DEFAULT_PROMPTS


def extract_variables(content: str) -> List[str]:
    """
    从模板内容中提取变量名

    Args:
        content: 模板内容

    Returns:
        变量名列表
    """
    # 匹配 {variable_name} 格式的变量
    pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
    variables = list(set(re.findall(pattern, content)))
    return variables


def get_all_modules() -> List[str]:
    """获取所有支持的模块"""
    return list(DEFAULT_PROMPTS.keys())
