"""
内置数据模块

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.services.proofread.data.built_in_entities import (
    CHINA_LOCATIONS,
    CHINA_CELEBRITIES,
    CHINA_HISTORICAL_EVENTS,
    SENSITIVE_WORDS,
    get_all_locations,
    get_all_celebrities,
    get_all_historical_events,
    get_entity_data
)

__all__ = [
    "CHINA_LOCATIONS",
    "CHINA_CELEBRITIES",
    "CHINA_HISTORICAL_EVENTS",
    "SENSITIVE_WORDS",
    "get_all_locations",
    "get_all_celebrities",
    "get_all_historical_events",
    "get_entity_data",
]
