"""
多Agent协作文学作品生成系统 - 结构师Agent 包入口

将原 structural_agent.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: StructuralAgent 主类，继承自子 Mixin
    _prompts.py: 提示词构建方法 (StructuralPromptsMixin)
    _parser.py: 场景解析和验证方法 (StructuralParserMixin)

@date: 2026-04-24
@version: v2.0.0
"""

import json
import time
from typing import Optional

from app.agents.writing.base_agent import BaseWritingAgent, AgentContext, AgentResult, AgentRole
from app.agents.writing.agent_config import AgentConfig
from ._prompts import StructuralPromptsMixin
from ._parser import StructuralParserMixin


class StructuralAgent(BaseWritingAgent, StructuralPromptsMixin, StructuralParserMixin):
    """结构师Agent - 负责将写作单元拆解为场景

    职责：
    1. 分析单元大纲和全局上下文
    2. 将单元内容拆分为3-6个场景
    3. 为每个场景规划：标题、地点、角色、事件、情绪、字数目标、钩子
    4. 确保场景间逻辑衔接和叙事节奏
    """

    agent_name = "结构师Agent"
    agent_role = AgentRole.STRUCTURAL
    default_model = ""
    default_temperature = 0.6

    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行单元结构拆解

        Args:
            context: Agent执行上下文

        Returns:
            AgentResult: 包含场景列表的数据
        """
        start_time = time.time()
        self.logger.info(f"开始拆解单元 {context.unit_index} 的结构")

        try:
            # 1. 构建提示词
            messages = self._build_prompt(context)

            # 2. 调用LLM
            llm_result = await self.call_llm(
                messages=messages,
                model=self.default_model,
                temperature=self.default_temperature,
                task_id=context.task_id,
                scene_id=f"{context.unit_index}_structural"
            )

            # 3. 记录LLM原始返回内容
            response = llm_result.get("content", "")
            self.logger.info(f"LLM原始返回内容(前500字符): {response[:500]}")

            # 4. 解析LLM输出
            scenes_data = self._parse_scenes(response)

            # 5. 如果解析失败，尝试重试一次
            if not scenes_data:
                self.logger.warning("第一次解析失败，尝试重试并强调JSON格式要求")
                scenes_data = await self._retry_parse_with_strict_prompt(context, messages)

            if not scenes_data:
                return self._build_error_result(
                    "无法从LLM输出中解析场景结构",
                    raw_content=response[:500]
                )

            # 6. 验证场景数据
            validated_scenes = self._validate_scenes(scenes_data)

            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.info(f"单元 {context.unit_index} 结构拆解完成，生成 {len(validated_scenes)} 个场景，耗时 {duration_ms}ms")

            return self._build_success_result(
                content=json.dumps({"scenes": validated_scenes}, ensure_ascii=False, indent=2),
                token_usage={
                    "input_tokens": llm_result.get("input_tokens", 0),
                    "output_tokens": llm_result.get("output_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0)
                },
                duration_ms=duration_ms,
                model_id=llm_result.get("model", self.default_model),
                scenes=validated_scenes,
                scene_count=len(validated_scenes)
            )

        except Exception as e:
            self.logger.exception(f"拆解单元结构时发生异常: {str(e)}")
            return self._build_error_result(f"结构拆解失败: {str(e)}")
