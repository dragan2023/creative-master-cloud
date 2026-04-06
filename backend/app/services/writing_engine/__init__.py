"""
多Agent协作文学作品生成系统 - 写作引擎服务层

模块: services.writing_engine
文件: __init__.py
功能: 写作引擎模块入口，导出核心服务类

依赖关系:
    - 依赖: task_manager.py, pipeline.py, websocket_manager.py
    - 被依赖: API层、外部调用者

使用说明:
    from app.services.writing_engine import TaskManager, WritingPipeline, WebSocketManager

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.services.writing_engine.task_manager import TaskManager
from app.services.writing_engine.pipeline import WritingPipeline
from app.services.writing_engine.websocket_manager import WebSocketManager

__all__ = [
    "TaskManager",
    "WritingPipeline",
    "WebSocketManager",
]
