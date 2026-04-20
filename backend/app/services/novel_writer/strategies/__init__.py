"""
上下文构建策略模块

通过策略模式消除三套build_*_context方法和三套_extract_*_outline方法的代码冗余。
新增内容类型时只需添加一个策略类。

@date: 2026-04-19
@version: v1.0.0
"""
from app.services.novel_writer.strategies.base import ContextBuildStrategy
from app.services.novel_writer.strategies.novel import NovelStrategy
from app.services.novel_writer.strategies.series_script import SeriesScriptStrategy
from app.services.novel_writer.strategies.movie_script import MovieScriptStrategy
from app.services.novel_writer.strategies.factory import get_strategy

__all__ = [
    "ContextBuildStrategy",
    "NovelStrategy",
    "SeriesScriptStrategy",
    "MovieScriptStrategy",
    "get_strategy",
]
