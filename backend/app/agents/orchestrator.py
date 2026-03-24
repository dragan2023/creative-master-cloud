"""
Agent 编排器
协调 LLM、工具和记忆系统完成创意生成任务
"""
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime
import json
import time
import random
import re
import asyncio
import base64
import os
import mimetypes

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.llm_manager import get_llm_manager, LLMManager
from app.agents.memory_manager import get_memory_manager, MemoryManager
from app.agents.prompt_manager import get_prompt_manager, PromptManager

from app.tools.web_search import get_web_search_tool, WebSearchTool
from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool, KnowledgeRetrievalTool
from app.tools.webpage_reader import get_webpage_reader, WebpageReader
from app.tools.file_parser import get_file_parser, FileParser
from app.tools.mcp.mcp_client import get_mcp_client, MCPClient
from app.tools.creative_search import get_creative_search, OptimizedCreativeSearch
from app.core.logger import get_logger, LoggerAdapter
from app.core.config import PRESET_MODELS, get_settings
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory
from app.models.generation import Generation, GenerationModule, GenerationStatus


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


async def process_input_params_files(
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


class AgentOrchestrator:
    """Agent 编排器"""

    def __init__(self):
        self.llm_manager = get_llm_manager()
        self.memory_manager = get_memory_manager()
        self.prompt_manager = get_prompt_manager()
        self.web_search = get_web_search_tool()
        self.knowledge_retrieval = get_knowledge_retrieval_tool()
        self.webpage_reader = get_webpage_reader()
        self.mcp_client = get_mcp_client()
        self.logger = get_logger("orchestrator")

    async def generate(
        self,
        db: AsyncSession,
        module: str,
        user_id: int,
        input_params: Dict[str, Any],
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        执行创意生成（非流式）

        Args:
            db: 数据库会话
            module: 模块名称
            user_id: 用户ID
            input_params: 输入参数
            session_id: 会话ID
            enable_search: 是否启用联网搜索
            enable_knowledge: 是否启用知识库增强（三层检索：通用→垂直领域→官方手册）
            reference_urls: 参考网页URL列表
            provider: 指定LLM提供者
            temperature: 温度参数
            images: 图片URL列表（多模态支持）
            videos: 视频URL列表（多模态支持，仅部分模型支持）

        Returns:
            生成结果
        """
        logger = get_logger(str(user_id))
        start_time = time.time()

        try:
            # 1. 获取 LLM 提供者
            llm_provider = await self.llm_manager.get_provider_from_db(
                db=db,
                user_id=user_id,
                provider_name=provider
            )

            # 2. 处理输入参数中的文件URL（将文件内容提取出来）
            input_params = await process_input_params_files(input_params, logger)

            # 3. 获取提示词模板
            prompt_template = await self.prompt_manager.get_prompt(db, module)

            # 4. 渲染提示词
            system_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module=module)

            # 3.1 添加创意变化引导（确保每次生成不同）
            creative_angles = [
                "请从一个独特的角度来诠释这个创意，避免常规套路",
                "请在创作中融入一些出人意料的元素，让人眼前一亮",
                "请尝试用新鲜的叙事方式来呈现，打破传统模式",
                "请在细节处理上有一些独到的巧思，增加记忆点",
                "请赋予作品一些独特的情感色彩，形成差异化风格",
                "请从逆向思维出发，挑战常规认知，带来新颖的视角",
                "请在结构上有一些创新设计，让整体更有层次感",
                "请在开篇设计一个吸引人的钩子，迅速抓住读者注意力",
                "请在结尾留下深刻印象，形成强烈的情感共鸣或思考",
                "请在中间段落设置一些反转或惊喜，增加戏剧张力"
            ]
            creative_styles = [
                "幽默风趣", "温馨感人", "悬疑紧张", "清新文艺",
                "热血励志", "轻松治愈", "反差萌", "情感共鸣"
            ]
            creative_seed = random.choice(creative_angles)
            creative_style_hint = random.choice(creative_styles)
            creative_id = random.randint(100000, 999999)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            system_prompt += f"""\n\n## 创意差异化指引
**本次创意编号**: #{creative_id}
**生成时间**: {current_time}
**风格倾向**: {creative_style_hint}

{creative_seed}

⚠️ 重要提示：本次创作必须与之前的创作有明显区别。请充分发挥创意，在保持主题一致的前提下，展现全新的创意思路和表达方式。避免重复使用相似的框架、句式和表达。"""

            # 4. 构建完整提示
            full_prompt = ""

            # 4.1 添加联网搜索结果
            if enable_search and input_params.get("topic"):
                # 使用降级策略搜索（免费优先）
                from app.tools.web_search import search_with_fallback

                async def get_user_search_key(provider: str):
                    """获取用户搜索API Key"""
                    try:
                        from app.models.user import UserAPIKey
                        result = await db.execute(
                            select(UserAPIKey).where(
                                UserAPIKey.user_id == user_id,
                                UserAPIKey.provider == provider,
                                UserAPIKey.is_valid == True
                            ).order_by(UserAPIKey.is_default.desc())
                        )
                        api_key_record = result.scalar_one_or_none()
                        if api_key_record:
                            from app.core.security import api_key_encryption
                            return api_key_encryption.decrypt(api_key_record.encrypted_key)
                    except Exception as e:
                        self.logger.warning(
                            f"获取用户{provider} API Key失败: {str(e)}")
                    return None

                search_results, engine_used = await search_with_fallback(
                    query=input_params["topic"],
                    num_results=3,
                    get_user_api_key=get_user_search_key
                )

                if search_results:
                    search_context = self.web_search.format_results(
                        search_results)
                    full_prompt += f"\n\n## 参考资料（联网搜索）\n{search_context}\n"
                    logger.info(
                        f"搜索完成，使用引擎: {engine_used}, 结果数: {len(search_results)}")

            # 4.2 三层检索知识库（通用→垂直领域→官方手册）
            if enable_knowledge:
                query_text = input_params.get(
                    "topic", "") or json.dumps(input_params)
                kb_contexts = await self._retrieve_classified_knowledge(
                    db=db,
                    user_id=user_id,
                    module=module,
                    query_text=query_text
                )

                # 将知识库内容添加到 prompt
                if kb_contexts["theory"].strip():
                    full_prompt += f"\n\n## 通用创意理论知识库\n{kb_contexts['theory']}\n"
                if kb_contexts["case"].strip():
                    full_prompt += f"\n\n## 垂直领域案例知识库\n{kb_contexts['case']}\n"
                if kb_contexts["manual"].strip():
                    full_prompt += f"\n\n## 官方规范手册\n{kb_contexts['manual']}\n"

            # 4.3 添加参考网页内容
            if reference_urls:
                webpage_contents = await self.webpage_reader.read_urls(reference_urls)
                if webpage_contents:
                    webpage_context = self.webpage_reader.format_for_context(
                        webpage_contents)
                    full_prompt += f"\n\n## 参考资料（网页链接）\n{webpage_context}\n"

            # 4.4 添加用户消息
            full_prompt += "\n\n请根据以上信息，按照要求的格式生成内容。"

            logger.info(f"开始生成 - 模块: {module}, 模型: {llm_provider.model_name}")

            # 转换图片URL为base64格式
            converted_images = convert_images_to_base64(images)
            if converted_images:
                logger.info(f"已转换 {len(converted_images)} 张图片为base64格式")

            # 处理视频URL
            if videos:
                logger.info(f"接收到 {len(videos)} 个视频URL: {videos}")

            # 5. 调用 LLM（支持多模态：文本、图片、视频）
            response = await llm_provider.generate(
                prompt=full_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                images=converted_images,
                videos=videos
            )

            # 6. 记录到会话
            if session_id:
                await self.memory_manager.add_message(
                    session_id=session_id,
                    role="user",
                    content=json.dumps(input_params, ensure_ascii=False)
                )
                await self.memory_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response.content
                )

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(f"生成完成 - 耗时: {duration_ms}ms")

            return {
                "success": True,
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
                "duration_ms": duration_ms
            }

        except Exception as e:
            logger.exception("生成失败")
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_stream(
        self,
        db: AsyncSession,
        module: str,
        user_id: int,
        input_params: Dict[str, Any],
        session_id: Optional[str] = None,
        enable_search: bool = False,  # 向后兼容，映射到 enable_creative_search
        enable_knowledge: bool = False,
        enable_mcp: bool = False,  # 向后兼容，映射到 enable_trending
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        # 知识库类别选择参数
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[List[int]] = None,
        kb_user_specific_ids: Optional[List[int]] = None,
        kb_manual_ids: Optional[List[int]] = None,
        # 创作辅助搜索参数（新）
        enable_creative_search: bool = False,
        search_keywords: Optional[List[str]] = None,
        search_depth: str = "normal",
        # 实时热点参数（新）
        enable_trending: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        执行创意生成（流式输出）

        Args:
            db: 数据库会话
            module: 模块名称
            user_id: 用户ID
            input_params: 输入参数
            session_id: 会话ID
            enable_search: 是否启用联网搜索（向后兼容，映射到 enable_creative_search）
            enable_knowledge: 是否启用知识库增强
            enable_mcp: 是否启用 MCP 实时热点数据（向后兼容，映射到 enable_trending）
            reference_urls: 参考网页URL列表
            provider: 指定LLM提供者
            temperature: 温度参数
            images: 图片URL列表（多模态支持）
            videos: 视频URL列表（多模态支持，仅部分LLM支持）
            kb_vertical: 是否启用垂直领域知识库
            kb_user_specific: 是否启用用户专属知识库
            kb_manual: 是否启用官方手册知识库
            kb_vertical_ids: 指定的垂直领域知识库ID列表
            kb_user_specific_ids: 指定的用户专属知识库ID列表
            kb_manual_ids: 指定的官方手册知识库ID列表
            enable_creative_search: 是否启用创作辅助搜索（智能搜索创作素材和背景信息）
            search_keywords: 用户指定的搜索关键词列表
            search_depth: 搜索深度 (quick/normal/deep)
            enable_trending: 是否启用实时热点聚合

        Yields:
            SSE 格式的数据块
        """
        logger = get_logger(str(user_id))
        start_time = time.time()

        # 参数兼容处理：旧参数映射到新参数
        actual_enable_creative_search = enable_creative_search or enable_search
        actual_enable_trending = enable_trending or enable_mcp

        # 定义工作流程步骤
        workflow_steps = []

        try:
            # 发送开始事件
            yield self._format_sse("workflow", {"type": "start", "steps": []})

            # 1. 获取 LLM 提供者
            workflow_steps.append(
                {"step": "model", "status": "running", "message": "正在加载AI模型..."})
            yield self._format_sse("workflow", {"type": "step", "step": "model", "status": "running", "message": "正在加载AI模型...", "icon": "Cpu"})
            llm_provider = await self.llm_manager.get_provider_from_db(
                db=db,
                user_id=user_id,
                provider_name=provider
            )
            # 获取模型友好名称用于显示
            model_display_name = get_model_friendly_name(
                llm_provider.get_model_info()["provider"],
                llm_provider.model_name
            )
            yield self._format_sse("workflow", {"type": "step", "step": "model", "status": "done", "message": f"已加载模型: {model_display_name}"})

            # 2. 处理输入参数中的文件URL（将文件内容提取出来）
            input_params = await process_input_params_files(input_params, logger)

            # 3. 获取提示词模板
            yield self._format_sse("workflow", {"type": "step", "step": "prompt", "status": "running", "message": "正在准备提示词...", "icon": "Document"})
            prompt_template = await self.prompt_manager.get_prompt(db, module)

            # 4. 渲染提示词
            system_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module=module)

            # 3.1 添加创意变化引导（确保每次生成不同）
            creative_angles = [
                "请从一个独特的角度来诠释这个创意，避免常规套路",
                "请在创作中融入一些出人意料的元素，让人眼前一亮",
                "请尝试用新鲜的叙事方式来呈现，打破传统模式",
                "请在细节处理上有一些独到的巧思，增加记忆点",
                "请赋予作品一些独特的情感色彩，形成差异化风格",
                "请从逆向思维出发，挑战常规认知，带来新颖的视角",
                "请在结构上有一些创新设计，让整体更有层次感",
                "请在开篇设计一个吸引人的钩子，迅速抓住读者注意力",
                "请在结尾留下深刻印象，形成强烈的情感共鸣或思考",
                "请在中间段落设置一些反转或惊喜，增加戏剧张力"
            ]
            creative_styles = [
                "幽默风趣", "温馨感人", "悬疑紧张", "清新文艺",
                "热血励志", "轻松治愈", "反差萌", "情感共鸣"
            ]
            creative_seed = random.choice(creative_angles)
            creative_style_hint = random.choice(creative_styles)
            creative_id = random.randint(100000, 999999)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            system_prompt += f"""\n\n## 创意差异化指引
**本次创意编号**: #{creative_id}
**生成时间**: {current_time}
**风格倾向**: {creative_style_hint}

{creative_seed}

⚠️ 重要提示：本次创作必须与之前的创作有明显区别。请充分发挥创意，在保持主题一致的前提下，展现全新的创意思路和表达方式。避免重复使用相似的框架、句式和表达。"""

            yield self._format_sse("workflow", {"type": "step", "step": "prompt", "status": "done", "message": "提示词准备完成"})

            # 4. 构建完整提示
            full_prompt = ""

            # 4.1 创作辅助搜索（智能搜索创作素材和背景信息）
            if actual_enable_creative_search:
                # 判断是否为用户主动搜索（用户指定了关键词）
                is_user_initiated_search = bool(search_keywords)

                if is_user_initiated_search:
                    # 用户主动搜索，直接使用用户指定的关键词
                    yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "running", "message": f"正在搜索创作素材，关键词：{', '.join(search_keywords)}...", "icon": "Search"})
                else:
                    # 智能分析是否需要搜索
                    yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "running", "message": "正在智能分析是否需要搜索创作素材...", "icon": "Search"})

                try:
                    # 获取创作辅助搜索实例
                    creative_search = get_creative_search()

                    # 执行智能搜索（用户指定关键词时强制搜索）
                    search_result = await creative_search.search(
                        input_params=input_params,
                        module=module,
                        user_keywords=search_keywords,
                        force_search=is_user_initiated_search,  # 用户指定关键词时强制搜索
                        search_depth=search_depth,
                        user_id=user_id,
                        db=db
                    )

                    if search_result["searched"] and search_result["results"]:
                        # 搜索成功，添加到提示词
                        full_prompt += f"\n\n{search_result['formatted_context']}\n"
                        cache_status = "（来自缓存）" if search_result["cached"] else ""
                        search_type = "用户指定" if is_user_initiated_search else "智能"
                        yield self._format_sse("workflow", {
                            "type": "step",
                            "step": "creative_search",
                            "status": "done",
                            "message": f"{search_type}搜索完成，找到 {len(search_result['results'])} 条参考资料{cache_status}，关键词：{', '.join(search_result['keywords'])}"
                        })
                        logger.info(
                            f"创作辅助搜索完成: keywords={search_result['keywords']}, results={len(search_result['results'])}, reason={search_result['reason']}")
                    elif search_result["searched"] and not search_result["results"]:
                        search_type = "用户指定" if is_user_initiated_search else "智能"
                        keywords_info = f"，关键词：{', '.join(search_result['keywords'])}" if search_result.get(
                            'keywords') else ""
                        yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "done", "message": f"{search_type}搜索未返回结果{keywords_info}"})
                    else:
                        # 不需要搜索（仅智能分析场景）
                        yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "done", "message": f"跳过搜索：{search_result['reason']}"})

                except Exception as e:
                    self.logger.exception("创作辅助搜索失败")
                    logger.exception(f"创作辅助搜索异常: {str(e)}")
                    yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "done", "message": "搜索服务暂时不可用，跳过"})

            # 4.2 知识库检索（通用固定调用 + 用户选择的类别）
            kb_contexts = {"theory": "", "case": "",
                           "user_specific": "", "manual": ""}
            query_text = input_params.get(
                "topic", "") or json.dumps(input_params)

            # 记录知识库检索状态
            logger.info(
                f"知识库增强状态: enable_knowledge={enable_knowledge}, kb_vertical={kb_vertical}, kb_user_specific={kb_user_specific}, kb_manual={kb_manual}")

            if enable_knowledge:
                # 构建检索状态消息
                kb_types = ["通用"]
                if kb_vertical:
                    kb_types.append("垂直领域")
                if kb_user_specific:
                    kb_types.append("用户专属")
                if kb_manual:
                    kb_types.append("官方手册")
                yield self._format_sse("workflow", {"type": "step", "step": "kb_retrieve", "status": "running", "message": f"正在检索知识库（{' → '.join(kb_types)})...", "icon": "Collection"})

                kb_contexts = await self._retrieve_classified_knowledge(
                    db=db,
                    user_id=user_id,
                    module=module,
                    query_text=query_text,
                    kb_vertical=kb_vertical,
                    kb_user_specific=kb_user_specific,
                    kb_manual=kb_manual,
                    kb_vertical_ids=kb_vertical_ids,
                    kb_user_specific_ids=kb_user_specific_ids,
                    kb_manual_ids=kb_manual_ids
                )

                # 统计检索结果
                theory_count = len(
                    [1 for line in kb_contexts["theory"].split("\n") if line.startswith("###")])
                case_count = len(
                    [1 for line in kb_contexts["case"].split("\n") if line.startswith("###")])
                user_specific_count = len(
                    [1 for line in kb_contexts["user_specific"].split("\n") if line.startswith("###")])
                manual_count = len(
                    [1 for line in kb_contexts["manual"].split("\n") if line.startswith("###")])

                # 构建结果消息
                result_parts = [f"通用:{theory_count}个"]
                if kb_vertical:
                    result_parts.append(f"垂直领域:{case_count}个")
                if kb_user_specific:
                    result_parts.append(f"用户专属:{user_specific_count}个")
                if kb_manual:
                    result_parts.append(f"官方手册:{manual_count}个")
                yield self._format_sse("workflow", {"type": "step", "step": "kb_retrieve", "status": "done", "message": f"已检索知识库（{', '.join(result_parts)}）"})

                # 将知识库内容添加到 prompt
                if kb_contexts["theory"].strip():
                    full_prompt += f"\n\n## 通用创意理论知识库\n{kb_contexts['theory']}\n"
                if kb_contexts["case"].strip():
                    full_prompt += f"\n\n## 垂直领域案例知识库\n{kb_contexts['case']}\n"
                if kb_contexts["user_specific"].strip():
                    full_prompt += f"\n\n## 用户专属知识库\n{kb_contexts['user_specific']}\n"
                if kb_contexts["manual"].strip():
                    full_prompt += f"\n\n## 官方规范手册\n{kb_contexts['manual']}\n"

            # 4.3 添加参考网页内容
            if reference_urls:
                yield self._format_sse("workflow", {"type": "step", "step": "webpage", "status": "running", "message": "智能体正在访问参考链接...", "icon": "Link"})
                webpage_contents = await self.webpage_reader.read_urls(reference_urls)
                if webpage_contents:
                    webpage_context = self.webpage_reader.format_for_context(
                        webpage_contents)
                    full_prompt += f"\n\n## 参考资料（网页链接）\n{webpage_context}\n"
                yield self._format_sse("workflow", {"type": "step", "step": "webpage", "status": "done", "message": f"已读取 {len(reference_urls)} 个链接"})

            # 4.4 添加实时热点数据（热点聚合）
            if actual_enable_trending:
                yield self._format_sse("workflow", {"type": "step", "step": "trending", "status": "running", "message": "正在聚合实时热点（通过搜索引擎获取）...", "icon": "TrendCharts"})
                try:
                    logger.info(f"热点聚合开始: user_id={user_id}")
                    # 获取热点数据（使用 search_hotnews provider，传递用户上下文以获取API Key）
                    trending_result = await self.mcp_client.get_trending_topics(
                        platforms=None,  # 获取所有平台
                        provider="search_hotnews",  # 使用基于搜索的热点聚合
                        limit=15,
                        use_cache=True,
                        db_session=db,
                        user_id=user_id
                    )
                    logger.info(
                        f"热点聚合结果: success={trending_result.success}, total_items={trending_result.total_items}, platforms={trending_result.platforms_count}")
                    if trending_result.success and trending_result.data:
                        trending_context = self.mcp_client.format_for_context(
                            trending_result, max_items=15)
                        # 添加明确的热点使用指令
                        hot_items_count = sum(len(p.items)
                                              for p in trending_result.data if p.items)
                        full_prompt += f"\n\n{trending_context}"
                        full_prompt += f"\n\n**🔥 热点融合创作指令**："
                        full_prompt += f"\n当前已获取 {hot_items_count} 条实时热点。你必须："
                        full_prompt += f"\n1. 从热点列表中选择1-3个与创作主题最相关的话题"
                        full_prompt += f"\n2. 将热点元素自然融入你的创作内容（可以是话题、事件、人物等）"
                        full_prompt += f"\n3. 在内容末尾添加\"📌 参考热点：[具体热点名称]\"标注"
                        full_prompt += f"\n4. 如果没有任何热点与主题相关，请说明原因并在内容中体现时效性"
                        # 统计热点数量
                        total_items = sum(len(p.items)
                                          for p in trending_result.data if p.items)
                        platform_count = len(
                            [p for p in trending_result.data if p.items])
                        yield self._format_sse("workflow", {"type": "step", "step": "trending", "status": "done", "message": f"已获取 {total_items} 条热点（来自{platform_count}个平台）"})
                    else:
                        error_msg = trending_result.error.message if trending_result.error else "未知错误"
                        logger.warning(f"热点聚合失败或无数据: {error_msg}")
                        yield self._format_sse("workflow", {"type": "step", "step": "trending", "status": "done", "message": "暂无热点数据"})
                except Exception as e:
                    self.logger.exception("获取热点数据失败")
                    logger.exception("热点聚合异常")
                    yield self._format_sse("workflow", {"type": "step", "step": "trending", "status": "done", "message": "热点数据获取失败，跳过"})

            # 4.5 添加用户消息
            full_prompt += "\n\n请根据以上信息，按照要求的格式生成内容。"

            logger.info(
                f"开始流式生成 - 模块: {module}, 模型: {llm_provider.model_name}")

            # 转换图片URL为base64格式
            converted_images = convert_images_to_base64(images)
            if converted_images:
                logger.info(f"已转换 {len(converted_images)} 张图片为base64格式")

            # 处理视频URL
            if videos:
                logger.info(f"接收到 {len(videos)} 个视频URL: {videos}")

            # 5. 生成并实时输出初稿内容
            yield self._format_sse("workflow", {"type": "step", "step": "generate", "status": "running", "message": "正在生成初稿内容...", "icon": "ChatDotRound"})

            # 获取模型支持的最大输出 token，并设置安全上限
            safe_output_limit = min(
                llm_provider.get_max_output_tokens(), 64000)
            logger.info(f"初次回答生成 - max_tokens: {safe_output_limit}")

            first_draft_content = []
            try:
                # Nuitka 兼容：确保 generate_stream 返回的是异步生成器
                stream = llm_provider.generate_stream(
                    prompt=full_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=safe_output_limit,
                    images=converted_images,
                    videos=videos
                )

                async for chunk in stream:
                    # 检查取消事件
                    if cancel_event and cancel_event.is_set():
                        logger.info(f"用户 {user_id} 取消了生成任务")
                        yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                        return

                    first_draft_content.append(chunk)
                    # 实时输出初稿内容给用户
                    yield self._format_sse("content", {"text": chunk})
            except Exception as stream_error:
                # 捕获流式生成过程中的异常
                logger.exception(f"流式生成异常: {stream_error}")
                yield self._format_sse("workflow", {"type": "error", "message": f"生成过程出错: {str(stream_error)}"})
                return

            yield self._format_sse("workflow", {"type": "step", "step": "generate", "status": "done", "message": "初稿内容生成完成"})

            # 6. 知识库评估与修正（如果启用了知识库）
            first_draft = "".join(first_draft_content)
            final_content = first_draft

            if enable_knowledge and (kb_contexts["theory"].strip() or kb_contexts["case"].strip() or kb_contexts["manual"].strip()):
                yield self._format_sse("workflow", {"type": "step", "step": "evaluate", "status": "running", "message": "智能体正在评估内容质量...", "icon": "DataAnalysis"})

                # 检查取消事件
                if cancel_event and cancel_event.is_set():
                    logger.info(f"用户 {user_id} 在评估阶段取消了生成任务")
                    yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                    return

                # 使用 LLM 评估初次回答与三类知识库的偏差
                evaluation_result = await self._evaluate_with_llm(
                    llm_provider=llm_provider,
                    first_answer=first_draft,
                    kb_contexts=kb_contexts,
                    input_params=input_params
                )

                if evaluation_result.get("needs_revision"):
                    issue_count = len(evaluation_result.get("theory_issues", [])) + \
                        len(evaluation_result.get("case_insights", [])) + \
                        len(evaluation_result.get("compliance_issues", []))
                    yield self._format_sse("workflow", {"type": "step", "step": "evaluate", "status": "done", "message": f"检测到可优化点：{issue_count}处"})

                    # 检查取消事件
                    if cancel_event and cancel_event.is_set():
                        logger.info(f"用户 {user_id} 在修正阶段取消了生成任务")
                        yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                        return

                    # 生成修正后的完整内容
                    yield self._format_sse("workflow", {"type": "step", "step": "revise", "status": "running", "message": "正在优化内容...", "icon": "Edit"})

                    revised_content = await self._generate_revised_content(
                        llm_provider=llm_provider,
                        original_content=first_draft,
                        evaluation_result=evaluation_result,
                        kb_contexts=kb_contexts,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        input_params=input_params,
                        cancel_event=cancel_event
                    )

                    if revised_content:
                        # 添加分隔线和修正标识
                        yield self._format_sse("content", {"text": "\n\n---\n\n### 🔄 基于知识库的优化建议\n\n"})
                        # 输出修正后的内容
                        yield self._format_sse("content", {"text": revised_content})
                        final_content = first_draft + "\n\n---\n\n### 🔄 基于知识库的优化建议\n\n" + revised_content

                    yield self._format_sse("workflow", {"type": "step", "step": "revise", "status": "done", "message": "内容优化完成"})
                else:
                    yield self._format_sse("workflow", {"type": "step", "step": "evaluate", "status": "done", "message": "知识库验证通过"})

            # 9. 自洽性检查
            yield self._format_sse("workflow", {"type": "step", "step": "consistency", "status": "running", "message": "执行自洽性检查...", "icon": "CircleCheck"})

            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                logger.info(f"用户 {user_id} 在自洽性检查阶段取消了生成任务")
                yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                return

            consistency_result = await self._check_self_consistency(
                llm_provider=llm_provider,
                content=first_draft,  # 检查初次回答
                input_params=input_params,
                module=module,
                temperature=temperature
            )

            # 如果发现逻辑问题，展示修正建议（不修改原内容）
            if consistency_result.get("issues"):
                issues_count = len(consistency_result.get("issues", []))
                yield self._format_sse("workflow", {"type": "step", "step": "consistency", "status": "done", "message": f"自洽性检查完成，发现{issues_count}处问题"})

                if consistency_result.get("needs_fix"):
                    fix_content = await self._auto_fix_issues(
                        llm_provider=llm_provider,
                        original_content=first_draft,
                        consistency_result=consistency_result,
                        temperature=temperature
                    )
                    if fix_content:
                        # 在初次回答下方展示修正建议，不修改原内容
                        yield self._format_sse("content", {"text": "\n\n---\n\n### 🤖 Agent修正建议\n\n"})
                        yield self._format_sse("content", {"text": fix_content})
                        final_content = first_draft + "\n\n---\n\n### 🤖 Agent修正建议\n\n" + fix_content
            else:
                yield self._format_sse("workflow", {"type": "step", "step": "consistency", "status": "done", "message": "自洽性检查通过"})

            # 10. 添加专业标识
            yield self._format_sse("content", {"text": "\n\n---\n\n✨ *该方案已经过全能创意大师智能验证与优化*"})
            final_content += "\n\n---\n\n✨ *该方案已经过全能创意大师智能验证与优化*"

            # 11. 保存生成记录到数据库
            try:
                # 从input_params中提取标题
                title = None
                if input_params:
                    # 优先级：title > topic > theme > subject > name
                    title_keys = ['title', 'topic', 'theme', 'subject', 'name']
                    for key in title_keys:
                        if key in input_params and input_params[key]:
                            title = str(input_params[key])[:200]  # 限制长度
                            break

                generation = Generation(
                    user_id=user_id,
                    module=GenerationModule(module),
                    status=GenerationStatus.COMPLETED,
                    input_params=input_params,
                    title=title,
                    output_content=final_content,
                    provider=llm_provider.get_model_info()["provider"],
                    model_name=llm_provider.model_name,
                    duration_ms=int((time.time() - start_time) * 1000)
                )
                db.add(generation)
                await db.commit()
                logger.info(f"生成记录已保存 - ID: {generation.id}, 标题: {title}")
            except Exception as save_error:
                logger.exception("保存生成记录失败")
                await db.rollback()

            # 12. 发送完成事件
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"流式生成完成 - 耗时: {duration_ms}ms")

            yield self._format_sse("workflow", {"type": "complete", "message": "生成完成"})
            yield self._format_sse("done", {
                "model": model_display_name,
                "model_id": llm_provider.model_name,
                "provider": llm_provider.get_model_info()["provider"],
                "duration_ms": duration_ms
            })

        except Exception as e:
            logger.exception("流式生成失败")
            yield self._format_sse("workflow", {"type": "error", "message": str(e)})
            yield self._format_sse("error", {"message": str(e)})

    # ==================== 模块与知识库分类映射 ====================

    # 模块名称到知识库分类的映射
    MODULE_CATEGORY_MAP = {
        "short_video": KnowledgeBaseCategory.SHORT_VIDEO,
        "script": KnowledgeBaseCategory.SCRIPT,
        "novel": KnowledgeBaseCategory.NOVEL,
        "print_ad": KnowledgeBaseCategory.PRINT_AD,
        "tvc": KnowledgeBaseCategory.TVC,
        "original_ip": KnowledgeBaseCategory.GENERAL,  # 原创IP计划使用通用知识库
    }

    def _sort_knowledge_bases_by_priority(
        self,
        kb_list: List[KnowledgeBase],
        module: str
    ) -> List[KnowledgeBase]:
        """
        按优先级排序知识库：通用 → 当前模块业务 → 其他业务 → 官方手册

        Args:
            kb_list: 知识库列表
            module: 当前模块名称

        Returns:
            排序后的知识库列表
        """
        # 获取当前模块对应的业务分类
        target_category = self.MODULE_CATEGORY_MAP.get(module)

        # 分离通用、业务和官方手册知识库
        general_kbs = []
        business_kbs = []
        manual_kbs = []
        other_kbs = []

        for kb in kb_list:
            if kb.category == KnowledgeBaseCategory.GENERAL:
                general_kbs.append(kb)
            elif kb.category == KnowledgeBaseCategory.MANUAL:
                manual_kbs.append(kb)
            elif target_category and kb.category == target_category:
                business_kbs.append(kb)
            else:
                other_kbs.append(kb)

        # 返回排序结果：通用 → 匹配的业务 → 其他业务 → 官方手册
        return general_kbs + business_kbs + other_kbs + manual_kbs

    # ==================== 预置知识库加载 ====================

    async def _get_static_knowledge_bases(
        self,
        db: AsyncSession,
        module: str = None
    ) -> List[KnowledgeBase]:
        """
        获取所有静态知识库（预置知识库），按优先级排序

        调用顺序：后台通用 → 后台业务（匹配当前模块）

        Args:
            db: 数据库会话
            module: 当前模块名称（用于匹配业务知识库）

        Returns:
            排序后的静态知识库列表
        """
        try:
            query = select(KnowledgeBase).where(
                KnowledgeBase.type == KnowledgeBaseType.STATIC,
                KnowledgeBase.status == KnowledgeBaseStatus.READY,
                # 排除 novel 类别：正文板块使用独立的项目专属知识库系统
                KnowledgeBase.category != KnowledgeBaseCategory.NOVEL
            )
            result = await db.execute(query)
            kb_list = list(result.scalars().all())

            # 按优先级排序
            if module:
                return self._sort_knowledge_bases_by_priority(kb_list, module)
            return kb_list
        except Exception as e:
            self.logger.exception("获取静态知识库失败")
            return []

    # ==================== 用户知识库加载 ====================

    async def _get_user_knowledge_bases(
        self,
        db: AsyncSession,
        user_id: int,
        module: str = None
    ) -> List[KnowledgeBase]:
        """
        获取用户知识库，按优先级排序

        调用顺序：用户端通用 → 用户端业务（匹配当前模块） → 其他业务 → 官方手册

        Args:
            db: 数据库会话
            user_id: 用户ID
            module: 当前模块名称（用于匹配业务知识库）

        Returns:
            排序后的用户知识库列表
        """
        try:
            query = select(KnowledgeBase).where(
                KnowledgeBase.type == KnowledgeBaseType.TEMP,
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.status == KnowledgeBaseStatus.READY,
                # 排除 novel 类别：正文板块使用独立的项目专属知识库系统
                KnowledgeBase.category != KnowledgeBaseCategory.NOVEL
            )
            result = await db.execute(query)
            kb_list = list(result.scalars().all())

            # 按优先级排序
            if module:
                return self._sort_knowledge_bases_by_priority(kb_list, module)
            return kb_list
        except Exception as e:
            self.logger.exception("获取用户知识库失败")
            return []

    async def _retrieve_classified_knowledge(
        self,
        db: AsyncSession,
        user_id: int,
        module: str,
        query_text: str,
        # 知识库类别选择参数
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[List[int]] = None,
        kb_user_specific_ids: Optional[List[int]] = None,
        kb_manual_ids: Optional[List[int]] = None
    ) -> Dict[str, str]:
        """
        按类别检索知识库

        检索顺序：
        1. 理论知识库（通用知识库）- 固定调用
        2. 垂直领域知识库 - 用户选择启用后调用
        3. 用户专属知识库 - 用户选择启用后调用
        4. 官方手册知识库 - 用户选择启用后调用

        Args:
            db: 数据库会话
            user_id: 用户ID
            module: 当前模块名称
            query_text: 检索查询文本
            kb_vertical: 是否启用垂直领域知识库
            kb_user_specific: 是否启用用户专属知识库
            kb_manual: 是否启用官方手册知识库
            kb_vertical_ids: 指定的垂直领域知识库ID列表
            kb_user_specific_ids: 指定的用户专属知识库ID列表
            kb_manual_ids: 指定的官方手册知识库ID列表

        Returns:
            {
                "theory": "通用理论知识库内容...",
                "case": "垂直领域知识库内容...",
                "user_specific": "用户专属知识库内容...",
                "manual": "官方手册内容..."
            }
        """
        kb_contexts = {
            "theory": "",
            "case": "",
            "user_specific": "",
            "manual": ""
        }

        try:
            # 获取用户的 GraphRAG 配置
            graphrag_enabled = await self._get_user_graphrag_config(db, user_id)

            # 获取用户知识库
            user_kb_list = await self._get_user_knowledge_bases(db, user_id, module)

            if not user_kb_list:
                return kb_contexts

            # 定义垂直领域类别
            # 注意：NOVEL 类别不在此列表中，因为正文板块使用独立的项目专属知识库系统
            # 正文板块的知识库通过 ProjectKnowledgeBase 类管理，不参与公共知识库检索
            vertical_categories = [
                KnowledgeBaseCategory.SHORT_VIDEO,
                KnowledgeBaseCategory.SCRIPT,
                # KnowledgeBaseCategory.NOVEL,  # 已移除：正文板块使用独立的项目专属知识库
                KnowledgeBaseCategory.PRINT_AD,
                KnowledgeBaseCategory.TVC
            ]

            # 逐个检索并按类别分类
            for kb in user_kb_list:
                try:
                    # 1. 通用知识库 - 固定调用
                    if kb.category == KnowledgeBaseCategory.GENERAL:
                        kb_result = await self._retrieve_single_kb(
                            kb, query_text, graphrag_enabled
                        )
                        if kb_result:
                            kb_contexts["theory"] += f"\n### {kb.name}\n{kb_result}\n"
                        continue

                    # 2. 垂直领域知识库 - 用户选择启用后调用
                    if kb.category in vertical_categories:
                        if not kb_vertical:
                            continue
                        # 如果指定了具体ID，检查是否在列表中
                        if kb_vertical_ids and kb.id not in kb_vertical_ids:
                            continue
                        kb_result = await self._retrieve_single_kb(
                            kb, query_text, graphrag_enabled
                        )
                        if kb_result:
                            kb_contexts["case"] += f"\n### {kb.name}\n{kb_result}\n"
                        continue

                    # 3. 用户专属知识库 - 用户选择启用后调用
                    if kb.category == KnowledgeBaseCategory.USER_SPECIFIC:
                        if not kb_user_specific:
                            continue
                        if kb_user_specific_ids and kb.id not in kb_user_specific_ids:
                            continue
                        # 用户专属知识库始终使用GraphRAG
                        kb_result = await self._retrieve_single_kb(
                            kb, query_text, True
                        )
                        if kb_result:
                            kb_contexts["user_specific"] += f"\n### {kb.name}\n{kb_result}\n"
                        continue

                    # 4. 官方手册 - 用户选择启用后调用（不使用GraphRAG）
                    if kb.category == KnowledgeBaseCategory.MANUAL:
                        if not kb_manual:
                            continue
                        if kb_manual_ids and kb.id not in kb_manual_ids:
                            continue
                        kb_result = await self._retrieve_single_kb(
                            kb, query_text, False
                        )
                        if kb_result:
                            kb_contexts["manual"] += f"\n### {kb.name}\n{kb_result}\n"
                        continue

                except Exception as e:
                    self.logger.exception(f"检索知识库 {kb.name} 失败")
                    continue

            return kb_contexts

        except Exception as e:
            self.logger.exception("分类检索知识库失败")
            return kb_contexts

    async def _retrieve_single_kb(
        self,
        kb: KnowledgeBase,
        query_text: str,
        use_graphrag: bool
    ) -> Optional[str]:
        """
        检索单个知识库

        Args:
            kb: 知识库对象
            query_text: 检索查询文本
            use_graphrag: 是否使用GraphRAG

        Returns:
            检索结果字符串或None
        """
        try:
            if use_graphrag:
                # GraphRAG 检索（知识图谱增强）
                kb_result = await self.knowledge_retrieval.retrieve_with_graph_context(
                    collection_name=kb.collection_name,
                    query=query_text,
                    n_results=2
                )
            else:
                # 传统向量检索
                kb_result = await self.knowledge_retrieval.retrieve_with_context(
                    collection_name=kb.collection_name,
                    query=query_text,
                    n_results=2
                )

            if kb_result and "未找到" not in kb_result:
                return kb_result
            return None
        except Exception as e:
            self.logger.exception(f"检索知识库 {kb.name} 异常")
            return None

    async def _get_user_graphrag_config(
        self,
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """
        获取用户的 GraphRAG 配置

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            是否启用 GraphRAG，默认为 True
        """
        try:
            from app.models import SystemConfig
            import json

            config_key = f"user_preprocessor_config_{user_id}"
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.id == config_key)
            )
            config_record = result.scalar_one_or_none()

            if config_record and config_record.config_value:
                config_data = json.loads(config_record.config_value)
                return config_data.get("graphrag_enabled", True)

            return True  # 默认启用
        except Exception as e:
            self.logger.exception("获取 GraphRAG 配置失败")
            return True  # 出错时默认启用

    # ==================== 知识库验证与修正 ====================

    async def _evaluate_with_llm(
        self,
        llm_provider,
        first_answer: str,
        kb_contexts: Dict[str, str],
        input_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用 LLM 评估初次回答与三类知识库的偏差

        评估维度：
        1. 理论支撑：是否恰当运用创意理论？
        2. 案例启发：是否受案例启发但非照搬？
        3. 规范符合：是否遵守用户手册？

        Args:
            llm_provider: LLM提供者
            first_answer: 初次生成的回答
            kb_contexts: 三类知识库内容
            input_params: 用户输入参数

        Returns:
            {
                "theory_issues": ["问题1", "问题2"],
                "case_insights": ["启发点1", "启发点2"],
                "compliance_issues": ["违规1"],
                "needs_revision": true/false,
                "explanation": "评估说明"
            }
        """
        evaluation_prompt = f"""你是专业的创意质量评审专家。

【用户需求】
{json.dumps(input_params, ensure_ascii=False, indent=2)}

【初次回答】
{first_answer[:2500]}

【创意理论知识库】
{kb_contexts.get('theory', '无相关理论')}

【案例资料知识库】
{kb_contexts.get('case', '无相关案例')}

【用户规范手册】
{kb_contexts.get('manual', '无规范手册')}

## 评估任务

请从以下三个维度评估初次回答：

### 1. 理论支撑性
- 是否运用了知识库中的创意理论？
- 理论应用是否恰当合理？
- **注意**：不要求死板套用理论，重点是看是否有理论支撑

### 2. 案例启发性（重点）
- 是否从案例中提取了创意思路、爆点设计或吸引点？
- **严格要求**：禁止直接复制案例的具体内容、框架或文案
- **正确做法**：分析案例背后的方法论和亮点，进行创新性转化

### 3. 规范符合性
- 是否违反用户规范手册中的要求？
- 如有明确规范，是否严格遵守？

## 输出要求

请以JSON格式输出评估结果：

{{
    "theory_issues": ["如：未运用知识库中的'悬念理论'"],
    "case_insights": ["如：可借鉴案例中的'反差式开头'但需重新设计"],
    "compliance_issues": ["如：违反手册'禁止使用夸张词汇'的规定"],
    "needs_revision": true,
    "explanation": "简要说明是否需要修正及原因"
}}

如果内容质量良好、无重大问题，返回：
{{"theory_issues": [], "case_insights": [], "compliance_issues": [], "needs_revision": false, "explanation": "内容符合要求"}}
"""

        try:
            # 使用较低温度进行稳定分析
            response = await llm_provider.generate(
                prompt=evaluation_prompt,
                temperature=0.3,
                max_tokens=30000
            )

            result_text = response.content.strip()

            # 尝试解析JSON结果
            import re
            json_match = re.search(
                r'\{[^{}]*"needs_revision"[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return {
                        "theory_issues": result.get("theory_issues", []),
                        "case_insights": result.get("case_insights", []),
                        "compliance_issues": result.get("compliance_issues", []),
                        "needs_revision": result.get("needs_revision", False),
                        "explanation": result.get("explanation", "")
                    }
                except json.JSONDecodeError:
                    pass

            # 如果JSON解析失败，返回默认结果
            return {
                "theory_issues": [],
                "case_insights": [],
                "compliance_issues": [],
                "needs_revision": False,
                "explanation": "评估完成"
            }

        except Exception as e:
            # 使用 logger 记录错误
            self.logger.exception("LLM评估失败")
            return {
                "theory_issues": [],
                "case_insights": [],
                "compliance_issues": [],
                "needs_revision": False,
                "explanation": f"评估失败: {str(e)}"
            }

    async def _generate_revised_content(
        self,
        llm_provider,
        original_content: str,
        evaluation_result: Dict[str, Any],
        kb_contexts: Dict[str, str],
        system_prompt: str,
        temperature: float,
        input_params: Dict[str, Any],
        cancel_event: Optional[asyncio.Event] = None
    ) -> Optional[str]:
        """
        根据评估结果，生成修正后的完整内容（非追加，而是重写）

        Args:
            llm_provider: LLM提供者
            original_content: 原始生成内容
            evaluation_result: 评估结果
            kb_contexts: 三类知识库内容
            system_prompt: 系统提示词
            temperature: 温度参数
            input_params: 输入参数（用于获取AI平台等信息）

        Returns:
            修正后的完整内容
        """
        theory_issues = evaluation_result.get("theory_issues", [])
        case_insights = evaluation_result.get("case_insights", [])
        compliance_issues = evaluation_result.get("compliance_issues", [])

        # 获取用户选择的AI平台
        ai_platforms = input_params.get("ai_platforms") or ""
        if isinstance(ai_platforms, list):
            ai_platforms = ", ".join(ai_platforms)
        ai_platforms = ai_platforms.strip()

        ai_platform_hint = ""
        if ai_platforms and ai_platforms != "无":
            ai_platform_hint = f"""

**【强制】AI平台名称保留**：
- 原始内容中的AI视频生成提示词标题必须严格使用平台名称："{ai_platforms}"
- 禁止更改为其他名称（如 SEDANCE、SoraDance、Seedance2 等）
- 禁止添加版本号（如 2.0、2 等）
- 必须完全按照 "{ai_platforms}" 输出"""

        # 构建修正提示词
        revision_prompt = f"""你是专业的创意优化师。你的任务是基于原始回答和知识库参考，生成一份**完整且优化后**的内容。

## 原始回答（必须以此为基础进行优化，保留所有内容）
{original_content}

## 知识库参考（用于优化指导）
- 创意理论：{kb_contexts.get('theory', '无')}
- 案例资料：{kb_contexts.get('case', '无')}
- 规范手册：{kb_contexts.get('manual', '无')}

## 评估发现的问题（需要针对性优化）
- 理论支撑问题：{theory_issues if theory_issues else '无'}
- 案例启发建议：{case_insights if case_insights else '无'}
- 规范符合问题：{compliance_issues if compliance_issues else '无'}

## 优化任务要求（必须严格遵守）

1. **【强制】完整输出**：必须输出完整的优化版本，包含原始回答的所有分镜、所有段落、所有内容。禁止只输出部分片段或修改的部分。
2. **【强制】保留结构**：保留原始回答的完整结构，包括标题、表格、分镜描述、AI提示词等所有部分。
3. **【强制】内容完整**：确保所有分镜序号（如分镜1、分镜2...分镜9）都包含在输出中，不要遗漏任何一部分。
4. **理论融入**：自然地运用相关创意理论，增强专业性
5. **案例转化**：从案例中提取方法论和亮点，创新性转化（绝不照搬）
6. **规范遵守**：严格遵守用户手册中的所有规定
7. **保持创意**：不要变得死板，保持内容的灵活性和创新性
{ai_platform_hint}

## 输出格式要求
- 输出完整的Markdown格式内容
- 保留所有表格、标题、列表等格式
- 确保内容长度与原始回答相当或更长

请直接输出优化后的**完整内容**（不要省略任何部分）：
"""

        try:
            # 使用流式生成修正内容，设置动态max_tokens确保内容完整
            safe_output_limit = min(
                llm_provider.get_max_output_tokens(), 64000)
            revised_content = []
            async for chunk in llm_provider.generate_stream(
                prompt=revision_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=safe_output_limit
            ):
                # 检查取消事件
                if cancel_event and cancel_event.is_set():
                    self.logger.info("内容重写被取消")
                    return None

                revised_content.append(chunk)

            result = "".join(revised_content)
            return result if result.strip() else None

        except Exception as e:
            self.logger.exception("内容重写失败")
            return None

    def _format_sse(self, event: str, data: Dict[str, Any]) -> str:
        """
        格式化为 SSE 格式

        Args:
            event: 事件类型
            data: 数据

        Returns:
            SSE 格式字符串
        """
        data_str = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {data_str}\n\n"

    async def create_session(
        self,
        user_id: int,
        module: str
    ) -> str:
        """
        创建新会话

        Args:
            user_id: 用户ID
            module: 模块名称

        Returns:
            会话ID
        """
        return await self.memory_manager.create_session(
            user_id=user_id,
            module=module
        )

    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        获取会话消息

        Args:
            session_id: 会话ID
            limit: 最大消息数

        Returns:
            消息列表
        """
        return await self.memory_manager.get_messages(session_id, limit)

    # ==================== 自主反思机制 ====================

    async def _evaluate_result(
        self,
        content: str,
        input_params: Dict[str, Any],
        module: str
    ) -> Dict[str, Any]:
        """
        评估生成结果质量

        Args:
            content: 生成的内容
            input_params: 输入参数
            module: 模块名称

        Returns:
            评估结果 {"score": 0-100, "issues": [...], "needs_retry": bool}
        """
        issues = []
        score = 100

        # 1. 检查内容长度
        if len(content) < 100:
            issues.append("内容过短")
            score -= 30
        elif len(content) < 300:
            issues.append("内容可能不够详细")
            score -= 10

        # 2. 检查是否包含关键元素
        topic = input_params.get("topic", "") or input_params.get(
            "theme", "") or input_params.get("synopsis", "")
        if topic and topic.lower() not in content.lower():
            issues.append("内容与主题关联度可能不足")
            score -= 15

        # 3. 检查结构完整性
        structure_markers = ["一、", "二、", "三、", "1.", "2.", "3.", "#", "##"]
        has_structure = any(marker in content for marker in structure_markers)
        if not has_structure:
            issues.append("内容结构可能不够清晰")
            score -= 10

        # 4. 检查是否有明确的结尾
        ending_markers = ["总结", "结语", "结尾", "完", "以上"]
        has_ending = any(marker in content for marker in ending_markers)
        if not has_ending and len(content) > 500:
            issues.append("内容可能缺少明确的结尾")
            score -= 5

        # 5. 根据模块检查特定内容
        module_checks = {
            "short_video": ["脚本", "场景", "镜头", "台词"],
            "script": ["场景", "人物", "对话", "剧情"],
            "novel": ["人物", "情节", "背景"],
            "print_ad": ["文案", "视觉", "核心"],
            "tvc": ["场景", "镜头", "旁白"]
        }

        if module in module_checks:
            keywords = module_checks[module]
            missing_keywords = [kw for kw in keywords if kw not in content]
            if len(missing_keywords) > len(keywords) // 2:
                issues.append(f"内容可能缺少关键元素: {', '.join(missing_keywords[:2])}")
                score -= 10

        # 确保分数在合理范围
        score = max(0, min(100, score))

        return {
            "score": score,
            "issues": issues,
            "needs_retry": score < 60 and len(issues) > 2
        }

    # ==================== 自洽性检查机制 ====================

    async def _check_self_consistency(
        self,
        llm_provider,
        content: str,
        input_params: Dict[str, Any],
        module: str,
        temperature: float
    ) -> Dict[str, Any]:
        """
        自洽性检查：验证内容的逻辑一致性、事实准确性

        使用LLM进行多维度分析：
        1. 逻辑一致性：前后内容是否矛盾
        2. 事实准确性：关键信息是否合理
        3. 格式完整性：是否遗漏必要元素

        Args:
            llm_provider: LLM提供者
            content: 生成的内容
            input_params: 输入参数
            module: 模块名称
            temperature: 温度参数

        Returns:
            {"issues": [...], "needs_fix": bool, "details": str}
        """
        issues = []

        # 构建自洽性检查提示词
        consistency_prompt = f"""你是一个专业的内容审核专家。请对以下内容进行自洽性检查，识别逻辑问题、矛盾或不合理之处。

## 用户原始需求
{json.dumps(input_params, ensure_ascii=False, indent=2)}

## 生成的内容
{content[:3000]}

## 检查要求
请检查以下维度：
1. **逻辑一致性**：内容前后是否矛盾？时间线是否合理？
2. **主题相关性**：内容是否紧扣用户的主题需求？
3. **格式完整性**：是否包含用户要求的特定格式（如AI视频提示词、分镜脚本等）？
4. **信息准确性**：是否有明显的事实错误或不合理描述？

## 输出格式
请用JSON格式输出检查结果：
{{"issues": ["问题1", "问题2"], "needs_fix": true/false, "summary": "简要总结"}}

如果内容质量良好，无重大问题，返回：{{"issues": [], "needs_fix": false, "summary": "内容质量良好，逻辑清晰"}}"""

        try:
            # 使用较低温度进行稳定分析
            response = await llm_provider.generate(
                prompt=consistency_prompt,
                temperature=0.3,
                max_tokens=30000
            )

            result_text = response.content.strip()

            # 尝试解析JSON结果
            import re
            json_match = re.search(
                r'\{[^{}]*"issues"[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return {
                        "issues": result.get("issues", []),
                        "needs_fix": result.get("needs_fix", False),
                        "summary": result.get("summary", "")
                    }
                except json.JSONDecodeError:
                    pass

            # 如果JSON解析失败，返回基本结果
            return {
                "issues": [],
                "needs_fix": False,
                "summary": "检查完成"
            }

        except Exception as e:
            self.logger.exception("自洽性检查失败")
            return {
                "issues": [],
                "needs_fix": False,
                "summary": f"检查失败: {str(e)}"
            }

    async def _auto_fix_issues(
        self,
        llm_provider,
        original_content: str,
        consistency_result: Dict[str, Any],
        temperature: float
    ) -> Optional[str]:
        """
        自动修正发现的问题

        Args:
            llm_provider: LLM提供者
            original_content: 原始内容
            consistency_result: 自洽性检查结果
            temperature: 温度参数

        Returns:
            修正补充内容
        """
        issues = consistency_result.get("issues", [])
        if not issues:
            return None

        fix_prompt = f"""你是内容修正专家。请根据以下发现的问题，生成修正或补充内容。

## 原始内容（部分）
{original_content[:2000]}

## 发现的问题
{chr(10).join('- ' + issue for issue in issues)}

## 任务
请直接输出修正或补充的内容。要求：
1. 只输出需要修正或补充的部分
2. 不要重复原始内容
3. 使用清晰的格式

修正内容："""

        try:
            safe_output_limit = min(
                llm_provider.get_max_output_tokens(), 64000)
            fix_content = []
            async for chunk in llm_provider.generate_stream(
                prompt=fix_prompt,
                temperature=temperature,
                max_tokens=safe_output_limit
            ):
                fix_content.append(chunk)

            result = "".join(fix_content)
            return result if result.strip() else None

        except Exception as e:
            self.logger.exception("自动修正失败")
            return None

    async def _reflect_and_retry(
        self,
        db: AsyncSession,
        module: str,
        user_id: int,
        input_params: Dict[str, Any],
        original_content: str,
        evaluation: Dict[str, Any],
        session_id: Optional[str] = None,
        enable_search: bool = False,
        knowledge_base_id: Optional[str] = None,
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        max_retries: int = 1
    ) -> Dict[str, Any]:
        """
        反思并重试生成

        Args:
            原始参数...
            original_content: 原始生成内容
            evaluation: 评估结果
            max_retries: 最大重试次数

        Returns:
            改进后的生成结果
        """
        logger = get_logger(str(user_id))

        if max_retries <= 0 or not evaluation.get("needs_retry"):
            return {
                "success": True,
                "content": original_content,
                "reflected": False
            }

        logger.info(f"开始反思重试 - 问题: {evaluation['issues']}")

        try:
            # 获取 LLM 提供者
            llm_provider = await self.llm_manager.get_provider_from_db(
                db=db, user_id=user_id, provider_name=provider
            )

            # 构建反思提示
            reflection_prompt = f"""
你之前生成的内容存在以下问题：
{chr(10).join('- ' + issue for issue in evaluation['issues'])}

原始内容：
{original_content[:1000]}...

请改进内容，确保：
1. 内容更加详细和完整
2. 结构清晰，有明确的章节划分
3. 紧扣主题，提供有价值的信息
4. 符合{module}类型的标准格式

请重新生成改进后的内容：
"""

            # 获取提示词模板
            prompt_template = await self.prompt_manager.get_prompt(db, module)
            system_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params)

            # 调用 LLM 重新生成
            response = await llm_provider.generate(
                prompt=reflection_prompt,
                system_prompt=system_prompt,
                temperature=0.8  # 稍微提高温度以获得更多变化
            )

            # 评估新结果
            new_evaluation = await self._evaluate_result(response.content, input_params, module)

            # 如果新结果更好，使用新结果
            if new_evaluation["score"] > evaluation["score"]:
                logger.info(f"反思改进成功 - 新分数: {new_evaluation['score']}")
                return {
                    "success": True,
                    "content": response.content,
                    "model": response.model,
                    "provider": response.provider,
                    "reflected": True,
                    "improvement": new_evaluation["score"] - evaluation["score"]
                }
            else:
                logger.info("反思未改善结果，保留原始内容")
                return {
                    "success": True,
                    "content": original_content,
                    "reflected": True,
                    "improvement": 0
                }

        except Exception as e:
            logger.exception("反思重试失败")
            return {
                "success": True,
                "content": original_content,
                "reflected": False,
                "error": str(e)
            }

    async def generate_with_reflection(
        self,
        db: AsyncSession,
        module: str,
        user_id: int,
        input_params: Dict[str, Any],
        session_id: Optional[str] = None,
        enable_search: bool = False,
        knowledge_base_id: Optional[str] = None,
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        enable_reflection: bool = True
    ) -> Dict[str, Any]:
        """
        带自主反思的生成

        Args:
            同 generate 方法
            enable_reflection: 是否启用反思机制

        Returns:
            生成结果
        """
        # 先执行正常生成
        result = await self.generate(
            db=db,
            module=module,
            user_id=user_id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            knowledge_base_id=knowledge_base_id,
            reference_urls=reference_urls,
            provider=provider,
            temperature=temperature
        )

        if not result.get("success"):
            return result

        # 如果启用反思，评估结果
        if enable_reflection:
            evaluation = await self._evaluate_result(
                result["content"],
                input_params,
                module
            )

            result["evaluation"] = evaluation

            # 如果需要重试
            if evaluation.get("needs_retry"):
                reflection_result = await self._reflect_and_retry(
                    db=db,
                    module=module,
                    user_id=user_id,
                    input_params=input_params,
                    original_content=result["content"],
                    evaluation=evaluation,
                    session_id=session_id,
                    enable_search=enable_search,
                    knowledge_base_id=knowledge_base_id,
                    reference_urls=reference_urls,
                    provider=provider
                )

                if reflection_result.get("reflected"):
                    result.update(reflection_result)

        return result


# 全局 Agent 编排器实例
agent_orchestrator = AgentOrchestrator()


def get_agent_orchestrator() -> AgentOrchestrator:
    """获取 Agent 编排器实例"""
    return agent_orchestrator
