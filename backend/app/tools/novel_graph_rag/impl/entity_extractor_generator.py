"""NovelEntityExtractor - 主类（组合所有Mixin）"""
import asyncio
from typing import Dict, Any

from app.core.logger import get_logger
from app.tools.novel_graph_rag.constants import (
    NOVEL_CHUNK_SIZE,
    NOVEL_MAX_ENTITIES_PER_CHUNK,
    NOVEL_MAX_RELATIONS_PER_CHUNK,
)
from app.tools.novel_graph_rag.prompts import NOVEL_EXTRACTION_PROMPT
from app.tools.novel_graph_rag.impl.entity_extractor_mixins import (
    TextSplittingMixin,
    JsonParsingMixin,
    CharacterExtractionMixin,
    ExtendedExtractionMixin,
)


class NovelEntityExtractor(
    TextSplittingMixin,
    JsonParsingMixin,
    CharacterExtractionMixin,
    ExtendedExtractionMixin,
):
    """
    正文板块专属实体提取器
    完全独立于公共知识库的LLMEntityExtractor类
    """

    def __init__(self, llm_provider):
        """
        初始化提取器

        Args:
            llm_provider: LLM提供者
        """
        self.llm_provider = llm_provider
        self.logger = get_logger("novel_entity_extractor")

        # 使用正文板块专属配置
        self.chunk_size = NOVEL_CHUNK_SIZE
        self.max_entities_per_chunk = NOVEL_MAX_ENTITIES_PER_CHUNK
        self.max_relations_per_chunk = NOVEL_MAX_RELATIONS_PER_CHUNK

    async def extract_with_llm(self, text: str, max_retries: int = 2) -> Dict[str, Any]:
        """
        使用LLM提取实体和关系

        Args:
            text: 输入文本
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...]}
        """
        # 检查文本长度，决定是否分块
        if len(text) > self.chunk_size:
            return await self._extract_from_long_text(text)

        return await self._extract_single_chunk(text, max_retries)

    async def _extract_from_long_text(self, text: str) -> Dict[str, Any]:
        """处理长文本，分段提取后合并"""
        all_entities = []
        all_relations = []
        success_count = 0
        fail_count = 0

        # 智能分块
        chunks = self._smart_split_text(text)
        total_chunks = len(chunks)

        self.logger.info(
            f"正文板块长文本分块: 总长度={len(text)}, chunk大小={self.chunk_size}, 分成{total_chunks}块")

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            self.logger.debug(f"处理第 {i+1}/{total_chunks} 块, 长度={len(chunk)}")
            result = await self._extract_single_chunk(chunk)

            if result.get("entities") or result.get("relations"):
                all_entities.extend(result.get("entities", []))
                all_relations.extend(result.get("relations", []))
                success_count += 1
            else:
                fail_count += 1

        # 去重
        unique_entities = self._deduplicate_entities(all_entities)
        unique_relations = self._deduplicate_relations(all_relations)

        self.logger.info(
            f"正文板块长文本处理完成: {total_chunks}个chunk, 成功{success_count}个, 失败{fail_count}个")

        return {
            "entities": unique_entities,
            "relations": unique_relations
        }

    async def _extract_single_chunk(self, text: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        提取单个文本块的实体和关系

        增强的重试机制：
        - 针对429错误（服务器过载）使用指数退避
        - 区分不同类型的错误
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                # 使用正文板块专用提示词
                prompt = NOVEL_EXTRACTION_PROMPT.format(
                    max_entities=self.max_entities_per_chunk,
                    max_relations=self.max_relations_per_chunk,
                    content=text
                )

                # 获取模型支持的最大输出token
                max_output_tokens = self.llm_provider.get_max_output_tokens()

                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=max_output_tokens
                )

                # 调试日志
                self.logger.debug(
                    f"LLM响应长度: {len(response.content) if response and hasattr(response, 'content') and response.content else 0}")

                if not response or not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"LLM返回无效响应，尝试 {attempt+1}/{max_retries}")
                    continue

                # 解析响应
                result = self._parse_llm_response(response.content)
                if result:
                    return result

                self.logger.warning(f"JSON解析失败，尝试 {attempt+1}/{max_retries}")

            except Exception as e:
                error_str = str(e)
                last_error = e

                # 检测429错误（服务器过载/限流）
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower(
                ) or 'overload' in error_str.lower()

                if is_rate_limit:
                    # 指数退避：10秒 -> 20秒 -> 40秒
                    wait_time = 10 * (2 ** attempt)
                    self.logger.warning(
                        f"API限流/服务器过载(429)，等待 {wait_time}秒 后重试... (尝试 {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                else:
                    # 其他错误：较短等待
                    self.logger.warning(f"LLM实体提取异常: {error_str[:200]}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)

        self.logger.error(
            f"所有重试失败，返回空结果。最后错误: {str(last_error)[:200] if last_error else 'None'}")
        return {"entities": [], "relations": []}
