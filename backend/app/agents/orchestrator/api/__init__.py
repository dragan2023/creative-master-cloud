"""Agent编排器 - API层（数据类、常量、模块函数）"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, Any, Optional, List
import base64
import mimetypes
import os
from app.core.config import PRESET_MODELS, get_settings
from app.tools.file_parser import get_file_parser

@dataclass
class GenerateStreamContext:
    """流式生成过程中的上下文数据"""
    # LLM相关
    llm_provider: Any = None
    model_display_name: str = ""

    # 提示词相关
    system_prompt: str = ""
    full_prompt: str = ""

    # 输入参数
    input_params: Dict[str, Any] = field(default_factory=dict)

    # 知识库上下文
    kb_contexts: Dict[str, str] = field(default_factory=lambda: {
        "theory": "", "case": "", "user_specific": "", "manual": ""
    })

    # 生成内容
    first_draft: str = ""
    final_content: str = ""

    # 时间相关
    start_time: float = 0.0

    # 多模态
    converted_images: Optional[List[str]] = None
    videos: Optional[List[str]] = None

def convert_images_to_base64(images: Optional[List[str]]) -> Optional[List[str]]:
    """
    将图片URL列表转换为base64编码格式

    Args:
        images: 图片URL列表，支持：
            - 相对路径（如 /api/v1/generate/uploads/xxx.png）
            - 完整URL（如 http://xxx/yyy.png）
            - 已经是base64格式（如 data:image/png;base64,xxx）

    Returns:
        转换后的图片URL列表（全部为 data:image/xxx;base64,yyy 格式）
    """
    if not images:
        return None

    settings = get_settings()
    upload_dir = settings.get_upload_dir()
    result = []

    for img_url in images:
        # 已经是base64格式，直接使用
        if img_url.startswith("data:image"):
            result.append(img_url)
            continue

        # 完整URL（http/https），直接使用（LLM可以访问）
        if img_url.startswith("http://") or img_url.startswith("https://"):
            result.append(img_url)
            continue

        # 相对路径，需要转换为base64
        if img_url.startswith("/api/v1/generate/uploads/"):
            # 提取文件名
            filename = img_url.split("/")[-1]
            file_path = os.path.join(upload_dir, filename)

            if os.path.exists(file_path):
                # 读取文件并转换为base64
                with open(file_path, "rb") as f:
                    image_data = f.read()

                # 获取MIME类型
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = "image/png"  # 默认

                base64_data = base64.b64encode(image_data).decode("utf-8")
                result.append(f"data:{mime_type};base64,{base64_data}")
            else:
                # 文件不存在，跳过
                continue
        else:
            # 其他格式，尝试作为相对路径处理
            result.append(img_url)

    return result if result else None

async def convert_file_url_to_content(file_url: Optional[str], logger=None) -> Optional[str]:
    """
    将文件URL转换为文件内容文本

    Args:
        file_url: 文件URL，支持：
            - 相对路径（如 /api/v1/generate/uploads/xxx.pdf）
            - 完整URL（如 http://xxx/yyy.docx）
            - 本地文件路径
        logger: 日志记录器

    Returns:
        文件内容文本，如果无法读取则返回原始URL
    """
    if not file_url:
        return None

    settings = get_settings()
    upload_dir = settings.get_upload_dir()
    file_parser = get_file_parser()

    if logger:
        logger.info(f"[文件解析] 开始解析文件URL: {file_url}")
        logger.info(f"[文件解析] 上传目录: {upload_dir}")

    # 确定文件路径
    file_path = None

    # 相对路径（如 /api/v1/generate/uploads/xxx.pdf）
    if file_url.startswith("/api/v1/generate/uploads/"):
        filename = file_url.split("/")[-1]
        file_path = os.path.join(upload_dir, filename)
        if logger:
            logger.info(f"[文件解析] 解析后的文件路径: {file_path}")
    # 完整URL（http/https）- 不支持远程文件，返回原始URL
    elif file_url.startswith("http://") or file_url.startswith("https://"):
        if logger:
            logger.warning(f"远程文件URL不支持解析: {file_url}")
        return file_url  # 返回原始URL，让提示词模板中使用URL
    # 本地文件路径
    elif os.path.exists(file_url):
        file_path = file_url
    else:
        if logger:
            logger.warning(f"文件不存在: {file_url}")
        return file_url

    # 检查文件是否存在
    if not file_path:
        if logger:
            logger.warning(f"文件路径为空")
        return file_url

    if not os.path.exists(file_path):
        if logger:
            logger.warning(f"文件不存在: {file_path}")
            # 列出目录内容帮助调试
            try:
                if os.path.exists(upload_dir):
                    files = os.listdir(upload_dir)
                    logger.info(f"[文件解析] 上传目录内容: {files[:10]}...")  # 只显示前10个文件
            except Exception as e:
                logger.error(f"[文件解析] 列出目录内容失败: {e}")
        return file_url

    # 检查文件类型是否支持
    if not file_parser.is_supported(file_path):
        if logger:
            logger.warning(f"不支持的文件类型: {file_path}")
        return file_url

    # 解析文件内容
    try:
        if logger:
            logger.info(f"[文件解析] 开始解析文件: {file_path}")
        result = await file_parser.parse(file_path)

        # 安全检查：确保 result 是字典类型
        if not isinstance(result, dict):
            if logger:
                logger.error(f"文件解析返回异常类型: {type(result)}")
            return file_url

        if "error" in result:
            error_msg = result.get("error", "未知错误")
            if logger:
                logger.error(f"文件解析失败: {error_msg}")
            return file_url

        content = result.get("content", "")
        if content:
            if logger:
                logger.info(f"成功解析文件内容: {file_path}, 字符数: {len(content)}")

            return f"""
【用户上传的大纲文件内容】

{content}

【以上是大纲文件内容，请在此基础上进行创作】
"""
        else:
            if logger:
                logger.warning(f"文件内容为空: {file_path}")
            return file_url

    except Exception as e:
        if logger:
            logger.exception(f"解析文件异常: {e}")
        return file_url

async def extract_input_params_files(
    input_params: Dict[str, Any],
    logger=None
) -> Dict[str, Any]:
    """
    处理输入参数中的文件URL，将文件内容提取出来

    Args:
        input_params: 输入参数字典
        logger: 日志记录器

    Returns:
        处理后的输入参数（原地修改并返回）
    """
    # 处理 custom_outline 字段（剧本大纲和小说大纲模块）
    if input_params.get("custom_outline"):
        original_value = input_params["custom_outline"]
        if logger:
            logger.info(
                f"[文件处理] 开始处理 custom_outline，原始值: {original_value[:100] if len(str(original_value)) > 100 else original_value}")

        content = await convert_file_url_to_content(
            input_params["custom_outline"],
            logger
        )

        # 只有当成功解析到内容时才更新
        # 成功解析的内容会包含"用户上传的大纲文件内容"标记
        if content and "用户上传的大纲文件内容" in content:
            input_params["custom_outline"] = content
            if logger:
                logger.info(
                    f"[文件处理] custom_outline 已更新为文件内容，长度: {len(str(content))}")
        else:
            if logger:
                logger.warning(
                    f"[文件处理] custom_outline 解析失败，返回内容: {str(content)[:200] if content else 'None'}")

    return input_params

def get_model_friendly_name(provider: str, model_id: str) -> str:
    """
    将模型ID转换为友好名称

    Args:
        provider: 提供商名称
        model_id: 模型ID

    Returns:
        模型友好名称
    """
    preset = PRESET_MODELS.get(provider.lower(), {})
    models = preset.get("models", [])

    for model in models:
        if model.get("id") == model_id:
            return model.get("name", model_id)

    # 如果找不到映射，返回原ID
    return model_id
