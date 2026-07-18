"""Public asynchronous document parser and text chunking helpers."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Dict, List, Optional

from app.core.blocking_executor import run_blocking
from app.core.config import get_settings
from app.tools.document_extractors import SUPPORTED_DOCUMENT_EXTENSIONS, extract_document


class FileParser:
    """Async facade over the single synchronous document extraction layer."""

    def __init__(self, use_preprocessor: bool | None = None):
        self.supported_extensions = set(SUPPORTED_DOCUMENT_EXTENSIONS)
        self.settings = get_settings()
        if use_preprocessor is None:
            use_preprocessor = self.settings.DOC_PREPROCESSOR_ENABLED
        self.use_preprocessor = use_preprocessor
        self._preprocessor = None

    def _get_preprocessor(self, config=None):
        if self._preprocessor is None and self.use_preprocessor:
            from app.tools.doc_preprocessor import DocumentPreprocessor

            self._preprocessor = DocumentPreprocessor(self.settings, config=config)
        elif config and self._preprocessor:
            self._preprocessor.config = config
        return self._preprocessor

    def is_supported(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.supported_extensions

    async def parse(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {"error": f"DOC-EXTRACT-NOT-FOUND: 文件不存在: {file_path}"}
        if not self.is_supported(file_path):
            return {
                "error": (
                    "DOC-EXTRACT-UNSUPPORTED: 不支持的文件格式: "
                    f"{Path(file_path).suffix}"
                )
            }
        return await run_blocking(extract_document, file_path)

    def split_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        if not text.strip():
            return []
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end < len(text):
                split_point = max(text.rfind("。", start, end), text.rfind("\n", start, end))
                if split_point > start + chunk_size // 2:
                    end = split_point + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap
        return chunks

    async def parse_and_split(
        self,
        file_path: str,
        chunk_size: int = 1000,
        overlap: int = 100,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        llm_provider=None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        preprocessor = self._get_preprocessor(config)
        if preprocessor:
            return await preprocessor.process(file_path, progress_callback, llm_provider)
        result = await self.parse(file_path)
        if "error" in result:
            return result
        chunks = self.split_text(result["content"], chunk_size, overlap)
        if not chunks:
            return {"error": "DOC-EXTRACT-EMPTY: 文件未提取到有效文本"}
        return {"chunks": chunks, "chunk_count": len(chunks), "metadata": result["metadata"]}


file_parser = FileParser()


def get_file_parser() -> FileParser:
    return file_parser


async def parse_document_file(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temporary:
        temporary.write(content)
        temporary_path = temporary.name
    try:
        result = await FileParser().parse(temporary_path)
        if "error" in result:
            raise ValueError(result["error"])
        return result["content"]
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
