"""
时间工具模块

背景:
    Python 3.12 起 `datetime.utcnow()` 被标记为弃用（DeprecationWarning）。
    本项目数据库列均为 naive datetime（无时区），直接切换到
    `datetime.now(timezone.utc)` 会产生 aware/naive 比较崩溃。

统一约定:
    所有需要"当前 UTC 时间"的业务代码一律调用 `utc_now_naive()`，
    语义与旧 `datetime.utcnow()` 完全一致（naive UTC），但不触发弃用警告。
"""
from datetime import datetime
from datetime import timezone


def utc_now_naive() -> datetime:
    """返回当前 UTC 时间（naive, 与数据库 naive datetime 列直接可比较）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
