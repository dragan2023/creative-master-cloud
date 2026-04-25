"""
monitoring/ 包 - 监控与错误处理模块

将原 monitoring_compat.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: 统一导出 MonitoringMixin, GraphCache, ExtendedContextAccumulator
    _graph_cache.py: GraphCache 知识图谱缓存管理器
    _context_accumulator.py: ExtendedContextAccumulator 扩展上下文累积器
    _base.py: 中断检测与处理 (_check_interrupted, interrupt, get_character_tracker)
    _ws.py: WebSocket消息推送 (_send_ws_message)
    _checkpoint.py: 检查点管理 (_load_checkpoint, _save_checkpoint)
    _character_tracker.py: 人物状态追踪 (_initialize_character_tracker, _update_character_states, _sync_extraction_to_tracker)
    _knowledge_graph.py: 知识图谱方法 (_sync_extended_states_to_knowledge_graph, _get_extended_context_info, _get_llm_provider_for_extraction)

@date: 2026-04-24
@version: v3.0.0
"""
from ._graph_cache import GraphCache
from ._context_accumulator import ExtendedContextAccumulator
from ._base import MonitoringBaseMixin
from ._ws import MonitoringWSMixin
from ._checkpoint import MonitoringCheckpointMixin
from ._character_tracker import MonitoringCharacterMixin
from ._knowledge_graph import MonitoringKnowledgeGraphMixin


class MonitoringMixin(
    MonitoringBaseMixin,
    MonitoringWSMixin,
    MonitoringCheckpointMixin,
    MonitoringCharacterMixin,
    MonitoringKnowledgeGraphMixin,
):
    """监控与错误处理 Mixin

    提供：
    - 中断检测与处理
    - WebSocket消息推送
    - 检查点保存与加载
    - 人物状态追踪初始化与更新
    - 图谱缓存与上下文累积
    """
    pass


__all__ = [
    "MonitoringMixin",
    "GraphCache",
    "ExtendedContextAccumulator",
]
