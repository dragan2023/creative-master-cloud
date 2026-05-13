"""
多Agent协作文学作品生成系统 - 写手Agent 包入口

将原 writer_agent.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: WriterAgent 主类，继承自子 Mixin
    _prompts.py: 提示词构建方法 (WriterPromptsMixin)
    _utils.py: 工具方法 (WriterUtilsMixin)

@date: 2026-04-24
@version: v2.0.0
"""

import time
from typing import Optional

from app.agents.writing.base_agent import (
    BaseWritingAgent,
    AgentContext,
    AgentResult,
    AgentRole
)
from ._prompts import WriterPromptsMixin
from ._utils import WriterUtilsMixin


class WriterAgent(BaseWritingAgent, WriterPromptsMixin, WriterUtilsMixin):
    """写手Agent - 核心内容生成器

    根据场景大纲生成文学内容，是整个多Agent协作系统中最重要的内容生产者。

    主要职责：
    1. 根据场景大纲创作文学内容
    2. 与前文自然衔接
    3. 保持角色性格一致性
    4. 达到目标字数要求
    5. 在场景末尾设置钩子/悬念

    特点：
    - 使用较高温度(0.8)增强创意性
    - 提示词设计注重文学性和连贯性
    - 支持流式输出用于实时预览
    """

    agent_name = "写手Agent"
    agent_role = AgentRole.WRITER
    default_model = ""
    default_temperature = 0.8

    async def execute(self, context: AgentContext) -> AgentResult:
        """根据场景大纲生成文学内容

        Args:
            context: Agent执行上下文

        Returns:
            AgentResult: 包含生成内容和统计信息
        """
        start_time = time.time()

        try:
            # 检查是否为整章生成模式
            direct_mode = context.extra.get("direct_mode", False)

            if direct_mode:
                # 整章生成模式
                return await self._execute_direct_mode(context, start_time)

            # 非整章生成模式默认走直接生成模式
            return await self._execute_direct_mode(context, start_time)

        except Exception as e:
            # 使用 {e!r} 避免异常消息中的花括号被误解析为格式化占位符
            self.logger.error(f"写手Agent执行失败: {e!r}", exc_info=True)
            return self._build_error_result(f"内容生成失败: {str(e)[:200]}")

    async def _execute_direct_mode(self, context: AgentContext, start_time: float) -> AgentResult:
        """整章生成模式

        Args:
            context: 执行上下文
            start_time: 开始时间

        Returns:
            AgentResult: 执行结果
        """
        # 提取单元信息
        unit_title = context.extra.get("unit_title", "未命名章节")
        unit_summary = context.extra.get("unit_summary", "")

        # 字数配置
        target_words = context.config.get("words_per_scene", 3000)

        self.logger.info(
            f"[整章生成] 开始生成章节内容 - 标题: {unit_title}, "
            f"目标字数: {target_words}, 模式: 全局大纲+单元概述"
        )

        system_prompt = self._build_direct_writer_system_prompt(context)

        user_prompt = self._build_direct_writer_user_prompt(
            unit_title=unit_title,
            unit_summary=unit_summary,
            previous_content=context.previous_content,
            global_context=context.global_context,
            target_words=target_words,
            context=context
        )

        # 调用LLM生成内容
        response = await self.call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            task_id=context.task_id,
            scene_id=f"{context.unit_index}_direct"
        )

        # 提取结果
        content = response.get("content", "")

        # 清理内容
        content = self._clean_content(content)

        # 计算字数
        word_count = len(content)

        # 生成摘要
        summary = await self._generate_summary(content, unit_title)

        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)

        self.logger.info(
            f"[整章生成] 章节内容生成完成 - 字数: {word_count}, "
            f"目标: {target_words}, 偏差: {word_count - target_words}"
        )

        return self._build_success_result(
            content=content,
            token_usage={
                "input_tokens": response.get("input_tokens", 0),
                "output_tokens": response.get("output_tokens", 0),
                "total_tokens": response.get("total_tokens", 0)
            },
            duration_ms=duration_ms,
            model_id=response.get("model", self.default_model),
            summary=summary,
            word_count=word_count,
            scene_title=unit_title
        )
