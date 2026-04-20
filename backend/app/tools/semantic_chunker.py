"""
语义切片器
基于语义相似度智能划分文本边界，优化GraphRAG检索效果

@date: 2026-04-10
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import List, Dict, Any, Optional
import numpy as np
from app.core.logger import get_logger

logger = get_logger("semantic_chunker")


class SemanticChunker:
    """
    语义切片器

    使用句子嵌入模型计算语义相似度，在语义变化大的地方切分文本
    相比固定大小切片，能更好地保持语义完整性
    """

    def __init__(
        self,
        chunk_size: int = 1024,
        threshold: float = 0.7,
        use_embeddings: bool = True
    ):
        """
        初始化语义切片器

        Args:
            chunk_size: 目标切片大小（Token数）
            threshold: 语义相似度阈值（0-1），越低分块越大
            use_embeddings: 是否使用嵌入模型（False则使用启发式方法）
        """
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.use_embeddings = use_embeddings
        self._embedding_model = None

        if use_embeddings:
            self._load_embedding_model()

    def _load_embedding_model(self):
        """加载嵌入模型（延迟加载）"""
        try:
            # 尝试使用sentence-transformers
            from sentence_transformers import SentenceTransformer

            # 使用轻量级中文模型
            model_name = "shibing624/text2vec-base-chinese"
            logger.info(f"加载语义嵌入模型: {model_name}")

            self._embedding_model = SentenceTransformer(model_name)
            logger.info("语义嵌入模型加载成功")

        except Exception as e:
            logger.warning(f"无法加载嵌入模型，将使用启发式方法: {str(e)}")
            self.use_embeddings = False
            self._embedding_model = None

    def chunk_text(self, text: str) -> List[str]:
        """
        将文本按语义切片

        Args:
            text: 输入文本

        Returns:
            切片后的文本列表
        """
        if not text or not text.strip():
            return []

        # 如果文本很短，直接返回
        if len(text) <= self.chunk_size:
            return [text.strip()]

        if self.use_embeddings and self._embedding_model:
            return self._chunk_with_embeddings(text)
        else:
            return self._chunk_with_heuristics(text)

    def _chunk_with_embeddings(self, text: str) -> List[str]:
        """使用嵌入模型进行语义切片"""
        try:
            # 1. 按句子分割
            sentences = self._split_into_sentences(text)

            if len(sentences) <= 1:
                return [text.strip()]

            # 2. 计算每个句子的嵌入向量
            embeddings = self._embedding_model.encode(sentences)

            # 3. 计算相邻句子的语义相似度
            similarities = []
            for i in range(len(embeddings) - 1):
                sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
                similarities.append(sim)

            # 4. 在相似度低于阈值的位置切分
            chunks = []
            current_chunk_start = 0

            for i, sim in enumerate(similarities):
                current_chunk = " ".join(sentences[current_chunk_start:i + 1])

                # 如果当前块达到目标大小且相似度低于阈值，则切分
                if len(current_chunk) >= self.chunk_size * 0.8 and sim < self.threshold:
                    chunk_text = " ".join(
                        sentences[current_chunk_start:i + 1]).strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_chunk_start = i + 1

            # 添加最后一个块
            if current_chunk_start < len(sentences):
                chunk_text = " ".join(sentences[current_chunk_start:]).strip()
                if chunk_text:
                    chunks.append(chunk_text)

            # 如果没有切分出任何块（所有相似度都很高），使用固定大小切分
            if not chunks:
                logger.info("语义切片未产生切分，回退到固定大小切片")
                return self._fixed_size_chunk(text)

            logger.info(f"语义切片完成: {len(sentences)}个句子 -> {len(chunks)}个块")
            return chunks

        except Exception as e:
            logger.error(f"语义切片失败，回退到启发式方法: {str(e)}")
            return self._chunk_with_heuristics(text)

    def _chunk_with_heuristics(self, text: str) -> List[str]:
        """
        使用启发式方法进行语义切片
        基于段落、标题、标点符号等结构特征
        """
        # 1. 首先按段落分割
        paragraphs = text.split('\n\n')

        # 2. 合并小段落，分割大段落
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_size = len(para)

            # 如果单个段落就超过目标大小，需要进一步分割
            if para_size > self.chunk_size * 1.5:
                # 先保存当前块
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_chunk = []
                    current_size = 0

                # 分割大段落
                sub_chunks = self._split_large_paragraph(para)
                chunks.extend(sub_chunks)

            # 如果加入这个段落会超过目标大小，先保存当前块
            elif current_size + para_size > self.chunk_size * 1.2:
                chunk_text = '\n\n'.join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                current_chunk = [para]
                current_size = para_size

            # 否则添加到当前块
            else:
                current_chunk.append(para)
                current_size += para_size

        # 添加最后一个块
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)

        # 如果还是没有切分，使用固定大小
        if not chunks:
            return self._fixed_size_chunk(text)

        logger.info(f"启发式切片完成: {len(chunks)}个块")
        return chunks

    def _split_large_paragraph(self, paragraph: str) -> List[str]:
        """分割大段落"""
        # 尝试在句子边界分割
        sentences = self._split_into_sentences(paragraph)

        if len(sentences) <= 1:
            return [paragraph]

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sent_size = len(sentence)

            if current_size + sent_size > self.chunk_size:
                if current_chunk:
                    chunk_text = ' '.join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_chunk = []
                    current_size = 0

            current_chunk.append(sentence)
            current_size += sent_size

        if current_chunk:
            chunk_text = ' '.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)

        return chunks if chunks else [paragraph]

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        将文本分割成句子
        支持中英文标点符号
        """
        import re

        # 中英文句子结束符
        sentence_endings = r'[。！？.!？\n]+'

        # 分割句子
        sentences = re.split(sentence_endings, text)

        # 过滤空句子
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def _fixed_size_chunk(self, text: str) -> List[str]:
        """固定大小切片（回退方案）"""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # 尝试在句子边界分割
            if end < len(text):
                last_period = text.rfind("。", start, end)
                last_newline = text.rfind("\n", start, end)
                last_space = text.rfind(" ", start, end)

                split_point = max(last_period, last_newline, last_space)

                if split_point > start + self.chunk_size // 2:
                    end = split_point + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end

        return chunks

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算两个向量的余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))
