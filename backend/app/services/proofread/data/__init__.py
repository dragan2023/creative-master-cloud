"""
内置数据模块
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
