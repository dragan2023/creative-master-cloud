"""
日志配置模块
使用 Loguru 实现日志记录，支持多级别、自动轮转、多进程安全
"""
import sys
import os
from loguru import logger
from typing import Optional

# 移除默认处理器
logger.remove()

# 定义日志格式
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[user_id]: <12}</cyan> | "
    "<level>{message}</level>"
)

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "{level: <8} | "
    "{extra[user_id]: <12} | "
    "{message}"
)

# 默认 user_id
DEFAULT_USER_ID = "system".ljust(12)


def setup_logger(log_dir: str, log_level: str = "INFO") -> None:
    """
    配置日志系统
    
    Args:
        log_dir: 日志文件存储目录
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    # 确保日志目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 控制台输出 (开发调试)
    logger.add(
        sys.stdout,
        format=CONSOLE_FORMAT,
        level=log_level,
        colorize=True,
        filter=lambda record: record["extra"].setdefault("user_id", DEFAULT_USER_ID) or True
    )
    
    # 文件输出 (生产记录)
    logger.add(
        os.path.join(log_dir, "app_{time:YYYY-MM-DD}.log"),
        rotation="00:00",       # 每天轮转
        retention="30 days",    # 保留30天
        compression="zip",      # 自动压缩
        level="INFO",
        enqueue=True,           # 多进程安全
        format=FILE_FORMAT,
        encoding="utf-8",
        filter=lambda record: record["extra"].setdefault("user_id", DEFAULT_USER_ID) or True
    )
    
    # 错误日志单独记录
    logger.add(
        os.path.join(log_dir, "error_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention="30 days",
        compression="zip",
        level="ERROR",
        enqueue=True,
        format=FILE_FORMAT,
        encoding="utf-8",
        filter=lambda record: record["extra"].setdefault("user_id", DEFAULT_USER_ID) or True
    )
    
    # Agent 调试日志 (仅 DEBUG 模式)
    logger.add(
        os.path.join(log_dir, "agent_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention="7 days",     # Agent日志保留7天
        compression="zip",
        level="DEBUG",
        enqueue=True,
        format=FILE_FORMAT,
        encoding="utf-8",
        filter=lambda record: record["extra"].setdefault("user_id", DEFAULT_USER_ID) or (record["extra"].get("agent", False) or False)
    )


def get_logger(user_id: str = "system", agent: bool = False) -> logger.__class__:
    """
    获取绑定用户ID的日志实例
    
    Args:
        user_id: 用户ID，用于日志追踪
        agent: 是否为 Agent 调试日志
    
    Returns:
        绑定了上下文信息的 logger 实例
    """
    return logger.bind(user_id=user_id, agent=agent)


def mask_sensitive(text: str, sensitive_keys: list = None) -> str:
    """
    脱敏处理敏感信息
    
    Args:
        text: 原始文本
        sensitive_keys: 需要脱敏的关键词列表
    
    Returns:
        脱敏后的文本
    """
    if sensitive_keys is None:
        sensitive_keys = ["api_key", "API_KEY", "password", "secret", "token"]
    
    import re
    for key in sensitive_keys:
        # 匹配 key=value 或 key: value 格式
        pattern = rf'({key}\s*[:=]\s*)[^\s,}}\]]+'
        text = re.sub(pattern, r'\1***', text, flags=re.IGNORECASE)
    
    return text


class LoggerAdapter:
    """
    日志适配器类，提供更便捷的日志记录方法
    """
    
    def __init__(self, user_id: str = "system"):
        self.user_id = user_id
        self._logger = get_logger(user_id)
    
    def info(self, message: str, **kwargs) -> None:
        """记录 INFO 级别日志"""
        self._logger.info(message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """记录 DEBUG 级别日志"""
        self._logger.debug(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """记录 WARNING 级别日志"""
        self._logger.warning(message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """记录 ERROR 级别日志"""
        if exc_info:
            self._logger.exception(message, **kwargs)
        else:
            self._logger.error(message, **kwargs)
    
    def agent_log(self, message: str, level: str = "DEBUG") -> None:
        """记录 Agent 调试日志"""
        agent_logger = get_logger(self.user_id, agent=True)
        getattr(agent_logger, level.lower())(message)


# 初始化标记
_initialized = False


def init_logging() -> None:
    """初始化日志系统"""
    global _initialized
    if _initialized:
        return
    
    from app.core.config import get_settings
    settings = get_settings()
    setup_logger(settings.get_log_dir(), settings.LOG_LEVEL)
    _initialized = True
    
    logger.info(f"日志系统初始化完成 - 日志目录: {settings.get_log_dir()}")
