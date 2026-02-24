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

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.llm_manager import get_llm_manager, LLMManager
from app.agents.memory_manager import get_memory_manager, MemoryManager
from app.agents.prompt_manager import get_prompt_manager, PromptManager
from app.tools.web_search import get_web_search_tool, WebSearchTool
from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool, KnowledgeRetrievalTool
from app.tools.webpage_reader import get_webpage_reader, WebpageReader
from app.core.logger import get_logger, LoggerAdapter
from app.core.config import PRESET_MODELS
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory
from app.models.generation import Generation, GenerationModule, GenerationStatus


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
        images: Optional[List[str]] = None
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

            # 2. 获取提示词模板
            prompt_template = await self.prompt_manager.get_prompt(db, module)

            # 3. 渲染提示词
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
                search_results = await self.web_search.search(
                    query=input_params["topic"],
                    num_results=3
                )
                search_context = self.web_search.format_results(search_results)
                full_prompt += f"\n\n## 参考资料（联网搜索）\n{search_context}\n"

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

            # 5. 调用 LLM（支持多模态）
            response = await llm_provider.generate(
                prompt=full_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                images=images
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
            logger.error(f"生成失败: {str(e)}", exc_info=True)
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
        enable_search: bool = False,
        enable_knowledge: bool = False,
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        images: Optional[List[str]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[str, None]:
        """
        执行创意生成（流式输出）

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

        Yields:
            SSE 格式的数据块
        """
        logger = get_logger(str(user_id))
        start_time = time.time()

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

            # 2. 获取提示词模板
            yield self._format_sse("workflow", {"type": "step", "step": "prompt", "status": "running", "message": "正在准备提示词...", "icon": "Document"})
            prompt_template = await self.prompt_manager.get_prompt(db, module)

            # 3. 渲染提示词
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

            # 4.1 添加联网搜索结果
            if enable_search and input_params.get("topic"):
                yield self._format_sse("workflow", {"type": "step", "step": "search", "status": "running", "message": "智能体正在联网搜索资料...", "icon": "Search"})
                search_results = await self.web_search.search(
                    query=input_params["topic"],
                    num_results=3
                )
                search_context = self.web_search.format_results(search_results)
                full_prompt += f"\n\n## 参考资料（联网搜索）\n{search_context}\n"
                yield self._format_sse("workflow", {"type": "step", "step": "search", "status": "done", "message": f"找到 {len(search_results)} 条参考资料"})

            # 4.2 三层检索知识库（通用→垂直领域→官方手册）
            kb_contexts = {"theory": "", "case": "", "manual": ""}
            query_text = input_params.get(
                "topic", "") or json.dumps(input_params)

            # 记录知识库检索状态
            logger.info(f"知识库增强状态: enable_knowledge={enable_knowledge}")

            if enable_knowledge:
                yield self._format_sse("workflow", {"type": "step", "step": "kb_retrieve", "status": "running", "message": "正在三层检索知识库（通用→垂直领域→官方手册）...", "icon": "Collection"})

                kb_contexts = await self._retrieve_classified_knowledge(
                    db=db,
                    user_id=user_id,
                    module=module,
                    query_text=query_text
                )

                # 统计检索结果
                theory_count = len(
                    [1 for line in kb_contexts["theory"].split("\n") if line.startswith("###")])
                case_count = len(
                    [1 for line in kb_contexts["case"].split("\n") if line.startswith("###")])
                manual_count = len(
                    [1 for line in kb_contexts["manual"].split("\n") if line.startswith("###")])

                yield self._format_sse("workflow", {"type": "step", "step": "kb_retrieve", "status": "done", "message": f"已检索知识库（通用:{theory_count}个，垂直领域:{case_count}个，官方手册:{manual_count}个）"})

                # 将知识库内容添加到 prompt
                if kb_contexts["theory"].strip():
                    full_prompt += f"\n\n## 通用创意理论知识库\n{kb_contexts['theory']}\n"
                if kb_contexts["case"].strip():
                    full_prompt += f"\n\n## 垂直领域案例知识库\n{kb_contexts['case']}\n"
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

            # 4.4 添加用户消息
            full_prompt += "\n\n请根据以上信息，按照要求的格式生成内容。"

            logger.info(
                f"开始流式生成 - 模块: {module}, 模型: {llm_provider.model_name}")

            # 5. 生成并实时输出初稿内容
            yield self._format_sse("workflow", {"type": "step", "step": "generate", "status": "running", "message": "正在生成初稿内容...", "icon": "ChatDotRound"})

            first_draft_content = []
            async for chunk in llm_provider.generate_stream(
                prompt=full_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                images=images
            ):
                # 检查取消事件
                if cancel_event and cancel_event.is_set():
                    logger.info(f"用户 {user_id} 取消了生成任务")
                    yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                    return

                first_draft_content.append(chunk)
                # 实时输出初稿内容给用户
                yield self._format_sse("content", {"text": chunk})

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
                logger.error(f"保存生成记录失败: {str(save_error)}")
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
            logger.error(f"流式生成失败: {str(e)}", exc_info=True)
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
                KnowledgeBase.status == KnowledgeBaseStatus.READY
            )
            result = await db.execute(query)
            kb_list = list(result.scalars().all())

            # 按优先级排序
            if module:
                return self._sort_knowledge_bases_by_priority(kb_list, module)
            return kb_list
        except Exception as e:
            self.logger.error(f"获取静态知识库失败: {str(e)}")
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
                KnowledgeBase.status == KnowledgeBaseStatus.READY
            )
            result = await db.execute(query)
            kb_list = list(result.scalars().all())

            # 按优先级排序
            if module:
                return self._sort_knowledge_bases_by_priority(kb_list, module)
            return kb_list
        except Exception as e:
            self.logger.error(f"获取用户知识库失败: {str(e)}")
            return []

    async def _retrieve_classified_knowledge(
        self,
        db: AsyncSession,
        user_id: int,
        module: str,
        query_text: str
    ) -> Dict[str, str]:
        """
        按三类分开检索用户知识库

        Args:
            db: 数据库会话
            user_id: 用户ID
            module: 当前模块名称
            query_text: 检索查询文本

        Returns:
            {
                "theory": "创意理论知识库内容...",
                "case": "案例资料知识库内容...",
                "manual": "用户规范手册内容..."
            }
        """
        kb_contexts = {
            "theory": "",
            "case": "",
            "manual": ""
        }

        try:
            # 获取用户的 GraphRAG 配置
            graphrag_enabled = await self._get_user_graphrag_config(db, user_id)

            # 获取用户知识库
            user_kb_list = await self._get_user_knowledge_bases(db, user_id, module)

            if not user_kb_list:
                return kb_contexts

            # 逐个检索并按类别分类
            for kb in user_kb_list:
                try:
                    # 官方手册类型始终使用传统检索（没有生成知识图谱）
                    # 其他类型根据用户配置选择检索方式
                    use_graphrag = (
                        graphrag_enabled and
                        kb.category != KnowledgeBaseCategory.MANUAL
                    )

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
                        # 根据知识库类别分类
                        if kb.category == KnowledgeBaseCategory.GENERAL:
                            kb_contexts["theory"] += f"\n### {kb.name}\n{kb_result}\n"
                        elif kb.category == KnowledgeBaseCategory.MANUAL:
                            kb_contexts["manual"] += f"\n### {kb.name}\n{kb_result}\n"
                        else:
                            # 业务类知识库（SHORT_VIDEO/SCRIPT/NOVEL/PRINT_AD/TVC）
                            kb_contexts["case"] += f"\n### {kb.name}\n{kb_result}\n"
                except Exception as e:
                    self.logger.error(f"检索知识库 {kb.name} 失败: {str(e)}")
                    continue

            return kb_contexts

        except Exception as e:
            self.logger.error(f"分类检索知识库失败: {str(e)}")
            return kb_contexts

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
            self.logger.error(f"获取 GraphRAG 配置失败: {str(e)}")
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
                max_tokens=800
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
            self.logger.error(f"LLM评估失败: {str(e)}")
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
            # 使用流式生成修正内容，设置较大的max_tokens确保内容完整
            revised_content = []
            async for chunk in llm_provider.generate_stream(
                prompt=revision_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=8000  # 确保输出完整内容不被截断
            ):
                # 检查取消事件
                if cancel_event and cancel_event.is_set():
                    self.logger.info("内容重写被取消")
                    return None

                revised_content.append(chunk)

            result = "".join(revised_content)
            return result if result.strip() else None

        except Exception as e:
            self.logger.error(f"内容重写失败: {str(e)}")
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
                max_tokens=500
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
            self.logger.error(f"自洽性检查失败: {str(e)}")
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
            fix_content = []
            async for chunk in llm_provider.generate_stream(
                prompt=fix_prompt,
                temperature=temperature
            ):
                fix_content.append(chunk)

            result = "".join(fix_content)
            return result if result.strip() else None

        except Exception as e:
            self.logger.error(f"自动修正失败: {str(e)}")
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
            logger.error(f"反思重试失败: {str(e)}")
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
