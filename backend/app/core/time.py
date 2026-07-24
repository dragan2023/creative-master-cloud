"""
统一时间入口 — 项目唯一的 UTC 时间获取方式。

使用方式：
    from app.core.time import utc_now
    now = utc_now()

禁止直接调用 datetime.utcnow()，该 API 已在 Python 3.12+ / Pydantic V2 中弃用。
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """返回当前 UTC 时间的时区感知 datetime 对象。

    替代已弃用的 datetime.utcnow()（返回 naive datetime）。
    返回值携带 timezone.utc，可安全用于数据库 timezone-aware 列和比较操作。
    """
    return datetime.now(timezone.utc)
