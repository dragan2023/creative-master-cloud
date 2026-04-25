"""
上下文窗口管理器 - 兼容导入

提供知识库集成模块的兼容导入（可选，用于兼容旧代码）。

@date: 2026-04-24
@version: v3.1.0 (从context_manager.py拆分)
"""

# 知识库集成模块（可选，用于兼容旧代码）
# TODO: 迁移到新的Writing Task系统后移除
try:
    from app.services.novel_writer.knowledge_integration import NovelKnowledgeIntegration
    _HAS_KNOWLEDGE_INTEGRATION = True
except ImportError:
    NovelKnowledgeIntegration = None
    _HAS_KNOWLEDGE_INTEGRATION = False
