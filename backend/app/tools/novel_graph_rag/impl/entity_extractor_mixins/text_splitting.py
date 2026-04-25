"""NovelEntityExtractor - 文本分块Mixin"""
import re
from typing import List


class TextSplittingMixin:
    """文本分块功能域"""

    def _smart_split_text(self, text: str) -> List[str]:
        """
        智能分块：优先按段落分割，如果段落过长则按句子分割
        """
        chunks = []

        # 1. 首先尝试按双换行符分割（段落）
        paragraphs = text.split('\n\n')

        # 如果只有一个段落（没有双换行符），尝试单换行符
        if len(paragraphs) == 1:
            paragraphs = text.split('\n')
            self.logger.debug(f"使用单换行符分割，得到 {len(paragraphs)} 个段落")
        else:
            self.logger.debug(f"使用双换行符分割，得到 {len(paragraphs)} 个段落")

        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前段落加上新段落不超过限制，合并
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n" + para
                else:
                    current_chunk = para
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果单个段落超过限制，需要进一步分割
                if len(para) > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(para)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = para

        # 保存最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        # 如果仍然没有分块（极端情况），强制按字符数分割
        if not chunks:
            for i in range(0, len(text), self.chunk_size):
                chunks.append(text[i:i+self.chunk_size])

        return chunks

    def _split_long_paragraph(self, para: str) -> List[str]:
        """分割过长的段落（按句子分割）"""
        chunks = []

        # 按中文句号、问号、感叹号分割句子
        sentences = re.split(r'([。！？!?\.]+)', para)

        # 重新组合句子和标点
        combined_sentences = []
        for i in range(0, len(sentences)-1, 2):
            if i+1 < len(sentences):
                combined_sentences.append(sentences[i] + sentences[i+1])
            else:
                combined_sentences.append(sentences[i])
        if len(sentences) % 2 == 1 and sentences[-1]:
            combined_sentences.append(sentences[-1])

        current_chunk = ""

        for sentence in combined_sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # 如果单个句子超过限制，强制截断
                if len(sentence) > self.chunk_size:
                    for i in range(0, len(sentence), self.chunk_size):
                        chunks.append(sentence[i:i+self.chunk_size])
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
