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
        # 🆕 追踪因HNSW损坏被自动修复（删除后重建为空）的集合
        self._repaired_empty: set = set()

    @property
    def client(self) -> chromadb.Client:
        """获取 ChromaDB 客户端（延迟初始化）"""
        if self._client is None:
            settings = get_settings()
            persist_dir = settings.get_chroma_dir()
            os.makedirs(persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=persist_dir)
        return self._client

    def _is_hnsw_corruption_error(self, error: Exception) -> bool:
        """检测 HNSW 索引损坏类错误（Nothing found on disk / segment reader 等）"""
        error_msg = str(error).lower()
        return any(kw in error_msg for kw in [
            "nothing found on disk",
            "error creating hnsw segment reader",
            "hnsw",
            "error executing plan",
            "internal error",
            "error finding id",
        ])

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """获取或创建集合（自动修复 HNSW 索引损坏）"""
        if name not in self._collections:
            embedding_func = get_embedding_function()
            existing = None
            needs_recreate = False

            try:
                existing = self.client.get_collection(name=name)
                count = existing.count()
                if count > 0:
                    self._collections[name] = existing
                    logger.debug(f"[向量库] 使用已存在的集合: {name}, 文档数: {count}")
                    return existing
                needs_recreate = True
            except Exception as e:
                if self._is_hnsw_corruption_error(e):
                    logger.warning(
                        f"[向量库] 检测到 HNSW 索引损坏，将删除后重建: {name}, "
                        f"error={str(e)[:100]}"
                    )
                    needs_recreate = True
                else:
                    logger.debug(f"[向量库] 获取集合失败，将创建新集合: {name}, 原因: {e}")
                    needs_recreate = True

            if needs_recreate:
                # 尝试删除损坏/空的集合（容错：即使删除失败也继续重建）
                try:
                    if existing is not None:
                        self.client.delete_collection(name=name)
                        logger.info(f"[向量库] 已删除损坏/空集合: {name}")
                except Exception as del_err:
                    logger.warning(
                        f"[向量库] 删除集合失败（可能索引已损坏），尝试强制清理: {name}, "
                        f"error={str(del_err)[:100]}"
                    )
                    # 如果 ChromaDB API 删除失败，尝试清除内部缓存后重试
                    self._clear_collection_cache(name)
                    try:
                        self.client.delete_collection(name=name)
                    except Exception:
                        logger.warning(
                            f"[向量库] 强制清理也无法删除集合，将尝试直接创建覆盖: {name}"
                        )

            try:
                self._collections[name] = self.client.create_collection(
                    name=name,
                    embedding_function=embedding_func,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"[向量库] 创建新集合: {name}")
            except Exception as create_error:
                error_msg = str(create_error)
                if "already exists" in error_msg.lower():
                    # 集合已存在（可能删除未生效），尝试强制 SQLite 清理后重建
                    logger.warning(
                        f"[向量库] 集合已存在（删除未生效），尝试 SQLite 强制清理: {name}"
                    )
                    self._force_delete_collection_via_sqlite(name)
                    # 重试创建
                    self._collections[name] = self.client.create_collection(
                        name=name,
                        embedding_function=embedding_func,
                        metadata={"hnsw:space": "cosine"}
                    )
                    logger.info(f"[向量库] SQLite 清理后创建成功: {name}")
                elif "embedding" in error_msg.lower():
                    logger.warning(f"[向量库] Embedding 冲突，尝试使用默认配置: {error_msg}")
                    self._collections[name] = self.client.get_or_create_collection(
                        name=name,
                        metadata={"hnsw:space": "cosine"}
                    )
                else:
                    raise
        return self._collections[name]

    def delete_collection(self, name: str) -> None:
        """删除集合（先尝试 API 删除，失败则强制 SQLite 清理）"""
        try:
            self.client.delete_collection(name=name)
            if name in self._collections:
                del self._collections[name]
            logger.debug(f"[向量库] 已通过 API 删除集合: {name}")
        except Exception as e:
            err_msg = str(e).lower()
            # 集合不存在 = 已处于期望状态，静默跳过
            if "does not exist" in err_msg or "not found" in err_msg:
                if name in self._collections:
                    del self._collections[name]
                logger.debug(f"[向量库] 集合不存在，跳过删除: {name}")
            elif self._is_hnsw_corruption_error(e) or "nothing found" in err_msg:
                logger.warning(
                    f"[向量库] API 删除失败（索引损坏），尝试 SQLite 强制清理: {name}"
                )
                self._force_delete_collection_via_sqlite(name)
            else:
                logger.warning(f"[向量库] 删除集合失败: {name}, error={str(e)[:100]}")

    def _force_delete_collection_via_sqlite(self, name: str) -> None:
        """直接通过 SQLite 删除 ChromaDB 集合元数据（用于 HNSW 索引损坏无法通过 API 删除的情况）"""
        import sqlite3
        settings = get_settings()
        persist_dir = settings.get_chroma_dir()
        db_path = os.path.join(persist_dir, "chroma.sqlite3")

        if not os.path.exists(db_path):
            logger.warning(f"[向量库] chroma.sqlite3 不存在，无法强制清理: {db_path}")
            return

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 查询集合 UUID
            cursor.execute(
                "SELECT id FROM collections WHERE name = ?", (name,)
            )
            row = cursor.fetchone()
            if row:
                collection_uuid = row[0]
                # 删除集合记录（CASCADE 会清理关联表）
                cursor.execute("DELETE FROM collections WHERE id = ?", (collection_uuid,))
                conn.commit()
                logger.info(
                    f"[向量库] SQLite 强制清理成功: {name} (uuid={collection_uuid})"
                )
                # 同时清理 segment 目录
                segment_dir = os.path.join(persist_dir, collection_uuid)
                if os.path.isdir(segment_dir):
                    import shutil
                    shutil.rmtree(segment_dir, ignore_errors=True)
                    logger.info(f"[向量库] 已清理 segment 目录: {collection_uuid}")
            else:
                logger.info(f"[向量库] SQLite 中未找到集合记录: {name}（可能已被清理）")

            conn.close()

            # 清除内存缓存
            if name in self._collections:
                del self._collections[name]
        except Exception as sqlite_err:
            logger.error(
                f"[向量库] SQLite 强制清理失败: {name}, error={str(sqlite_err)}"
            )

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
            if self._is_hnsw_corruption_error(e):
                logger.warning(f"[向量库] 查询遇到 HNSW 错误，尝试自动修复: {collection_name}, error={str(e)[:100]}")
                try:
                    # 清除缓存后通过 get_or_create_collection 自动修复（检测损坏→删除→重建）
                    self._clear_collection_cache(collection_name)
                    if self._client is None:
                        _ = self.client
                    if hasattr(self._client, 'clear_system_cache'):
                        self._client.clear_system_cache()
                    collection = self.get_or_create_collection(collection_name)
                    doc_count = collection.count()
                    if doc_count == 0:
                        # 🆕 标记该集合因HNSW损坏被重建为空，需要从KG JSON重新填充
                        self._repaired_empty.add(collection_name)
                        logger.warning(
                            f"[向量库] 集合已修复但为空（需从知识图谱JSON重建）: {collection_name}"
                        )
                        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
                                "_repaired_empty": True}
                    return collection.query(
                        query_texts=query_texts,
                        n_results=min(n_results, doc_count),
                        where=where
                    )
                except Exception as repair_error:
                    logger.warning(
                        f"[向量库] 自动修复失败（已返回空结果）: {collection_name}, "
                        f"error={str(repair_error)[:100]}"
                    )
                    return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            else:
                logger.error(f"[向量库] 查询失败: {collection_name}, error={str(e)}")
                raise

    def count_documents(self, collection_name: str) -> int:
        """获取文档数量"""
        collection = self.get_or_create_collection(collection_name)
        return collection.count()

    def health_check(self) -> dict:
        """健康检查：检测 ChromaDB 索引状态（HNSW 损坏自动标记）"""
        result = {"healthy": True, "collections": [], "errors": []}
        try:
            collections = self.client.list_collections()
            for coll in collections:
                try:
                    count = coll.count()
                    result["collections"].append({"name": coll.name, "count": count, "status": "ok"})
                except Exception as e:
                    result["healthy"] = False
                    error_type = (
                        "HNSW索引损坏" if self._is_hnsw_corruption_error(e)
                        else "未知错误"
                    )
                    result["collections"].append({
                        "name": coll.name,
                        "count": 0,
                        "status": "error",
                        "error_type": error_type,
                        "error": str(e)[:200]
                    })
                    result["errors"].append(
                        f"Collection '{coll.name}' [{error_type}]: {str(e)[:150]}"
                    )
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

    def is_repaired_empty(self, collection_name: str) -> bool:
        """检查集合是否因HNSW损坏被自动修复为空（需从KG JSON重建）"""
        return collection_name in self._repaired_empty

    def clear_repaired_flag(self, collection_name: str) -> None:
        """清除修复标志（重建完成后调用）"""
        self._repaired_empty.discard(collection_name)
