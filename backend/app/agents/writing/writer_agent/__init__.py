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
            direct_mode = context.extra.get("direct_mode", False) if isinstance(context.extra, dict) else False

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
        try:
            # 🔴 防御：安全提取 context 字段
            _config = context.config if isinstance(context.config, dict) else {}
            _extra = context.extra if isinstance(context.extra, dict) else {}
        except Exception as e:
            self.logger.error(f"[整章生成] 上下文字段提取失败: {e!r}", exc_info=True)
            return self._build_error_result(f"上下文字段异常: {str(e)[:200]}")

        # 提取单元信息
        content_type = _config.get("content_type", "novel")
        _unit_label_map = {"novel": "章", "series_script": "集", "movie_script": "场", "script": "场"}
        unit_label = _unit_label_map.get(content_type, "章")
        default_title = f"未命名{unit_label}节"
        unit_title = _extra.get("unit_title", default_title)
        unit_summary = _extra.get("unit_summary", "")

        # 字数/时长配置（根据内容类型区分）
        is_script = content_type in ("script", "series_script", "movie_script")
        target_words = _config.get("words_per_scene", 3000)
        if is_script:
            duration_minutes = _config.get("duration_minutes")
            if not duration_minutes:
                if content_type == "series_script":
                    er = _config.get("episode_duration_range", [30, 45])
                    duration_minutes = int((er[0] + er[1]) / 2) if isinstance(er, (list, tuple)) and len(er) == 2 else 40
                elif content_type == "movie_script":
                    dr = _config.get("duration_range", [10, 15])
                    duration_minutes = int((dr[0] + dr[1]) / 2) if isinstance(dr, (list, tuple)) and len(dr) == 2 else 12
                else:
                    duration_minutes = 5
            self.logger.info(
                f"[整{unit_label}生成] 开始生成{unit_label}节内容 - 标题: {unit_title}, "
                f"预计时长: {duration_minutes}分钟, 模式: 全局大纲+单元概述"
            )
        else:
            self.logger.info(
                f"[整{unit_label}生成] 开始生成{unit_label}节内容 - 标题: {unit_title}, "
                f"目标字数: {target_words}, 模式: 全局大纲+单元概述"
            )

        # 阶段1: 构建系统提示词
        try:
            system_prompt = self._build_direct_writer_system_prompt(context)
        except Exception as e:
            self.logger.error(f"[整{unit_label}生成] 构建系统提示词失败: {e!r}", exc_info=True)
            self._log_context_types(context, f"[整{unit_label}生成] 上下文诊断")
            return self._build_error_result(f"构建系统提示词失败: {str(e)[:200]}")

        # 阶段2: 构建用户提示词
        try:
            user_prompt = self._build_direct_writer_user_prompt(
                unit_title=unit_title,
                unit_summary=unit_summary,
                previous_content=context.previous_content,
                global_context=context.global_context,
                target_words=target_words,
                context=context
            )
        except Exception as e:
            self.logger.error(f"[整{unit_label}生成] 构建用户提示词失败: {e!r}", exc_info=True)
            self._log_context_types(context, f"[整{unit_label}生成] 上下文诊断")
            return self._build_error_result(f"构建用户提示词失败: {str(e)[:200]}")

        # 阶段3: 调用LLM生成内容
        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                task_id=context.task_id,
                scene_id=f"{context.unit_index}_direct",
                user_id=context.user_id
            )
        except Exception as e:
            self.logger.error(f"[整{unit_label}生成] LLM调用失败: {e!r}", exc_info=True)
            return self._build_error_result(f"LLM调用失败: {str(e)[:200]}")

        # [防御] 确保 response 是 dict 类型
        if not isinstance(response, dict):
            self.logger.error(f"[整{unit_label}生成] LLM响应类型异常: {type(response).__name__}, value={str(response)[:200]}")
            return self._build_error_result(f"LLM响应类型异常: {type(response).__name__}")

        # 提取结果
        content = response.get("content", "")

        # 清理内容
        try:
            content = self._clean_content(content)
        except Exception as e:
            self.logger.error(f"[整{unit_label}生成] 内容清理失败: {e!r}", exc_info=True)
            return self._build_error_result(f"内容清理失败: {str(e)[:200]}")

        # 计算字数
        word_count = len(content)

        # 生成摘要
        try:
            summary = await self._generate_summary(content, unit_title)
        except Exception as e:
            self.logger.error(f"[整{unit_label}生成] 摘要生成失败: {e!r}", exc_info=True)
            summary = ""

        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)

        self.logger.info(
            f"[整{unit_label}生成] {unit_label}节内容生成完成 - 字数: {word_count}, "
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

    @staticmethod
    def _log_context_types(context, prefix="上下文诊断"):
        """记录上下文字段的类型信息，用于错误诊断"""
        try:
            fields = ["config", "extra", "style_guide", "outline", "character_profiles",
                      "world_settings", "previous_content", "global_context"]
            parts = []
            for f in fields:
                val = getattr(context, f, None)
                parts.append(f"{f}={type(val).__name__}")
            logger = get_logger("agent.writer")
            logger.error(f"{prefix}: {', '.join(parts)}")
        except Exception:
            pass
