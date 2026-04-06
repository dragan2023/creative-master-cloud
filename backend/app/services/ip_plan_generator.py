"""
原创IP计划生成服务
核心逻辑：基于用户简化的描述输入，AI自动解析并构建完整的角色IP档案
遵循核心公式：记忆锚点 + 情感投射 + 行为惯性 = 角色生命力

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
import json
import time

from app.agents.llm_manager import get_llm_manager
from app.agents.prompt_manager import get_prompt_manager
from app.agents.orchestrator import get_model_friendly_name

from app.core.logger import get_logger
from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool


def _format_sse(event: str, data: Dict[str, Any]) -> str:
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


class IPPlanGenerator:
    """原创IP计划生成器"""

    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.logger = get_logger(__name__)
        self.llm_manager = get_llm_manager()
        self.prompt_manager = get_prompt_manager()

    async def generate(
        self,
        ip_description: str,
        user_id: int = None,
        target_platform: str = "综合",
        reference_ip: str = None,
        commercial_goal: str = None,
        custom_requirements: str = None,
        provider: str = None,
        model: str = None,
        temperature: float = 0.8,
        knowledge_base_ids: list = None,
        enable_search: bool = False
    ) -> Dict[str, Any]:
        """
        生成原创IP计划

        Args:
            ip_description: IP角色概括性描述
            user_id: 用户ID（用于获取API配置）
            target_platform: 目标平台
            reference_ip: 参考的知名IP
            commercial_goal: 商业目标
            custom_requirements: 其他特殊要求
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            knowledge_base_ids: 知识库ID列表
            enable_search: 是否启用联网搜索

        Returns:
            生成结果字典
        """
        start_time = time.time()

        # 构建用户输入变量
        user_variables = {
            "ip_description": ip_description,
            "target_platform": target_platform or "综合（漫画/动画/游戏/周边等多平台）",
            "reference_ip": reference_ip or "无特定参考IP",
            "commercial_goal": commercial_goal or "打造具有商业价值的原创IP角色",
            "custom_requirements": custom_requirements or "无特殊要求"
        }

        # 从 prompt_manager 获取默认提示词模板
        template = self.prompt_manager.get_default_prompt("original_ip")

        # 渲染提示词（智能变量填充）
        full_prompt = self.prompt_manager.render_prompt(
            template=template,
            variables=user_variables,
            module="original_ip"
        )

        # 获取知识库上下文（如果启用）
        knowledge_context = ""
        if knowledge_base_ids:
            try:
                knowledge_tool = get_knowledge_retrieval_tool()
                for kb_id in knowledge_base_ids:
                    result = await knowledge_tool.retrieve(
                        query=f"IP角色设计 创意理论 {ip_description}",
                        knowledge_base_id=kb_id,
                        top_k=5
                    )
                    if result:
                        knowledge_context += result + "\n\n"
            except Exception as e:
                self.logger.warning(f"知识库检索失败: {e}")

        # 联网搜索（如果启用）
        search_context = ""
        if enable_search:
            try:
                # 这里可以调用搜索工具获取IP市场趋势
                search_context = "\n[联网搜索获取的IP市场趋势信息将在此补充]\n"
            except Exception as e:
                self.logger.warning(f"联网搜索失败: {e}")

        # 组合完整系统提示词
        system_prompt = "你是一位资深的IP角色设计专家，擅长从简单的概念描述中构建出具有商业价值和情感吸引力的完整角色IP档案。"
        if knowledge_context:
            system_prompt += f"\n\n## 知识库参考信息\n\n{knowledge_context}"
        if search_context:
            system_prompt += f"\n\n## IP市场趋势参考\n\n{search_context}"

        # 调用LLM生成
        try:
            # 获取LLM提供商
            if self.db and user_id:
                llm_provider = await self.llm_manager.get_provider_from_db(
                    self.db, user_id, provider
                )
            else:
                llm_provider = self.llm_manager.get_default_provider(
                    provider or "qianwen")

            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            # 调用LLM生成
            response = await llm_provider.generate(
                prompt=full_prompt,
                system_prompt=system_prompt,
                temperature=temperature
            )

            content = response.content

            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)

            return {
                "success": True,
                "content": content,
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
                "duration_ms": duration_ms
            }

        except Exception as e:
            self.logger.error(f"IP计划生成失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_stream(
        self,
        ip_description: str,
        user_id: int = None,
        target_platform: str = "综合",
        reference_ip: str = None,
        commercial_goal: str = None,
        custom_requirements: str = None,
        provider: str = None,
        model: str = None,
        temperature: float = 0.8,
        knowledge_base_ids: list = None,
        enable_search: bool = False,
        cancel_event=None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成原创IP计划

        Args:
            ip_description: IP角色概括性描述
            user_id: 用户ID（用于获取API配置）
            其他参数同generate方法
            cancel_event: 取消事件

        Yields:
            SSE格式的数据块（包含workflow事件和content内容）
        """
        start_time = time.time()

        try:
            # 发送开始事件
            yield _format_sse("workflow", {"type": "start", "steps": []})

            # 1. 获取 LLM 提供者
            yield _format_sse("workflow", {"type": "step", "step": "model", "status": "running", "message": "正在加载AI模型...", "icon": "Cpu"})

            if self.db and user_id:
                llm_provider = await self.llm_manager.get_provider_from_db(
                    self.db, user_id, provider
                )
            else:
                llm_provider = self.llm_manager.get_default_provider(
                    provider or "qianwen")

            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            # 获取模型友好名称用于显示
            model_display_name = get_model_friendly_name(
                llm_provider.get_model_info()["provider"],
                llm_provider.model_name
            )
            yield _format_sse("workflow", {"type": "step", "step": "model", "status": "done", "message": f"已加载模型: {model_display_name}"})

            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                yield _format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                return

            # 2. 准备提示词
            yield _format_sse("workflow", {"type": "step", "step": "prompt", "status": "running", "message": "正在准备提示词...", "icon": "Document"})

            # 构建用户输入变量
            user_variables = {
                "ip_description": ip_description,
                "target_platform": target_platform or "综合（漫画/动画/游戏/周边等多平台）",
                "reference_ip": reference_ip or "无特定参考IP",
                "commercial_goal": commercial_goal or "打造具有商业价值的原创IP角色",
                "custom_requirements": custom_requirements or "无特殊要求"
            }

            # 从 prompt_manager 获取默认提示词模板
            template = self.prompt_manager.get_default_prompt("original_ip")

            # 渲染提示词（智能变量填充）
            full_prompt = self.prompt_manager.render_prompt(
                template=template,
                variables=user_variables,
                module="original_ip"
            )

            yield _format_sse("workflow", {"type": "step", "step": "prompt", "status": "done", "message": "提示词准备完成"})

            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                yield _format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                return

            # 3. 知识库检索（如果启用）
            knowledge_context = ""
            if knowledge_base_ids:
                yield _format_sse("workflow", {"type": "step", "step": "knowledge", "status": "running", "message": "正在检索知识库...", "icon": "FolderOpened"})

                try:
                    knowledge_tool = get_knowledge_retrieval_tool()
                    kb_count = 0
                    for kb_id in knowledge_base_ids:
                        result = await knowledge_tool.retrieve(
                            query=f"IP角色设计 创意理论 {ip_description}",
                            knowledge_base_id=kb_id,
                            top_k=5
                        )
                        if result:
                            knowledge_context += result + "\n\n"
                            kb_count += 1
                    yield _format_sse("workflow", {"type": "step", "step": "knowledge", "status": "done", "message": f"已检索 {kb_count} 个知识库"})
                except Exception as e:
                    self.logger.warning(f"知识库检索失败: {e}")
                    yield _format_sse("workflow", {"type": "step", "step": "knowledge", "status": "done", "message": "知识库检索失败，跳过"})

            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                yield _format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                return

            # 4. 组合完整系统提示词
            system_prompt = "你是一位资深的IP角色设计专家，擅长从简单的概念描述中构建出具有商业价值和情感吸引力的完整角色IP档案。"
            if knowledge_context:
                system_prompt += f"\n\n## 知识库参考信息\n\n{knowledge_context}"

            # 5. 生成内容
            yield _format_sse("workflow", {"type": "step", "step": "generate", "status": "running", "message": "正在生成IP角色档案...", "icon": "ChatDotRound"})

            # 流式调用LLM生成
            async for chunk in llm_provider.generate_stream(
                prompt=full_prompt,
                system_prompt=system_prompt,
                temperature=temperature
            ):
                if cancel_event and cancel_event.is_set():
                    self.logger.info("IP计划生成被取消")
                    yield _format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                    return
                # 输出内容
                yield _format_sse("content", {"text": chunk})

            yield _format_sse("workflow", {"type": "step", "step": "generate", "status": "done", "message": "IP角色档案生成完成"})

            # 6. 发送完成事件
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.info(f"IP计划流式生成完成 - 耗时: {duration_ms}ms")

            yield _format_sse("workflow", {"type": "complete", "message": "生成完成"})
            yield _format_sse("done", {
                "model": model_display_name,
                "model_id": llm_provider.model_name,
                "provider": llm_provider.get_model_info()["provider"],
                "duration_ms": duration_ms
            })

        except Exception as e:
            self.logger.error(f"IP计划流式生成失败: {e}")
            yield _format_sse("workflow", {"type": "error", "message": str(e)})
            yield _format_sse("error", {"message": str(e)})


# 单例获取函数
_ip_plan_generator = None


def get_ip_plan_generator(db: AsyncSession = None) -> IPPlanGenerator:
    """获取IP计划生成器单例"""
    global _ip_plan_generator
    if _ip_plan_generator is None:
        _ip_plan_generator = IPPlanGenerator(db)
    elif db is not None:
        # 更新数据库会话
        _ip_plan_generator.db = db
    return _ip_plan_generator
