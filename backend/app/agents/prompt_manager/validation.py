"""
提示词参数验证模块
包含变量验证和上下文构建逻辑

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any

from app.agents.prompt_manager.config import MODULE_VARIABLES_CONFIG


def validate_variables(
    module: str,
    variables: Dict[str, Any]
) -> Dict[str, Any]:
    """
    验证变量是否满足模块要求

    Args:
        module: 模块名称
        variables: 变量字典

    Returns:
        验证结果 {"valid": bool, "missing": list, "errors": list}
    """
    module_config = MODULE_VARIABLES_CONFIG.get(module, {})
    var_configs = module_config.get("variables", {})

    missing = []
    errors = []

    for var_name, var_config in var_configs.items():
        if var_config.get("required", False):
            # 检查必需变量
            front_field = var_config.get("front_field", var_name)
            if var_name not in variables and front_field not in variables:
                missing.append(var_name)
            elif not variables.get(var_name) and not variables.get(front_field):
                missing.append(var_name)

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "errors": errors
    }


def build_prompt_context(
    module: str,
    user_input: Dict[str, Any]
) -> Dict[str, Any]:
    """
    构建提示词上下文（用于调试和预览）

    显示每个变量的实际值和来源

    Args:
        module: 模块名称
        user_input: 用户输入

    Returns:
        上下文字典
    """
    module_config = MODULE_VARIABLES_CONFIG.get(module, {})
    var_configs = module_config.get("variables", {})

    context = {
        "module": module,
        "variables": {}
    }

    for var_name, var_config in var_configs.items():
        var_info = {
            "description": var_config.get("description", ""),
            "required": var_config.get("required", False),
            "default": var_config.get("default"),
            "actual_value": None,
            "source": "default"
        }

        # 确定实际值和来源
        if var_name in user_input and user_input[var_name]:
            var_info["actual_value"] = user_input[var_name]
            var_info["source"] = "user_input"
        elif "front_field" in var_config:
            front_field = var_config["front_field"]
            if front_field in user_input and user_input[front_field]:
                var_info["actual_value"] = user_input[front_field]
                var_info["source"] = "mapped"

        if var_info["actual_value"] is None:
            var_info["actual_value"] = var_config.get("default")

        context["variables"][var_name] = var_info

    return context
