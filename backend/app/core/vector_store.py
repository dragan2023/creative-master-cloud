"""
向量数据库配置
使用 ChromaDB 存储和检索向量数据

重要说明：
- ChromaDB 1.5.0 使用 PersistentClient 进行持久化
- HNSW 索引在内存中缓存，可能导致多进程/多实例数据不一致
- 需要在写入后验证数据完整性，确保数据正确持久化
"""
# [2026-03-27] 多Agent重构: Embedding模型从 all-MiniLM-L6-v2 升级为 BAAI/bge-small-zh-v1.5（中文优化）
# 使用pysqlite3替代系统sqlite（解决ChromaDB版本要求）- 必须在导入chromadb之前执行
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass  # 如果pysqlite3不可用，使用系统sqlite

# [关键] 在导入 chromadb 之前设置环境变量，确保 sentence-transformers 缓存目录正确
import os as _os
try:
    from app.core.config import get_settings as _get_settings
    _settings_module = _get_settings()
    _os.environ["SENTENCE_TRANSFORMERS_HOME"] = _settings_module.get_chroma_model_cache_dir()
    if _settings_module.HF_ENDPOINT:
        _os.environ["HF_ENDPOINT"] = _settings_module.HF_ENDPOINT
except Exception:
    pass  # 如果配置加载失败，使用默认值

# 标准库导入
import os
import asyncio
import time
import threading
from functools import wraps
from typing import Optional, List, Dict, Any

# 第三方库导入
import chromadb
from chromadb.utils import embedding_functions

# 本地模块导入
from app.core.logger import get_logger
from app.core.config import get_settings


logger = get_logger("vector_store")

# 全局嵌入函数实例（延迟初始化）
_embedding_function = None


def get_embedding_function():
    """
    获取嵌入函数（使用sentence-transformers，支持自定义模型缓存目录）

    相比ChromaDB默认的ONNX嵌入函数：
    - 支持自定义模型缓存目录（通过环境变量SENTENCE_TRANSFORMERS_HOME）
    - 更灵活的模型管理
    - 避免ONNX模型下载问题
    """
    global _embedding_function
    if _embedding_function is None:
        settings = get_settings()

        # 设置sentence-transformers模型缓存目录（必须在导入前设置）
        model_cache_dir = settings.get_chroma_model_cache_dir()
        os.environ["SENTENCE_TRANSFORMERS_HOME"] = model_cache_dir

        # 设置HuggingFace镜像（国内加速）
        if settings.HF_ENDPOINT:
            os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT

        logger.info(f"[向量库] 嵌入模型缓存目录: {model_cache_dir}")

        try:
            # 创建sentence-transformers嵌入函数
            # ChromaDB 1.5.0+ 不再支持 cache_folder 参数，改用环境变量
            _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-small-zh-v1.5",
                device="cpu",  # 使用CPU，确保兼容性
                normalize_embeddings=True  # 归一化向量，提高检索效果
            )

            logger.info("[向量库] 嵌入函数初始化完成: BAAI/bge-small-zh-v1.5")
        except Exception as e:
            logger.error(f"[向量库] 嵌入函数初始化失败: {e}")
            # 尝试使用默认模型作为回退
            try:
                _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2",
                    device="cpu"
                )
                logger.warning("[向量库] 使用回退模型: all-MiniLM-L6-v2")
            except Exception as fallback_error:
                logger.error(f"[向量库] 回退模型初始化也失败: {fallback_error}")
                raise

    return _embedding_function


def _setup_chroma_environment():
    """设置 ChromaDB 环境变量（模型缓存目录等）

    必须在 ChromaDB 初始化前调用，确保所有模型缓存路径正确。
    """
    settings = get_settings()

    # 设置模型缓存目录到项目文件夹
    model_cache_dir = settings.get_chroma_model_cache_dir()

    # ChromaDB ONNX 模型缓存目录（关键：必须在 ChromaDB 导入前设置）
    os.environ["CHROMA_MODEL_CACHE_DIR"] = model_cache_dir

    # sentence-transformers 模型缓存目录
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = model_cache_dir

    # ONNX Runtime 模型缓存（ChromaDB 内部使用）
    os.environ["ORT_HOME"] = model_cache_dir

    # 设置 HuggingFace 镜像（国内加速）
    if settings.HF_ENDPOINT:
        os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
        os.environ["HF_HUB_OFFLINE"] = "0"  # 允许在线下载

    # 设置代理（如果配置了）
    if settings.HTTPS_PROXY:
        os.environ["HTTPS_PROXY"] = settings.HTTPS_PROXY
    if settings.HTTP_PROXY:
        os.environ["HTTP_PROXY"] = settings.HTTP_PROXY

    logger.info(f"[向量库] 环境变量已设置: CHROMA_MODEL_CACHE_DIR={model_cache_dir}")


# 在模块加载时设置环境
_setup_chroma_environment()


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
        # 写入锁，确保串行化（支持多线程和多协程）
        self._write_lock = threading.Lock()
        self._async_write_lock = asyncio.Lock()
        # 重试配置
        self._max_retries = 3
        self._retry_delay = 1.0  # 秒
        # 验证配置
        self._verify_writes = True
        self._verify_delay = 0.1  # 写入后等待时间，确保数据持久化

    @property
    def client(self) -> chromadb.Client:
        """获取 ChromaDB 客户端（延迟初始化）"""
        if self._client is None:
            settings = get_settings()
            persist_dir = settings.get_chroma_dir()

            # 确保目录存在
            os.makedirs(persist_dir, exist_ok=True)

            # 使用新的 PersistentClient API (ChromaDB 1.0+)
            self._client = chromadb.PersistentClient(path=persist_dir)
        return self._client

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """
        获取或创建集合

        处理 embedding function 冲突：如果已存在的集合使用了不同的
        embedding function，会自动删除旧集合并重新创建。

        Args:
            name: 集合名称

        Returns:
            Collection 实例
        """
        if name not in self._collections:
            # 使用自定义嵌入函数（支持自定义模型缓存目录）
            embedding_func = get_embedding_function()

            try:
                # 首先尝试获取已存在的集合（不传 embedding_function）
                # 这样可以避免与已存在的集合发生 embedding function 冲突
                existing = self.client.get_collection(name=name)
                # 如果成功获取，检查是否有数据
                count = existing.count()
                if count > 0:
                    # 集合存在且有数据，直接使用
                    self._collections[name] = existing
                    logger.debug(f"[向量库] 使用已存在的集合: {name}, 文档数: {count}")
                    return existing
                # 集合存在但无数据，可以安全删除重建
                self.client.delete_collection(name=name)
                logger.info(f"[向量库] 删除空集合以便重建: {name}")
            except Exception as e:
                # 集合不存在或其他错误，继续创建新集合
                logger.debug(f"[向量库] 获取集合失败，将创建新集合: {name}, 原因: {e}")

            try:
                # 创建新集合（使用自定义 embedding function）
                self._collections[name] = self.client.create_collection(
                    name=name,
                    embedding_function=embedding_func,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"[向量库] 创建新集合: {name}")
            except Exception as create_error:
                # 如果创建失败，尝试不传 embedding_function
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
        """
        删除集合

        Args:
            name: 集合名称
        """
        try:
            self.client.delete_collection(name=name)
            if name in self._collections:
                del self._collections[name]
        except Exception as e:
            logger.warning(f"删除集合失败: {e}")
            pass

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        verify: bool = True
    ) -> Dict[str, Any]:
        """
        添加文档到向量数据库（带重试机制和写入验证）

        Args:
            collection_name: 集合名称
            documents: 文档列表
            metadatas: 元数据列表
            ids: 文档ID列表
            verify: 是否验证写入结果

        Returns:
            {"success": bool, "count": int, "verified": bool, "error": str|None}
        """
        import uuid

        result = {
            "success": False,
            "count": 0,
            "verified": False,
            "error": None
        }

        if not documents:
            result["success"] = True
            return result

        # 使用线程锁确保写入串行化
        with self._write_lock:
            collection = self.get_or_create_collection(collection_name)

            if ids is None:
                ids = [str(uuid.uuid4()) for _ in documents]

            # 清理 metadata，确保所有值都是 ChromaDB 支持的类型
            # ChromaDB 只支持 str, int, float, bool，不支持 None
            cleaned_metadatas = None
            if metadatas:
                cleaned_metadatas = []
                for meta in metadatas:
                    cleaned_meta = {}
                    for key, value in meta.items():
                        if value is None:
                            # None 转换为空字符串
                            cleaned_meta[key] = ""
                        elif isinstance(value, (str, int, float, bool)):
                            cleaned_meta[key] = value
                        else:
                            # 其他类型转换为字符串
                            cleaned_meta[key] = str(value)
                    cleaned_metadatas.append(cleaned_meta)

            # 带重试的写入
            last_error = None
            for attempt in range(self._max_retries):
                try:
                    collection.add(
                        documents=documents,
                        metadatas=cleaned_metadatas,
                        ids=ids
                    )

                    # 写入后等待，确保数据持久化
                    if self._verify_delay > 0:
                        time.sleep(self._verify_delay)

                    # 验证写入结果
                    if verify and self._verify_writes:
                        verified = self._verify_write(
                            collection, ids, len(documents))
                        if not verified:
                            logger.warning(
                                f"[向量库] 写入验证失败，重试中: collection={collection_name}, "
                                f"attempt={attempt + 1}/{self._max_retries}"
                            )
                            # 清除缓存，重新获取集合
                            self._clear_collection_cache(collection_name)
                            collection = self.get_or_create_collection(
                                collection_name)
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
                        logger.debug(
                            f"[向量库] 写入成功: collection={collection_name}, count={len(documents)}"
                        )
                    return result

                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()

                    # 检查是否是 HNSW 索引错误或 SQLite 锁定错误
                    if any(err in error_msg for err in ["hnsw", "compaction", "index", "locked", "busy", "timeout"]):
                        logger.warning(
                            f"[向量库] 写入错误（第{attempt + 1}次尝试）: {str(e)[:100]}"
                        )
                        if attempt < self._max_retries - 1:
                            # 等待后重试
                            time.sleep(self._retry_delay * (attempt + 1))
                            # 清除缓存，重新获取集合
                            self._clear_collection_cache(collection_name)
                            try:
                                collection = self.get_or_create_collection(
                                    collection_name)
                            except Exception as e:
                                logger.warning(f"重建集合失败: {e}")
                                pass
                            continue
                    else:
                        # 非索引错误，直接抛出
                        logger.error(f"[向量库] 写入失败: {str(e)}")
                        result["error"] = str(e)
                        raise

            # 所有重试都失败
            logger.error(
                f"[向量库] 写入失败（已重试{self._max_retries}次）: collection={collection_name}, error={last_error}"
            )
            result["error"] = str(last_error)
            raise last_error

    def _verify_write(
        self,
        collection: chromadb.Collection,
        ids: List[str],
        expected_count: int
    ) -> bool:
        """
        验证写入是否成功

        通过检查文档数量和ID是否存在来验证

        Args:
            collection: 集合对象
            ids: 写入的文档ID列表
            expected_count: 期望的文档数量

        Returns:
            是否验证成功
        """
        try:
            # 检查文档数量
            actual_count = collection.count()
            if actual_count < expected_count:
                logger.warning(
                    f"[向量库] 验证失败: 文档数量不足, expected>={expected_count}, actual={actual_count}"
                )
                return False

            # 检查ID是否存在（采样检查，避免全量查询）
            sample_size = min(5, len(ids))
            sample_ids = ids[:sample_size]

            try:
                result = collection.get(ids=sample_ids, include=[])
                if len(result.get("ids", [])) != sample_size:
                    logger.warning(
                        f"[向量库] 验证失败: 部分ID不存在, "
                        f"expected={sample_size}, found={len(result.get('ids', []))}"
                    )
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
        """
        清除集合缓存

        当遇到写入问题或需要重新加载集合时调用
        """
        if collection_name in self._collections:
            del self._collections[collection_name]
            logger.debug(f"[向量库] 已清除集合缓存: {collection_name}")

    def clear_all_caches(self) -> None:
        """
        清除所有缓存

        当遇到数据不一致问题时调用，强制重新加载所有集合
        """
        self._collections.clear()
        logger.info("[向量库] 已清除所有集合缓存")

    def clear_system_cache(self) -> bool:
        """
        清除 ChromaDB 系统缓存

        解决多进程/多实例数据不一致问题
        参考: https://github.com/chroma-core/chroma/issues/2536

        Returns:
            是否成功
        """
        try:
            # ChromaDB 1.5.0 的 PersistentClient 支持 clear_system_cache
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
        """
        异步添加文档到向量数据库（带串行化和重试机制）

        使用异步锁确保写入操作串行化，避免并发写入导致的索引冲突。

        Args:
            collection_name: 集合名称
            documents: 文档列表
            metadatas: 元数据列表
            ids: 文档ID列表
            verify: 是否验证写入结果

        Returns:
            {"success": bool, "count": int, "verified": bool, "error": str|None}
        """
        async with self._async_write_lock:
            # 在异步上下文中执行同步写入
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.add_documents(
                    collection_name, documents, metadatas, ids, verify
                )
            )
            return result

    def query(
        self,
        collection_name: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[dict] = None
    ) -> dict:
        """
        查询相似文档

        Args:
            collection_name: 集合名称
            query_texts: 查询文本列表
            n_results: 返回结果数量
            where: 过滤条件

        Returns:
            查询结果
        """
        try:
            collection = self.get_or_create_collection(collection_name)

            # 检查集合是否为空
            doc_count = collection.count()
            if doc_count == 0:
                logger.debug(f"[向量库] 集合为空，跳过查询: {collection_name}")
                return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

            return collection.query(
                query_texts=query_texts,
                n_results=min(n_results, doc_count),  # 确保不超过实际文档数
                where=where
            )
        except Exception as e:
            error_msg = str(e).lower()
            # 处理 HNSW 索引错误和其他 ChromaDB 内部错误
            if ("hnsw" in error_msg or
                "nothing found on disk" in error_msg or
                "error finding id" in error_msg or
                "internal error" in error_msg or
                    "error executing plan" in error_msg):
                logger.warning(
                    f"[向量库] 查询遇到内部错误，返回空结果: {collection_name}, error={str(e)[:100]}")
                # 返回空结果而不是抛出异常
                return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            else:
                logger.error(f"[向量库] 查询失败: {collection_name}, error={str(e)}")
                raise

    def count_documents(self, collection_name: str) -> int:
        """
        获取文档数量

        Args:
            collection_name: 集合名称

        Returns:
            文档数量
        """
        collection = self.get_or_create_collection(collection_name)
        return collection.count()

    def health_check(self) -> dict:
        """
        健康检查：检测 ChromaDB 索引状态

        Returns:
            健康状态报告
        """
        result = {
            "healthy": True,
            "collections": [],
            "errors": []
        }

        try:
            # 获取所有集合
            collections = self.client.list_collections()

            for coll in collections:
                try:
                    # 尝试查询以检测索引是否正常
                    count = coll.count()
                    result["collections"].append({
                        "name": coll.name,
                        "count": count,
                        "status": "ok"
                    })
                except Exception as e:
                    result["healthy"] = False
                    result["collections"].append({
                        "name": coll.name,
                        "count": 0,
                        "status": "error",
                        "error": str(e)[:100]
                    })
                    result["errors"].append(
                        f"Collection '{coll.name}': {str(e)[:100]}")

        except Exception as e:
            result["healthy"] = False
            result["errors"].append(f"Client error: {str(e)[:100]}")

        return result

    def repair_collection(self, collection_name: str) -> bool:
        """
        修复损坏的集合

        通过删除并重建集合来修复索引问题。

        Args:
            collection_name: 集合名称

        Returns:
            是否修复成功
        """
        try:
            logger.info(f"[向量库] 开始修复集合: {collection_name}")

            # 删除损坏的集合
            self.delete_collection(collection_name)

            # 重新创建集合
            self.get_or_create_collection(collection_name)

            logger.info(f"[向量库] 集合修复成功: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"[向量库] 集合修复失败: {collection_name}, error={str(e)}")
            return False

    def repair_all_collections(self) -> dict:
        """
        修复所有损坏的集合

        Returns:
            修复报告
        """
        report = {
            "checked": 0,
            "repaired": 0,
            "failed": 0,
            "details": []
        }

        health = self.health_check()

        for coll_info in health["collections"]:
            report["checked"] += 1

            if coll_info.get("status") == "error":
                if self.repair_collection(coll_info["name"]):
                    report["repaired"] += 1
                    report["details"].append({
                        "name": coll_info["name"],
                        "action": "repaired",
                        "success": True
                    })
                else:
                    report["failed"] += 1
                    report["details"].append({
                        "name": coll_info["name"],
                        "action": "repair_failed",
                        "success": False
                    })

        logger.info(
            f"[向量库] 修复完成: 检查={report['checked']}, "
            f"修复={report['repaired']}, 失败={report['failed']}"
        )

        return report


# 全局向量存储实例
vector_store = VectorStore()


def get_vector_store() -> VectorStore:
    """获取向量存储实例"""
    return vector_store
