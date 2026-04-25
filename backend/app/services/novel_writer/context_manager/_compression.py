"""
上下文窗口管理器 - 语义压缩Mixin

提供上下文压缩和智能截断功能。

@date: 2026-04-24
@version: v3.1.0 (从context_manager.py拆分)
"""
from typing import Dict, Any


class CompressionMixin:
    """语义压缩Mixin

    核心原则：
    - 仅压缩"参考性"字段（前文摘要、向量检索结果等）
    - 绝不压缩"指导性"字段（global_outline、unit_summaries、当前单元大纲等）
    - 绝不使用字符串切片截断大纲/概述内容
    - 当上下文总长度超过阈值时才触发压缩
    """

    async def _compress_context(
        self,
        context: Dict[str, Any],
        max_length: int = None
    ) -> Dict[str, Any]:
        """语义压缩：对超长字段用LLM摘要替代截断

        Args:
            context: 原始上下文字典
            max_length: 最大允许长度（已忽略，由压缩阈值控制）

        Returns:
            压缩后的上下文字典
        """
        if not self.semantic_compressor:
            # 无压缩器时直接返回原始上下文（向后兼容）
            return context

        # 仅压缩可压缩的参考性字段
        compressible_keys = [
            "previous_content_summaries",
            "short_summary",
            "vector_context",
            "global_summary",
        ]

        return await self.semantic_compressor.compress_context_dict(
            context, compressible_keys=compressible_keys
        )

    def _smart_truncate(self, text: str, max_len: int) -> str:
        """智能截断（已重构为安全占位方法）

        核心约束：禁止对正文生成结果做截断处理。
        此方法保留仅为向后兼容，实际不再执行截断。
        对于前文摘要等需要精简的场景，使用SemanticCompressor替代。

        Args:
            text: 原始文本
            max_len: 最大长度（已忽略）

        Returns:
            原始文本（不做截断）
        """
        # 核心约束：禁止截断，直接返回原始文本
        # 如需压缩前文摘要等参考性内容，请使用SemanticCompressor
        return text
