"""大纲生成器 - 主类（组合所有Mixin）"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.agents.llm_manager import get_llm_manager, LLMManager
from app.agents.prompt_manager import get_prompt_manager, PromptManager
from app.services.outline_generator.impl.mixins import (
    ParserMixin,
    GlobalOutlineMixin,
    UnitSummaryGenerateMixin,
    UnitSummaryStreamMixin,
    UnitSummaryResumeMixin,
    UnitSummarySingleMixin,
    UnitSummaryResumeContextMixin,
    RevisionMixin,
    RevisionAutoMixin,
    QcUnitAnalysisMixin,
    QcLayeredMixin,
    QcGlobalAnalysisMixin,
    QcGlobalRevisionMixin,
    ChapterBoundaryMixin,
    SemanticBoundaryValidatorMixin,
    AtomicChapterGeneratorMixin,
    AtomicChapterStreamMixin,
)


class OutlineGenerator(
    ParserMixin,
    GlobalOutlineMixin,
    UnitSummaryGenerateMixin,
    UnitSummaryStreamMixin,
    UnitSummaryResumeMixin,
    UnitSummarySingleMixin,
    UnitSummaryResumeContextMixin,
    RevisionMixin,
    RevisionAutoMixin,
    QcUnitAnalysisMixin,
    QcLayeredMixin,
    QcGlobalAnalysisMixin,
    QcGlobalRevisionMixin,
    ChapterBoundaryMixin,
    SemanticBoundaryValidatorMixin,
    AtomicChapterGeneratorMixin,
    AtomicChapterStreamMixin,
):
    """大纲生成器（两阶段） - 组合Mixin实现"""

    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.logger = get_logger(__name__)
        self.prompt_manager = get_prompt_manager()
        self.llm_manager = get_llm_manager()

    def _format_sse(self, event_type: str, data: dict) -> str:
        """格式化 SSE 事件"""
        import json
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 全局实例
_outline_generator = None


def get_outline_generator(db: AsyncSession = None) -> "OutlineGenerator":
    """获取大纲生成器实例"""
    global _outline_generator
    if _outline_generator is None:
        _outline_generator = OutlineGenerator(db)
    elif db is not None:
        _outline_generator.db = db
    return _outline_generator
