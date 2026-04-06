"""
提示词管理器包
管理各模块的提示词模板，支持智能变量填充

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import TYPE_CHECKING, Optional, Dict, Any, List

# 避免循环导入：仅在类型检查时导入
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models import PromptTemplate

# 导入无循环依赖的子模块
from app.agents.prompt_manager.config import MODULE_VARIABLES_CONFIG
from app.agents.prompt_manager.templates import DEFAULT_PROMPTS
from app.agents.prompt_manager.validation import validate_variables, build_prompt_context
from app.agents.prompt_manager.utils import extract_variables, get_all_modules
from app.agents.prompt_manager.cache import PromptCache, get_prompt_cache


class PromptManager:
    """提示词管理器"""

    def __init__(self):
        # 延迟导入避免循环依赖
        from app.core.config import get_settings
        self.settings = get_settings()

    async def get_prompt(
        self,
        db: "AsyncSession",
        module: str
    ) -> "PromptTemplate":
        """
        获取模块的激活提示词模板

        Args:
            db: 数据库会话
            module: 模块名称

        Returns:
            提示词模板
        """
        # 延迟导入
        from sqlalchemy import select
        from app.models import PromptTemplate
        
        # 尝试从数据库获取激活的模板
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.module == module)
            .where(PromptTemplate.is_active == True)
            .order_by(PromptTemplate.updated_at.desc())
            .limit(1)
        )
        template = result.scalar_one_or_none()

        if template:
            return template

        # 如果数据库中没有，返回默认模板
        return self.get_default_prompt(module)

    def get_default_prompt(self, module: str) -> "PromptTemplate":
        """
        获取默认提示词模板

        Args:
            module: 模块名称

        Returns:
            提示词模板
        """
        # 延迟导入
        from app.models import PromptTemplate
        
        default = DEFAULT_PROMPTS.get(module, {})

        return PromptTemplate(
            module=module,
            name=default.get("name", f"{module} 生成器"),
            description=default.get("description", ""),
            content=default.get("content", ""),
            variables=str(default.get("variables", []))
        )

    def render_prompt(
        self,
        template: "PromptTemplate",
        variables: Dict[str, Any],
        module: str = None
    ) -> str:
        """
        渲染提示词模板（智能变量填充）

        未提供的变量将自动使用默认值

        Args:
            template: 提示词模板
            variables: 变量字典（用户输入）
            module: 模块名称（用于获取变量配置）

        Returns:
            渲染后的提示词
        """
        import json
        
        # 延迟导入
        from app.core.logger import get_logger
        
        logger = get_logger("prompt_manager")
        content = template.content

        # 获取模块变量配置
        module_config = MODULE_VARIABLES_CONFIG.get(module, {})
        var_configs = module_config.get("variables", {})

        # 从模板中提取所有变量
        template_vars = extract_variables(content)

        # 构建完整的变量字典（用户值 + 默认值）
        filled_vars = {}
        for var_name in template_vars:
            # 1. 优先使用用户提供的值
            if var_name in variables and variables[var_name] is not None and variables[var_name] != "":
                filled_vars[var_name] = variables[var_name]
            # 2. 尝试从前端字段映射
            elif var_name in var_configs:
                front_field = var_configs[var_name].get("front_field")
                if front_field and front_field in variables and variables[front_field]:
                    filled_vars[var_name] = variables[front_field]
                else:
                    # 3. 使用默认值
                    filled_vars[var_name] = var_configs[var_name].get(
                        "default", "未指定")
            # 4. 使用通用默认值
            else:
                filled_vars[var_name] = "未指定"

        # 特殊处理：custom_outline 变量
        if "custom_outline" in filled_vars:
            outline_value = filled_vars["custom_outline"]
            if not outline_value or outline_value.strip() == "":
                filled_vars["custom_outline"] = "（未提供自写大纲）"
            elif outline_value.startswith("http") or outline_value.startswith("/api"):
                filled_vars["custom_outline"] = f"（文件解析失败，原URL: {outline_value[:50]}...）"
                logger.warning(
                    f"custom_outline 文件解析可能失败，值仍为URL: {outline_value[:100]}")

        # 特殊处理：description 变量
        if "description" in filled_vars:
            desc_value = filled_vars["description"]
            if not desc_value or desc_value.strip() == "" or desc_value == "未指定" or desc_value == "null":
                filled_vars["description"] = "（用户未提供详细描述，请根据上述补充参数自主发挥创意，设计出符合品牌调性和广告目的的方案）"
                logger.info("description 为空，已设置默认提示")

        # 特殊处理：reference_materials 变量
        if "reference_materials" in filled_vars:
            ref_value = filled_vars["reference_materials"]
            if not ref_value or ref_value.strip() == "":
                filled_vars["reference_materials"] = "（未提供参考资料）"
            elif ref_value.startswith("http") or ref_value.startswith("/api"):
                filled_vars["reference_materials"] = f"（文件解析失败，原URL: {ref_value[:50]}...）"
                logger.warning(
                    f"reference_materials 文件解析可能失败，值仍为URL: {ref_value[:100]}")

        # 特殊处理：unit_label 和 unit_unit 变量
        if "unit_label" in template_vars or "unit_unit" in template_vars:
            series_type = filled_vars.get("series_type", "")
            movie_types = ["院线电影", "网络电影", "微电影", "纪录片", "动画电影"]
            if series_type in movie_types:
                filled_vars["unit_label"] = "场景"
                filled_vars["unit_unit"] = "场"
            else:
                filled_vars["unit_label"] = "分集"
                filled_vars["unit_unit"] = "集"

        # 替换变量
        for key, value in filled_vars.items():
            placeholder = f"{{{key}}}"
            if value is None:
                display_value = "未指定"
            elif isinstance(value, (list, dict)):
                display_value = json.dumps(value, ensure_ascii=False)
            else:
                display_value = str(value)
            content = content.replace(placeholder, display_value)

            if key == "ai_platforms":
                logger.info(
                    f"AI平台变量填充 - 原始值: {value!r}, 显示值: {display_value!r}")

        logger.info(f"提示词变量填充完成 - 模块: {module}, 变量数: {len(filled_vars)}")
        return content

    def _extract_variables(self, content: str) -> List[str]:
        """从模板内容中提取变量名（兼容旧接口）"""
        return extract_variables(content)

    def get_module_variables(self, module: str) -> Dict[str, Any]:
        """获取模块的变量配置"""
        return MODULE_VARIABLES_CONFIG.get(module, {})

    def validate_variables(
        self,
        module: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证变量是否满足模块要求"""
        return validate_variables(module, variables)

    def build_prompt_context(
        self,
        module: str,
        user_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建提示词上下文（用于调试和预览）"""
        return build_prompt_context(module, user_input)

    async def create_or_update_prompt(
        self,
        db: "AsyncSession",
        module: str,
        name: str,
        content: str,
        description: Optional[str] = None,
        variables: Optional[List[str]] = None,
        is_active: bool = True
    ) -> "PromptTemplate":
        """创建或更新提示词模板"""
        import json
        
        # 延迟导入
        from sqlalchemy import select
        from app.models import PromptTemplate

        # 将之前的激活模板设为非激活
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.module == module)
            .where(PromptTemplate.is_active == True)
        )
        old_templates = result.scalars().all()

        for old_template in old_templates:
            old_template.is_active = False

        # 创建新模板
        new_template = PromptTemplate(
            module=module,
            name=name,
            content=content,
            description=description,
            variables=json.dumps(
                variables, ensure_ascii=False) if variables else None,
            is_active=is_active
        )

        db.add(new_template)
        await db.commit()
        await db.refresh(new_template)

        return new_template

    def get_all_modules(self) -> List[str]:
        """获取所有支持的模块"""
        return get_all_modules()


# 全局提示词管理器实例
prompt_manager = PromptManager()


def get_prompt_manager() -> PromptManager:
    """获取提示词管理器实例"""
    return prompt_manager


# 导出公共接口
__all__ = [
    # 核心类和实例
    "PromptManager",
    "prompt_manager",
    "get_prompt_manager",
    # 配置
    "MODULE_VARIABLES_CONFIG",
    # 模板
    "DEFAULT_PROMPTS",
    # 验证
    "validate_variables",
    "build_prompt_context",
    # 工具函数
    "extract_variables",
    "get_all_modules",
    # 缓存
    "PromptCache",
    "get_prompt_cache",
]
