# -*- coding: utf-8 -*-
"""
向量数据库配置 - 嵌入函数模块

提供 ChromeDB 嵌入函数的初始化和环境配置。
"""
import os as _os
from app.core.logger import get_logger
from app.core.config import get_settings

logger = get_logger("vector_store")


def get_embedding_function():
    """
    获取嵌入函数(使用sentence-transformers,支持自定义模型缓存目录)

    相比ChromaDB默认的ONNX嵌入函数:
    - 支持自定义模型缓存目录(通过环境变量SENTENCE_TRANSFORMERS_HOME)
    - 更灵活的模型管理
    - 避免ONNX模型下载问题
    - 自动检测并重建已关闭的客户端
    """
    global _embedding_function

    # 检查现有实例是否仍然有效
    if _embedding_function is not None:
        try:
            # 尝试进行一次简单的向量生成来检测客户端是否可用
            _embedding_function(["测试"])
            return _embedding_function
        except Exception as e:
            error_msg = str(e).lower()
            # 检测客户端已关闭的错误
            if "closed" in error_msg or "client" in error_msg:
                logger.warning(f"[向量库] 检测到嵌入函数客户端已关闭,正在重建: {e}")
                _embedding_function = None  # 重置全局变量
            else:
                # 其他错误,直接返回现有实例
                logger.debug(f"[向量库] 嵌入函数健康检查异常: {e}")
                return _embedding_function

    # 初始化新的嵌入函数
    settings = get_settings()

    # 设置sentence-transformers模型缓存目录(必须在导入前设置)
    model_cache_dir = settings.get_chroma_model_cache_dir()
    _os.environ["SENTENCE_TRANSFORMERS_HOME"] = model_cache_dir

    # 设置HuggingFace镜像(国内加速)
    if settings.HF_ENDPOINT:
        _os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT

    logger.info(f"[向量库] 嵌入模型缓存目录: {model_cache_dir}")

    try:
        from chromadb.utils import embedding_functions
        # 创建sentence-transformers嵌入函数
        _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-small-zh-v1.5",
            device="cpu",
            normalize_embeddings=True
        )
        logger.info("[向量库] 嵌入函数初始化完成: BAAI/bge-small-zh-v1.5")
    except Exception as e:
        logger.error(f"[向量库] 嵌入函数初始化失败: {e}")
        try:
            from chromadb.utils import embedding_functions
            _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2",
                device="cpu"
            )
            logger.warning("[向量库] 使用回退模型: all-MiniLM-L6-v2")
        except Exception as fallback_error:
            logger.error(f"[向量库] 回退模型初始化也失败: {fallback_error}")
            raise

    return _embedding_function


def setup_chroma_environment():
    """设置 ChromaDB 环境变量（模型缓存目录等）

    必须在 ChromaDB 初始化前调用，确保所有模型缓存路径正确。
    """
    settings = get_settings()
    model_cache_dir = settings.get_chroma_model_cache_dir()

    _os.environ["CHROMA_MODEL_CACHE_DIR"] = model_cache_dir
    _os.environ["SENTENCE_TRANSFORMERS_HOME"] = model_cache_dir
    _os.environ["ORT_HOME"] = model_cache_dir

    if settings.HF_ENDPOINT:
        _os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
        _os.environ["HF_HUB_OFFLINE"] = "0"

    if settings.HTTPS_PROXY:
        _os.environ["HTTPS_PROXY"] = settings.HTTPS_PROXY
    if settings.HTTP_PROXY:
        _os.environ["HTTP_PROXY"] = settings.HTTP_PROXY

    logger.info(f"[向量库] 环境变量已设置: CHROMA_MODEL_CACHE_DIR={model_cache_dir}")


# 全局嵌入函数实例（延迟初始化）
_embedding_function = None
