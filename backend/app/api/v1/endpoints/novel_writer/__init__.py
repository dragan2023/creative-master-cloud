"""
小说/剧本正文生成 API 端点包

统一路由挂载，保持API路径与原单文件一致

架构说明：
- utils.py 定义主 router 和共享工具函数
- 各子模块（projects, outlines, chapters, knowledge_base, style_document, content）
  从 utils 导入 router 并直接在其上注册端点
- 此 __init__.py 导入所有子模块以触发端点注册，然后导出 router

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
# 从 utils 导入主 router（所有子模块共享此 router）
from .utils import (
    router,  # 主路由器，已设置 prefix="/novel-writer"
    generate_project_code,
    get_project_data_dir,
    _build_project_response,
    extract_chapter_count,
    parse_unit_summaries_from_content,
    is_cancelled,
    set_cancel_token,
    get_cancel_token,
    clear_cancel_token
)

# 导入子模块以触发端点注册（它们会在 utils.router 上注册端点）
# 注意：必须导入所有子模块，否则对应的端点不会被注册
from . import projects      # 项目管理端点
from . import outlines      # 大纲管理端点
from . import chapters      # 章节管理端点
from . import knowledge_base  # 知识库端点
from . import style_document  # 风格文档端点
from . import content       # 内容管理端点
from . import quality_control  # 质量管控端点(旧版)
from . import quality_control_v2  # 质量管控端点v2.0(LLM智能修正+反馈学习)
from . import _unit_content  # 单元内容编辑端点

# 从 task_manager 直接导出
from app.services.task_manager import (
    set_memory_cancel_token,
    clear_memory_cancel_token,
    trigger_memory_cancel,
    is_memory_cancelled
)

# 导出公共接口
__all__ = [
    "router",
    # 工具函数
    "generate_project_code",
    "get_project_data_dir",
    "_build_project_response",
    "extract_chapter_count",
    "parse_unit_summaries_from_content",
    # 取消令牌相关
    "is_cancelled",
    "set_cancel_token",
    "get_cancel_token",
    "clear_cancel_token",
    "set_memory_cancel_token",
    "clear_memory_cancel_token",
    "trigger_memory_cancel",
    "is_memory_cancelled",
]
