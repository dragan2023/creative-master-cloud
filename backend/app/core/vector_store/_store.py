# -*- coding: utf-8 -*-
"""
向量数据库 - VectorStore 核心类

提供 ChromaDB 集合管理、文档增删查改、健康检查与修复等功能。
"""
import os
import time
import asyncio
import threading
import uuid
from typing import Optional, List, Dict, Any

import chromadb
from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.vector_store._embedding import get_embedding_function

logger = get_logger("vector_store")


class VectorStore:
    """向量数据库管理类

    特性：
    - 写入串行化：使用异步锁避免并发写入冲突
    - 自动重试：HNSW 索引错误时自动重试
    - 健康检查：检测并修复损坏的索引
    - 写入验证：写入后验证数据完整性
    - 缓存管理：管理 ChromaDB 内部缓存，避免数据不一致
    """

    def __init__(self):
        self._client: Optional[chromadb.Client] = None
        self._collections: Dict[str, chromadb.Collection] = {}
        self._write_lock = threading.Lock()
        self._async_write_lock = asyncio.Lock()
        self._max_retries = 3
        self._retry_delay = 1.0
        self._verify_writes = True
        self._verify_delay = 0.1

    @property
    def client(self) -> chromadb.Client:
        """获取 ChromaDB 客户端（延迟初始化）"""
        if self._client is None:
            settings = get_settings()
            persist_dir = settings.get_chroma_dir()
            os.makedirs(persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=persist_dir)
        return self._client

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """获取或创建集合"""
        if name not in self._collections:
            embedding_func = get_embedding_function()
            try:
                existing = self.client.get_collection(name=name)
                count = existing.count()
                if count > 0:
                    self._collections[name] = existing
                    logger.debug(f"[向量库] 使用已存在的集合: {name}, 文档数: {count}")
                    return existing
                self.client.delete_collection(name=name)
                logger.info(f"[向量库] 删除空集合以便重建: {name}")
            except Exception as e:
                logger.debug(f"[向量库] 获取集合失败，将创建新集合: {name}, 原因: {e}")

            try:
                self._collections[name] = self.client.create_collection(
                    name=name,
                    embedding_function=embedding_func,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"[向量库] 创建新集合: {name}")
            except Exception as create_error:
                error_msg = str(create_error)
                if "embedding" in error_msg.lower():
                    logger.warning(f"[向量库] Embedding 冲突，尝试使用默认配置: {error_msg}")
                    self._collections[name] = self.client.get_or_create_collection(
                        name=name,
                        metadata={"hnsw:space": "cosine"}
                    )
                else:
                    raise
        return self._collections[name]

    def delete_collection(self, name: str) -> None:
        """删除集合"""
        try:
            self.client.delete_collection(name=name)
            if name in self._collections:
                del self._collections[name]
        except Exception as e:
            logger.warning(f"删除集合失败: {e}")

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        verify: bool = True
    ) -> Dict[str, Any]:
        """添加文档到向量数据库（带重试机制和写入验证）"""
        result = {"success": False, "count": 0, "verified": False, "error": None}

        if not documents:
            result["success"] = True
            return result

        with self._write_lock:
            collection = self.get_or_create_collection(collection_name)
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in documents]

            cleaned_metadatas = None
            if metadatas:
                cleaned_metadatas = []
                for meta in metadatas:
                    cleaned_meta = {}
                    for key, value in meta.items():
                        if value is None:
                            cleaned_meta[key] = ""
                        elif isinstance(value, (str, int, float, bool)):
                            cleaned_meta[key] = value
                        else:
                            cleaned_meta[key] = str(value)
                    cleaned_metadatas.append(cleaned_meta)

            last_error = None
            for attempt in range(self._max_retries):
                try:
                    collection.add(
                        documents=documents,
                        metadatas=cleaned_metadatas,
                        ids=ids
                    )
                    if self._verify_delay > 0:
                        time.sleep(self._verify_delay)

                    if verify and self._verify_writes:
                        verified = self._verify_write(collection, ids, len(documents))
                        if not verified:
                            logger.warning(
                                f"[向量库] 写入验证失败，重试中: collection={collection_name}, "
                                f"attempt={attempt + 1}/{self._max_retries}"
                            )
                            self._clear_collection_cache(collection_name)
                            collection = self.get_or_create_collection(collection_name)
                            if attempt < self._max_retries - 1:
                                time.sleep(self._retry_delay * (attempt + 1))
                                continue
                        else:
                            result["verified"] = True

                    result["success"] = True
                    result["count"] = len(documents)
                    if attempt > 0:
                        logger.info(
                            f"[向量库] 写入成功（第{attempt + 1}次重试）: collection={collection_name}, "
                            f"count={len(documents)}, verified={result['verified']}"
                        )
                    else:
                        logger.debug(f"[向量库] 写入成功: collection={collection_name}, count={len(documents)}")
                    return result

                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    if any(err in error_msg for err in ["hnsw", "compaction", "index", "locked", "busy", "timeout"]):
                        logger.warning(f"[向量库] 写入错误（第{attempt + 1}次尝试）: {str(e)[:100]}")
                        if attempt < self._max_retries - 1:
                            time.sleep(self._retry_delay * (attempt + 1))
                            self._clear_collection_cache(collection_name)
                            try:
                                collection = self.get_or_create_collection(collection_name)
                            except Exception as e:
                                logger.warning(f"重建集合失败: {e}")
                            continue
                    else:
                        logger.error(f"[向量库] 写入失败: {str(e)}")
                        result["error"] = str(e)
                        raise

            logger.error(f"[向量库] 写入失败（已重试{self._max_retries}次）: collection={collection_name}, error={last_error}")
            result["error"] = str(last_error)
            raise last_error

    def _verify_write(self, collection: chromadb.Collection, ids: List[str], expected_count: int) -> bool:
        """验证写入是否成功"""
        try:
            actual_count = collection.count()
            if actual_count < expected_count:
                logger.warning(f"[向量库] 验证失败: 文档数量不足, expected>={expected_count}, actual={actual_count}")
                return False

            sample_size = min(5, len(ids))
            sample_ids = ids[:sample_size]
            try:
                result = collection.get(ids=sample_ids, include=[])
                if len(result.get("ids", [])) != sample_size:
                    logger.warning(f"[向量库] 验证失败: 部分ID不存在, expected={sample_size}, found={len(result.get('ids', []))}")
                    return False
            except Exception as e:
                logger.warning(f"[向量库] ID验证异常: {e}")
                return False

            logger.debug(f"[向量库] 写入验证通过: count={actual_count}")
            return True
        except Exception as e:
            logger.warning(f"[向量库] 验证过程异常: {e}")
            return False

    def _clear_collection_cache(self, collection_name: str) -> None:
        """清除集合缓存"""
        if collection_name in self._collections:
            del self._collections[collection_name]
            logger.debug(f"[向量库] 已清除集合缓存: {collection_name}")

    def clear_all_caches(self) -> None:
        """清除所有缓存"""
        self._collections.clear()
        logger.info("[向量库] 已清除所有集合缓存")

    def clear_system_cache(self) -> bool:
        """清除 ChromaDB 系统缓存"""
        try:
            if hasattr(self._client, 'clear_system_cache'):
                self._client.clear_system_cache()
                logger.info("[向量库] 已清除系统缓存")
                return True
            else:
                logger.warning("[向量库] 当前 ChromaDB 版本不支持 clear_system_cache")
                return False
        except Exception as e:
            logger.warning(f"[向量库] 清除系统缓存失败: {e}")
            return False

    async def add_documents_async(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        verify: bool = True
    ) -> Dict[str, Any]:
        """异步添加文档到向量数据库"""
        async with self._async_write_lock:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.add_documents(collection_name, documents, metadatas, ids, verify)
            )
            return result

    def query(
        self,
        collection_name: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[dict] = None
    ) -> dict:
        """查询相似文档"""
        try:
            collection = self.get_or_create_collection(collection_name)
            doc_count = collection.count()
            if doc_count == 0:
                logger.debug(f"[向量库] 集合为空，跳过查询: {collection_name}")
                return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

            return collection.query(
                query_texts=query_texts,
                n_results=min(n_results, doc_count),
                where=where
            )
        except Exception as e:
            error_msg = str(e).lower()
            if any(err in error_msg for err in ["hnsw", "nothing found on disk", "error finding id", "internal error", "error executing plan"]):
                logger.warning(f"[向量库] 查询遇到内部错误，尝试修复: {collection_name}, error={str(e)[:100]}")
                try:
                    self._clear_collection_cache(collection_name)
                    if self._client is None:
                        _ = self.client
                    if hasattr(self._client, 'clear_system_cache'):
                        self._client.clear_system_cache()
                    collection = self.get_or_create_collection(collection_name)
                    doc_count = collection.count()
                    if doc_count == 0:
                        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
                    return collection.query(
                        query_texts=query_texts,
                        n_results=min(n_results, doc_count),
                        where=where
                    )
                except Exception as repair_error:
                    logger.error(f"[向量库] 自动修复失败: {collection_name}, error={str(repair_error)[:100]}")
                    return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            else:
                logger.error(f"[向量库] 查询失败: {collection_name}, error={str(e)}")
                raise

    def count_documents(self, collection_name: str) -> int:
        """获取文档数量"""
        collection = self.get_or_create_collection(collection_name)
        return collection.count()

    def health_check(self) -> dict:
        """健康检查：检测 ChromaDB 索引状态"""
        result = {"healthy": True, "collections": [], "errors": []}
        try:
            collections = self.client.list_collections()
            for coll in collections:
                try:
                    count = coll.count()
                    result["collections"].append({"name": coll.name, "count": count, "status": "ok"})
                except Exception as e:
                    result["healthy"] = False
                    result["collections"].append({"name": coll.name, "count": 0, "status": "error", "error": str(e)[:100]})
                    result["errors"].append(f"Collection '{coll.name}': {str(e)[:100]}")
        except Exception as e:
            result["healthy"] = False
            result["errors"].append(f"Client error: {str(e)[:100]}")
        return result

    def repair_collection(self, collection_name: str) -> bool:
        """修复损坏的集合"""
        try:
            logger.info(f"[向量库] 开始修复集合: {collection_name}")
            self.delete_collection(collection_name)
            self.get_or_create_collection(collection_name)
            logger.info(f"[向量库] 集合修复成功: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"[向量库] 集合修复失败: {collection_name}, error={str(e)}")
            return False

    def repair_all_collections(self) -> dict:
        """修复所有损坏的集合"""
        report = {"checked": 0, "repaired": 0, "failed": 0, "details": []}
        health = self.health_check()
        for coll_info in health["collections"]:
            report["checked"] += 1
            if coll_info.get("status") == "error":
                if self.repair_collection(coll_info["name"]):
                    report["repaired"] += 1
                    report["details"].append({"name": coll_info["name"], "action": "repaired", "success": True})
                else:
                    report["failed"] += 1
                    report["details"].append({"name": coll_info["name"], "action": "repair_failed", "success": False})
        logger.info(f"[向量库] 修复完成: 检查={report['checked']}, 修复={report['repaired']}, 失败={report['failed']}")
        return report
