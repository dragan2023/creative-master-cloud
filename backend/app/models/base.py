"""
数据库模型基类
提供通用字段和方法
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declared_attr
from app.core.database import Base


# 获取中国时区的本地时间 (UTC+8)
def get_local_now():
    """获取本地时间（中国时区 UTC+8）"""
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)


class TimestampMixin:
    """时间戳混入类"""

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=get_local_now, nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(DateTime, default=get_local_now, onupdate=get_local_now, nullable=False)


class BaseModel(Base, TimestampMixin):
    """模型基类"""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    def to_dict(self, exclude: list = None) -> dict:
        """
        转换为字典

        Args:
            exclude: 排除的字段列表

        Returns:
            字典表示
        """
        exclude = exclude or []
        result = {}
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[column.name] = value
        return result
