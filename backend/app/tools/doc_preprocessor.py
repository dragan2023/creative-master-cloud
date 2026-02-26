"""
文档预处理器模块
构建三层预处理流水线：Cleaner -> Filter -> Refiner
优化 GraphRAG 的输入质量，降低 Token 消耗并提升知识图谱准确性
"""
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import os
import re
import asyncio

from app.core.logger import get_logger
from app.core.config import get_settings


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

# 摘要压缩提示词
SUMMARIZATION_PROMPT = """请将以下内容浓缩为"事实清单"格式，保留所有关键信息，去除冗余描述：

{text}

要求：
1. 保留所有实体名称、数值、时间等关键信息
2. 保留因果关系和逻辑链条
3. 使用简洁的陈述句
4. 输出为JSON数组格式

事实清单：
["事实1", "事实2", ...]

请直接输出JSON数组，不要其他说明："""


class DocumentPreprocessor:
    """
    文档预处理器

    三层流水线架构：
    1. Cleaner 层 (Marker): 将 PDF/DOCX 转换为标准 Markdown
    2. Filter 层 (Regex): 剔除无意义内容
    3. Refiner 层 (Chonkie): 语义切片，确保每个 Chunk 信息丰富
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.logger = get_logger("doc_preprocessor")

        # 检测GPU可用性
        self._detect_and_setup_gpu()

        # 静默设置 Marker 模型目录环境变量（必须在导入 marker 之前）
        marker_model_dir = self.settings.get_marker_model_dir()
        os.environ["MARKER_MODEL_DIR"] = marker_model_dir
        os.environ["TORCH_HOME"] = marker_model_dir
        os.environ["TRANSFORMERS_CACHE"] = marker_model_dir
        os.environ["HUGGINGFACE_HUB_CACHE"] = marker_model_dir

        # 静默设置 Chonkie 模型缓存目录（使用 marker_models 目录）
        chonkie_model_dir = marker_model_dir  # 复用 marker_models 目录
        # 设置环境变量，让 transformers 使用本地模型目录
        os.environ["HF_HOME"] = chonkie_model_dir
        os.environ["TRANSFORMERS_CACHE"] = chonkie_model_dir

        # 设置 Hugging Face 镜像（默认使用国内镜像）
        hf_endpoint = os.getenv(
            "HF_ENDPOINT") or self.settings.HF_ENDPOINT or "https://hf-mirror.com"
        os.environ["HF_ENDPOINT"] = hf_endpoint
        self.logger.info(f"使用 Hugging Face 镜像: {hf_endpoint}")

        # 精简 Hugging Face 下载日志输出
        # 设置日志级别为 warning，减少进度条等冗余信息
        os.environ["HF_HUB_VERBOSITY"] = "warning"
        # 禁用 tqdm 进度条的详细输出（保留基本状态）
        os.environ["TQDM_MININTERVAL"] = "5"  # 每5秒更新一次进度
        # 静默 huggingface_hub 的日志输出
        import logging
        logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("filelock").setLevel(logging.WARNING)

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

        # 延迟加载的组件
        self._marker_converter = None
        self._semantic_chunker = None

    def _detect_and_setup_gpu(self):
        """检测并设置GPU加速 - 带详细诊断信息"""
        try:
            import torch

            # ========== GPU 诊断信息 ==========
            self.logger.info("=" * 50)
            self.logger.info("GPU 环境诊断开始")
            self.logger.info("=" * 50)

            # PyTorch 版本信息
            self.logger.info(f"PyTorch 版本: {torch.__version__}")

            # 检查是否为 GPU 版本的 PyTorch
            torch_cuda_version = getattr(torch.version, 'cuda', None)
            if torch_cuda_version:
                self.logger.info(f"PyTorch CUDA 版本: {torch_cuda_version}")
            else:
                self.logger.warning("PyTorch 未编译 CUDA 支持（可能是 CPU 版本）")

            # 检查 CUDA 是否可用
            cuda_available = torch.cuda.is_available()
            self.logger.info(f"torch.cuda.is_available(): {cuda_available}")

            if cuda_available:
                # GPU 检测成功
                gpu_count = torch.cuda.device_count()
                self.logger.info(f"检测到 {gpu_count} 个 GPU 设备")

                for i in range(gpu_count):
                    gpu_name = torch.cuda.get_device_name(i)
                    gpu_memory = torch.cuda.get_device_properties(
                        i).total_memory / (1024**3)
                    self.logger.info(
                        f"  GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")

                # 选择 GPU
                device_id = min(self.settings.GPU_DEVICE_ID, gpu_count - 1)
                self.device = f"cuda:{device_id}"
                selected_gpu_name = torch.cuda.get_device_name(device_id)

                self.logger.info(f"选择使用 GPU {device_id}: {selected_gpu_name}")
                self.logger.info("GPU 加速已启用")
                self.logger.info("=" * 50)

                # Marker 官方推荐的环境变量设置
                # TORCH_DEVICE 必须是 "cuda"，不是 "cuda:0"
                os.environ["TORCH_DEVICE"] = "cuda"
                os.environ["CUDA_VISIBLE_DEVICES"] = str(device_id)

                # PyTorch 内存管理优化
                os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
            else:
                # ========== CUDA 不可用 - 详细诊断 ==========
                self.logger.warning("CUDA 不可用，开始详细诊断...")

                # 诊断 1: 检查是否安装了 GPU 版本的 PyTorch
                if torch_cuda_version is None:
                    self.logger.error("诊断结果: 安装的是 CPU 版本的 PyTorch")
                    self.logger.error("解决方案: 请重新安装 GPU 版本:")
                    self.logger.error("  pip uninstall torch")
                    self.logger.error(
                        "  pip install torch --index-url https://download.pytorch.org/whl/cu126")
                else:
                    self.logger.info(
                        f"PyTorch 编译了 CUDA {torch_cuda_version} 支持")

                # 诊断 2: 检查 NVIDIA 驱动
                try:
                    import subprocess
                    result = subprocess.run(
                        ['nvidia-smi'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.logger.info("nvidia-smi 检测成功，NVIDIA 驱动已安装")
                        # 解析驱动版本
                        for line in result.stdout.split('\n')[:5]:
                            if 'Driver Version' in line:
                                self.logger.info(f"  {line.strip()}")
                                break
                    else:
                        self.logger.warning("nvidia-smi 返回错误，可能驱动有问题")
                except FileNotFoundError:
                    self.logger.error("诊断结果: nvidia-smi 未找到，NVIDIA 驱动可能未安装")
                except Exception as e:
                    self.logger.warning(f"nvidia-smi 检测失败: {e}")

                # 诊断 3: 检查 CUDA_HOME 环境变量
                cuda_home = os.environ.get(
                    'CUDA_HOME') or os.environ.get('CUDA_PATH')
                if cuda_home:
                    self.logger.info(f"CUDA_HOME: {cuda_home}")
                else:
                    self.logger.warning("CUDA_HOME 环境变量未设置（可选）")

                # 诊断 4: 检查 nvcc
                try:
                    result = subprocess.run(
                        ['nvcc', '--version'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.logger.info(
                            f"nvcc 检测成功:\n  {result.stdout.strip()}")
                    else:
                        self.logger.warning("nvcc 返回错误")
                except FileNotFoundError:
                    self.logger.warning(
                        "nvcc 未找到（CUDA Toolkit 可能未安装或未加入 PATH）")
                except Exception as e:
                    self.logger.warning(f"nvcc 检测失败: {e}")

                self.logger.info("=" * 50)

                # 根据配置决定是否报错
                if getattr(self.settings, 'FORCE_GPU', False):
                    self.logger.error("=" * 50)
                    self.logger.error("GPU 检测失败！")
                    self.logger.error("FORCE_GPU=True，但无法使用 GPU 加速。")
                    self.logger.error("请检查上述诊断信息，确认问题原因。")
                    self.logger.error("=" * 50)
                    raise RuntimeError(
                        "GPU 检测失败，详细诊断信息已输出到日志。\n"
                        "常见原因:\n"
                        "1. 安装了 CPU 版本的 PyTorch\n"
                        "2. NVIDIA 驱动未安装或版本过旧\n"
                        "3. PyTorch CUDA 版本与系统 CUDA 版本不匹配\n\n"
                        "解决方案:\n"
                        "1. 重新安装 GPU 版本 PyTorch:\n"
                        "   pip uninstall torch\n"
                        "   pip install torch --index-url https://download.pytorch.org/whl/cu126\n\n"
                        "2. 或在 .env 文件中设置 FORCE_GPU=False 使用 CPU 模式"
                    )

                # 降级到 CPU
                self.logger.warning("降级到 CPU 模式运行")
                self.device = "cpu"
                os.environ["TORCH_DEVICE"] = "cpu"

        except ImportError:
            self.logger.error("无法导入 torch 模块")
            if getattr(self.settings, 'FORCE_GPU', False):
                raise RuntimeError(
                    "FORCE_GPU=True 但无法导入 PyTorch。\n"
                    "请安装 PyTorch:\n"
                    "  pip install torch --index-url https://download.pytorch.org/whl/cu126"
                )
            self.device = "cpu"
            os.environ["TORCH_DEVICE"] = "cpu"
        except OSError as e:
            # DLL 加载失败（通常是 CUDA 版本不匹配）
            error_str = str(e).lower()
            self.logger.error(f"PyTorch DLL 加载失败: {str(e)}")

            if "caffe2_nvrtc.dll" in error_str or "nvrtc" in error_str or "cuda" in error_str:
                self.logger.error("=" * 50)
                self.logger.error("CUDA 运行时库加载失败！")
                self.logger.error("这通常是因为 PyTorch CUDA 版本与系统 CUDA 版本不匹配。")
                self.logger.error("=" * 50)

                if getattr(self.settings, 'FORCE_GPU', False):
                    raise RuntimeError(
                        "CUDA 运行时库加载失败。\n\n"
                        "原因：PyTorch CUDA 版本与系统 CUDA 版本不匹配。\n\n"
                        "解决方案：\n"
                        "1. 重新安装匹配的 PyTorch 版本（推荐）：\n"
                        "   pip uninstall torch torchvision torchaudio\n"
                        "   pip install torch --index-url https://download.pytorch.org/whl/cu126\n\n"
                        "2. 或在 .env 文件中设置 FORCE_GPU=False 使用 CPU 模式\n\n"
                        "3. 运行项目根目录的 check-gpu.py 获取详细诊断信息"
                    )
            else:
                if getattr(self.settings, 'FORCE_GPU', False):
                    raise RuntimeError(
                        f"PyTorch DLL 加载失败: {str(e)}\n\n"
                        "解决方案：\n"
                        "1. 重新安装 PyTorch:\n"
                        "   pip uninstall torch torchvision torchaudio\n"
                        "   pip install torch --index-url https://download.pytorch.org/whl/cu126\n\n"
                        "2. 或在 .env 文件中设置 FORCE_GPU=False 使用 CPU 模式"
                    )

            self.logger.warning("降级到 CPU 模式运行")
            self.device = "cpu"
            os.environ["TORCH_DEVICE"] = "cpu"
        except Exception as e:
            self.logger.error(f"GPU 设置过程中发生错误: {str(e)}")
            if getattr(self.settings, 'FORCE_GPU', False):
                raise RuntimeError(f"FORCE_GPU=True 但 GPU 设置失败: {str(e)}")
            self.device = "cpu"
            os.environ["TORCH_DEVICE"] = "cpu"

        # 支持的文件扩展名
        self.supported_extensions = {".pdf", ".docx", ".doc", ".txt", ".md"}

    def _refresh_config(self):
        """动态刷新配置（每次处理时调用）"""
        # 重新获取 settings 以获取最新配置
        self.settings = get_settings()
        self.enable_marker = self.settings.MARKER_ENABLED
        self.enable_filter = True  # 默认启用过滤
        self.enable_semantic_chunk = self.settings.SEMANTIC_CHUNK_ENABLED
        self.enable_summarization = self.settings.SUMMARIZATION_ENABLED

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

            if self.enable_marker and ext in [".pdf", ".docx", ".doc"]:
                text = await self._clean_with_marker(file_path)
            else:
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

            # Step 3: Refiner - 语义切片
            if progress_callback:
                progress_callback("正在进行语义切片...", 25, 3)

            if self.enable_semantic_chunk:
                chunks = await self._semantic_chunk(text)
            else:
                chunks = self._fallback_chunk(text)

            # Step 4: 可选 - 摘要压缩
            if self.enable_summarization:
                if progress_callback:
                    progress_callback("正在压缩内容...", 35, 4)
                chunks = await self._summarize_chunks(chunks, llm_provider)
                stats["steps_completed"].append("summarization")

            stats["chunk_count"] = len(chunks)
            stats["steps_completed"].append("refiner")

            return {
                "chunks": chunks,
                "metadata": {
                    "file_path": file_path,
                    "file_type": ext.lstrip("."),
                    "preprocessor_enabled": True,
                    "marker_used": self.enable_marker and ext in [".pdf", ".docx", ".doc"],
                    "semantic_chunk_used": self.enable_semantic_chunk,
                    "summarization_used": self.enable_summarization
                },
                "stats": stats
            }

        except Exception as e:
            self.logger.error(f"文档预处理失败: {str(e)}")
            # 尝试回退到基本解析
            return await self._fallback_process(file_path, str(e))

    async def _clean_with_marker(self, file_path: str) -> str:
        """
        Cleaner层：使用 Marker 将文档转换为 Markdown

        Marker 特点：
        - 高质量 PDF/DOCX 转 Markdown
        - 保留表格、公式、代码块结构
        - 自动去除页眉页脚
        """
        try:
            # 延迟导入（marker-pdf 是可选依赖）
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            from marker.output import text_from_rendered

            # 设置代理（如果配置了）
            if self.settings.HTTP_PROXY:
                os.environ["HTTP_PROXY"] = self.settings.HTTP_PROXY
            if self.settings.HTTPS_PROXY:
                os.environ["HTTPS_PROXY"] = self.settings.HTTPS_PROXY

            # 延迟初始化 Marker 转换器
            if self._marker_converter is None:
                self.logger.info("正在初始化 Marker 模型...")
                try:
                    # Marker 会自动读取 TORCH_DEVICE 环境变量
                    self._marker_converter = PdfConverter(
                        artifact_dict=create_model_dict()
                    )
                    self.logger.info("Marker 模型初始化完成")
                except Exception as init_error:
                    self.logger.warning(f"Marker 初始化失败: {init_error}，使用基本解析")
                    return await self._parse_with_fallback(file_path)

            # 执行转换
            try:
                rendered = self._marker_converter(file_path)
                text, _, images = text_from_rendered(rendered)
                return text
            except Exception as convert_error:
                error_msg = str(convert_error)
                # 检测 GPU 内存错误
                if "out of memory" in error_msg.lower():
                    self.logger.warning(
                        f"GPU 显存不足，尝试清理缓存后重试: {error_msg[:100]}")
                    # 清理 GPU 缓存并重试
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                            import gc
                            gc.collect()
                            # 重试一次
                            rendered = self._marker_converter(file_path)
                            text, _, images = text_from_rendered(rendered)
                            return text
                    except Exception as retry_error:
                        self.logger.warning(f"重试失败: {str(retry_error)[:100]}")
                elif "cuda" in error_msg.lower() or "device" in error_msg.lower():
                    self.logger.warning(f"GPU 设备错误，回退到 CPU: {error_msg[:100]}")
                else:
                    self.logger.warning(f"Marker 转换失败: {error_msg[:100]}")
                return await self._parse_with_fallback(file_path)

        except ImportError:
            self.logger.info("marker-pdf 未安装，使用基本PDF解析")
            return await self._parse_with_fallback(file_path)
        except OSError as dll_error:
            # DLL 加载失败（通常是 CUDA 版本不匹配或依赖缺失）
            error_str = str(dll_error).lower()
            if "onnxruntime" in error_str or "dll" in error_str:
                self.logger.warning(f"DLL 加载失败，可能缺少依赖: {str(dll_error)[:100]}")
                self.logger.warning(
                    "建议安装 onnxruntime: pip install onnxruntime")
            else:
                self.logger.warning(f"系统依赖缺失: {str(dll_error)[:100]}")
            return await self._parse_with_fallback(file_path)
        except Exception as e:
            self.logger.warning(f"Marker 转换跳过: {str(e)[:100]}，使用基本解析")
            return await self._parse_with_fallback(file_path)

    async def _parse_with_fallback(self, file_path: str) -> str:
        """回退解析方法：使用 pypdf 或 python-docx"""
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
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()

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

    async def _semantic_chunk(self, text: str) -> List[str]:
        """
        Refiner层：语义切片

        使用 Chonkie SemanticChunker 基于语义相似度划分文本边界
        确保每个 Chunk 都是信息丰富的"干货"
        """
        try:
            # 检查 onnxruntime 是否真正可用（chonkie 语义切片必需）
            # 注意：onnxruntime 包可能存在但 DLL 依赖缺失，需要实际加载测试
            try:
                import onnxruntime
                # 尝试获取版本号，这会触发实际的 DLL 加载
                _ = onnxruntime.__version__
                self.logger.debug(f"onnxruntime 版本: {onnxruntime.__version__}")
            except ImportError:
                self.logger.warning("onnxruntime 未安装，语义切片需要此依赖")
                self.logger.info("跳过语义切片，使用固定大小切片")
                return self._fallback_chunk(text)
            except OSError as dll_error:
                # DLL 加载失败（缺少 Visual C++ Redistributable 等）
                self.logger.warning(
                    f"onnxruntime DLL 加载失败: {str(dll_error)[:100]}")
                self.logger.warning(
                    "可能缺少 Visual C++ Redistributable，请安装: https://aka.ms/vs/17/release/vc_redist.x64.exe")
                self.logger.info("跳过语义切片，使用固定大小切片")
                return self._fallback_chunk(text)
            except Exception as e:
                self.logger.warning(f"onnxruntime 加载异常: {str(e)[:100]}")
                self.logger.info("跳过语义切片，使用固定大小切片")
                return self._fallback_chunk(text)

            # 延迟导入（chonkie 是可选依赖）
            from chonkie import SemanticChunker

            # 延迟初始化语义切片器
            if self._semantic_chunker is None:
                self._semantic_chunker = SemanticChunker(
                    embedding_model="minishlab/potion-base-32M",  # 轻量级嵌入模型
                    threshold=self.settings.SEMANTIC_THRESHOLD,
                    chunk_size=self.settings.SEMANTIC_CHUNK_SIZE,
                    similarity_window=3,
                    min_sentences_per_chunk=2,
                    min_characters_per_sentence=20
                )

            # 执行语义切片
            chunks = self._semantic_chunker.chunk(text)
            result = [chunk.text for chunk in chunks]

            return result

        except ImportError as e:
            self.logger.info(f"chonkie 未安装，使用固定大小切片: {str(e)[:50]}")
            return self._fallback_chunk(text)
        except OSError as e:
            # DLL 加载失败等系统错误
            self.logger.warning(f"语义切片系统错误: {str(e)[:100]}")
            self.logger.info("跳过语义切片，使用固定大小切片")
            return self._fallback_chunk(text)
        except ValueError as e:
            # chonkie 内部检测到 onnxruntime 问题时抛出 ValueError
            error_msg = str(e).lower()
            if "onnxruntime" in error_msg or "onnx" in error_msg:
                self.logger.warning(
                    f"chonkie 检测到 onnxruntime 问题: {str(e)[:100]}")
                self.logger.warning(
                    "可能原因: 1) onnxruntime 未安装 2) DLL 依赖缺失 3) Python 版本不兼容")
                self.logger.info("跳过语义切片，使用固定大小切片")
            else:
                self.logger.warning(f"语义切片值错误: {str(e)[:100]}")
            return self._fallback_chunk(text)
        except Exception as e:
            error_msg = str(e).lower()
            if "onnxruntime" in error_msg or "onnx" in error_msg:
                self.logger.warning(f"onnxruntime 相关错误: {str(e)[:100]}")
                self.logger.warning("建议执行: pip install onnxruntime")
            else:
                self.logger.warning(f"语义切片跳过: {str(e)[:100]}")
            self.logger.info("使用固定大小切片作为降级方案")
            return self._fallback_chunk(text)

    def _fallback_chunk(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """回退切片方法：固定大小切片"""
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

    async def _summarize_chunks(self, chunks: List[str], llm_provider=None) -> List[str]:
        """
        可选：摘要压缩

        将长文本块压缩为"事实清单"格式
        降低 50%+ Token 消耗
        """
        if not llm_provider:
            self.logger.warning("未提供 LLM 提供者，跳过摘要压缩")
            return chunks

        summarized = []
        for chunk in chunks:
            # 只对较长的 chunk 进行压缩
            if len(chunk) < 500:
                summarized.append(chunk)
                continue

            try:
                prompt = SUMMARIZATION_PROMPT.format(text=chunk)
                response = await llm_provider.generate(prompt, temperature=0.3, max_tokens=1000)

                # 解析 JSON 响应
                import json
                try:
                    facts = json.loads(response.content)
                    if isinstance(facts, list):
                        summarized.append("\n".join(f"- {f}" for f in facts))
                    else:
                        summarized.append(chunk)
                except:
                    summarized.append(chunk)

            except Exception as e:
                self.logger.warning(f"摘要压缩失败: {str(e)}")
                summarized.append(chunk)

        return summarized

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
