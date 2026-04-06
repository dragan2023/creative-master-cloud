"""
文档预处理器模块
构建两层预处理流水线：Cleaner -> Filter
优化 GraphRAG 的输入质量，降低 Token 消耗并提升知识图谱准确性

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import os
import re
import asyncio

from app.core.logger import get_logger
from app.core.config import get_settings


# 支持的编码列表（按优先级排序）
SUPPORTED_ENCODINGS = ['utf-8', 'gbk',
                       'gb2312', 'gb18030', 'utf-16', 'latin-1']


def read_file_with_encoding(file_path: str, encodings: List[str] = None) -> str:
    """
    尝试多种编码读取文件内容

    Args:
        file_path: 文件路径
        encodings: 要尝试的编码列表，默认使用 SUPPORTED_ENCODINGS

    Returns:
        文件内容字符串

    Raises:
        UnicodeDecodeError: 所有编码都无法解码
    """
    encodings = encodings or SUPPORTED_ENCODINGS
    last_error = None

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            return content
        except UnicodeDecodeError as e:
            last_error = e
            continue
        except Exception as e:
            raise

    # 所有编码都失败，抛出最后一个错误
    raise last_error


# 无意义内容正则模式（Filter层使用）
FILTER_PATTERNS = [
    # 免责声明
    r"免责声明[：:][\s\S]{0,300}(?=\n\n|\Z)",
    r"声明[：:][\s\S]{0,200}(?=\n\n|\Z)",
    # 版权信息
    r"版权所有[，,][\s\S]{0,150}(?=\n\n|\Z)",
    r"著作权[：:][\s\S]{0,150}(?=\n\n|\Z)",
    r"[\(（]c[\)）]\s*\d{4}[\s\S]{0,100}(?=\n\n|\Z)",
    # 参考文献
    r"参考文献\s*\n[\s\S]*?(?=\n\n[A-Z]|$)",
    r"References\s*\n[\s\S]*?(?=\n\n[A-Z]|$)",
    # 作者简介
    r"作者简介[：:][\s\S]{0,400}(?=\n\n|\Z)",
    r"关于作者[：:][\s\S]{0,400}(?=\n\n|\Z)",
    # 通用无意义声明
    r"本文.*?仅供参考[\s\S]{0,100}",
    r"转载请注明出处[\s\S]{0,100}",
    r"未经授权.*?禁止转载",
    r"所有权利保留",
    # 页眉页脚标记
    r"第\s*\d+\s*页\s*(共|/)\s*\d+\s*页",
    r"Page\s*\d+\s*(of|/)\s*\d+",
]


class DocumentPreprocessor:
    """
    文档预处理器

    两层流水线架构：
    1. Cleaner 层: 将 PDF/DOCX/TXT/MD 转换为纯文本
    2. Filter 层 (Regex): 剔除无意义内容
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.logger = get_logger("doc_preprocessor")

        # 设置代理（如果配置了）
        http_proxy = self.settings.HTTP_PROXY
        https_proxy = self.settings.HTTPS_PROXY
        if http_proxy:
            os.environ["HTTP_PROXY"] = http_proxy
            os.environ["http_proxy"] = http_proxy
            self.logger.info(f"使用 HTTP 代理: {http_proxy}")
        if https_proxy:
            os.environ["HTTPS_PROXY"] = https_proxy
            os.environ["https_proxy"] = https_proxy
            self.logger.info(f"使用 HTTPS 代理: {https_proxy}")

        # 支持的文件扩展名
        self.supported_extensions = {".pdf", ".docx", ".doc", ".txt", ".md"}

    def _refresh_config(self):
        """动态刷新配置（每次处理时调用）"""
        self.settings = get_settings()
        self.enable_filter = True  # 默认启用过滤

    def is_supported(self, file_path: str) -> bool:
        """检查文件是否支持"""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_extensions

    async def process(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        llm_provider=None
    ) -> Dict[str, Any]:
        """
        完整预处理流水线

        Args:
            file_path: 文件路径
            progress_callback: 进度回调函数 (step_name, progress, step_index)

        Returns:
            {
                "chunks": List[str],  # 切片后的文本块
                "metadata": Dict,     # 元数据
                "stats": Dict         # 统计信息
            }
        """
        # 动态刷新配置（确保使用最新设置）
        self._refresh_config()

        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}

        if not self.is_supported(file_path):
            return {"error": f"不支持的文件格式: {Path(file_path).suffix}"}

        ext = Path(file_path).suffix.lower()
        stats = {
            "original_size": 0,
            "cleaned_size": 0,
            "filtered_size": 0,
            "chunk_count": 0,
            "steps_completed": []
        }

        try:
            # Step 1: Cleaner - 文档转换
            if progress_callback:
                progress_callback("正在转换文档格式...", 5, 1)

            text = await self._parse_with_fallback(file_path)

            stats["original_size"] = len(text)
            stats["steps_completed"].append("cleaner")

            # Step 2: Filter - 内容过滤
            if progress_callback:
                progress_callback("正在过滤无效内容...", 15, 2)

            if self.enable_filter:
                text = self._filter_content(text)

            stats["filtered_size"] = len(text)
            stats["steps_completed"].append("filter")

            # Step 3: 切片
            if progress_callback:
                progress_callback("正在切分文档...", 25, 3)

            chunks = self._fallback_chunk(text)

            stats["chunk_count"] = len(chunks)
            stats["steps_completed"].append("chunk")

            return {
                "chunks": chunks,
                "metadata": {
                    "file_path": file_path,
                    "file_type": ext.lstrip("."),
                    "preprocessor_enabled": True,
                },
                "stats": stats
            }

        except Exception as e:
            self.logger.error(f"文档预处理失败: {str(e)}")
            # 尝试回退到基本解析
            return await self._fallback_process(file_path, str(e))

    async def _parse_with_fallback(self, file_path: str) -> str:
        """解析文档：使用 pypdf 或 python-docx"""
        ext = Path(file_path).suffix.lower()

        try:
            if ext == ".pdf":
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                text_parts = [page.extract_text()
                              for page in reader.pages if page.extract_text()]
                return "\n\n".join(text_parts)

            elif ext in [".docx", ".doc"]:
                from docx import Document
                doc = Document(file_path)
                paragraphs = [
                    para.text for para in doc.paragraphs if para.text.strip()]
                return "\n".join(paragraphs)

            elif ext in [".txt", ".md"]:
                return read_file_with_encoding(file_path)

            else:
                return ""

        except Exception as e:
            self.logger.error(f"回退解析失败: {str(e)}")
            return ""

    def _filter_content(self, text: str) -> str:
        """
        Filter层：过滤无意义内容

        使用正则模式匹配并删除：
        - 免责声明
        - 版权信息
        - 参考文献
        - 作者简介
        - 页眉页脚
        """
        original_len = len(text)

        for pattern in FILTER_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

        # 去除多余空白
        text = re.sub(r"\n{3,}", "\n\n", text)  # 最多两个连续换行
        text = re.sub(r" {2,}", " ", text)  # 最多一个连续空格
        text = re.sub(r"^\s+|\s+$", "", text, flags=re.MULTILINE)  # 去除行首行尾空白

        filtered_len = len(text)

        return text.strip()

    def _fallback_chunk(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """固定大小切片"""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # 尝试在句子边界分割
            if end < len(text):
                last_period = text.rfind("。", start, end)
                last_newline = text.rfind("\n", start, end)
                split_point = max(last_period, last_newline)

                if split_point > start + chunk_size // 2:
                    end = split_point + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    async def _fallback_process(self, file_path: str, error: str) -> Dict[str, Any]:
        """完全回退处理"""
        self.logger.warning(f"使用完全回退处理: {error}")

        text = await self._parse_with_fallback(file_path)
        chunks = self._fallback_chunk(text)

        return {
            "chunks": chunks,
            "metadata": {
                "file_path": file_path,
                "preprocessor_enabled": False,
                "fallback_used": True,
                "error": error
            },
            "stats": {
                "chunk_count": len(chunks),
                "original_size": len(text),
                "steps_completed": ["fallback"]
            }
        }


# 全局预处理器实例
_doc_preprocessor = None


def get_doc_preprocessor() -> DocumentPreprocessor:
    """获取文档预处理器单例"""
    global _doc_preprocessor
    if _doc_preprocessor is None:
        _doc_preprocessor = DocumentPreprocessor()
    return _doc_preprocessor


# 便捷函数
async def preprocess_document(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> Dict[str, Any]:
    """
    预处理文档的便捷函数

    Args:
        file_path: 文件路径
        progress_callback: 进度回调

    Returns:
        预处理结果
    """
    preprocessor = get_doc_preprocessor()
    return await preprocessor.process(file_path, progress_callback)
