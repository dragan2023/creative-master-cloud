"""
策略工厂 - 根据内容类型获取对应的上下文构建策略

@date: 2026-04-19
@version: v1.0.0
"""
from app.services.novel_writer.strategies.base import ContextBuildStrategy
from app.services.novel_writer.strategies.novel import NovelStrategy
from app.services.novel_writer.strategies.series_script import SeriesScriptStrategy
from app.services.novel_writer.strategies.movie_script import MovieScriptStrategy


def get_strategy(content_type: str) -> ContextBuildStrategy:
    """根据内容类型获取对应的上下文构建策略

    Args:
        content_type: 内容类型标识符
            - "novel": 小说
            - "series_script" / "script": 剧集剧本
            - "movie_script": 电影剧本

    Returns:
        对应的策略实例

    Raises:
        ValueError: 不支持的内容类型
    """
    strategies = {
        "novel": NovelStrategy,
        "series_script": SeriesScriptStrategy,
        "script": SeriesScriptStrategy,  # 兼容旧版
        "movie_script": MovieScriptStrategy,
    }

    strategy_cls = strategies.get(content_type)
    if strategy_cls is None:
        # 未知类型默认使用小说策略
        return NovelStrategy()

    return strategy_cls()
