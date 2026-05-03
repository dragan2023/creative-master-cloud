"""全维度日志收集器"""
from .backend_logger import BackendLogger
from .frontend_logger import FrontendLogger
from .console_logger import ConsoleLogger
from .behavior_logger import BehaviorLogger

__all__ = ['BackendLogger', 'FrontendLogger', 'ConsoleLogger', 'BehaviorLogger']
