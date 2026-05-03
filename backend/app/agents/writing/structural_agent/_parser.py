"""
多Agent协作文学作品生成系统 - 结构师Agent 解析模块

从 structural_agent.py 拆分，包含场景数据解析和验证方法。

@date: 2026-04-24
@version: v2.0.0
"""

import json
from typing import Any, Dict, List, Optional

from app.utils.json_parser import parse_json


class StructuralParserMixin:
    """结构师Agent场景解析 Mixin

    提供JSON提取、场景解析和验证等核心功能。
    """

    def _extract_json(self, text: str) -> Optional[dict]:
        """从LLM输出中提取JSON，使用健壮的JSON解析器

        Args:
            text: LLM输出文本

        Returns:
            Optional[dict]: 解析后的JSON数据，失败返回None
        """
        if not text or not text.strip():
            return None

        result = parse_json(text, default=None)

        if result is not None:
            self.logger.debug("JSON解析成功")
            return result

        return None

    async def _retry_parse_with_strict_prompt(self, context: 'AgentContext', original_messages: List[Dict[str, str]]) -> Optional[List[Dict[str, Any]]]:
        """使用更严格的prompt重试解析

        Args:
            context: Agent执行上下文
            original_messages: 原始提示词消息

        Returns:
            Optional[List[Dict]]: 场景列表，解析失败返回None
        """
        try:
            strict_messages = original_messages.copy()
            strict_system_prompt = self.SYSTEM_PROMPT_TEMPLATE + """

## 重要提醒

你必须严格以JSON格式返回，不要包含任何额外文字、说明或markdown标记。
只输出纯JSON数据，格式如下：
{"scenes": [{...}, {...}]}
"""
            strict_messages[0] = {"role": "system", "content": strict_system_prompt}

            self.logger.info("使用严格JSON格式要求重新调用LLM")

            llm_result = await self.call_llm(
                messages=strict_messages,
                model=self.default_model,
                temperature=0.3,
                task_id=context.task_id,
                scene_id=f"{context.unit_index}_structural_retry"
            )

            response = llm_result.get("content", "")
            self.logger.info(f"重试LLM返回内容(前500字符): {response[:500]}")

            return self._parse_scenes(response)

        except Exception as e:
            self.logger.error(f"重试解析时发生异常: {str(e)}")
            return None

    def _parse_scenes(self, content: str) -> Optional[List[Dict[str, Any]]]:
        """解析LLM输出的场景数据

        Args:
            content: LLM输出内容

        Returns:
            Optional[List[Dict]]: 场景列表，解析失败返回None
        """
        self.logger.info(f"开始解析场景数据，内容长度: {len(content)}")

        data = self._extract_json(content)

        if data is None:
            self.logger.warning(f"无法提取JSON，原始内容前200字符: {content[:200]}...")
            return None

        self.logger.info(f"成功提取JSON数据，类型: {type(data)}")

        if isinstance(data, dict):
            if "scenes" in data:
                scenes = data["scenes"]
                self.logger.info(f"从字典中提取scenes字段，场景数量: {len(scenes)}")
                return scenes
            else:
                self.logger.info("字典中没有scenes字段，尝试将整个字典作为单个场景")
                return [data]
        elif isinstance(data, list):
            self.logger.info(f"直接返回列表格式，场景数量: {len(data)}")
            return data

        self.logger.warning(f"无法识别的数据格式: {type(data)}")
        return None

    def _validate_scenes(self, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证和规范化场景数据

        Args:
            scenes: 场景数据列表

        Returns:
            List[Dict]: 验证后的场景列表
        """
        validated = []

        for i, scene in enumerate(scenes, 1):
            validated_scene = {
                "scene_index": scene.get("scene_index", i),
                "scene_title": scene.get("scene_title", f"场景{i}"),
                "location": scene.get("location", "未指定"),
                "characters": scene.get("characters", []),
                "event": scene.get("event", ""),
                "mood": scene.get("mood", "中性"),
                "word_target": scene.get("word_target", 800),
                "hook": scene.get("hook", "")
            }

            # 确保characters是列表
            if not isinstance(validated_scene["characters"], list):
                validated_scene["characters"] = [str(validated_scene["characters"])]

            # 确保word_target是整数且在合理范围
            word_target = validated_scene["word_target"]
            if not isinstance(word_target, int):
                try:
                    word_target = int(word_target)
                except (ValueError, TypeError):
                    word_target = 800
            word_target = max(300, min(2000, word_target))
            validated_scene["word_target"] = word_target

            validated.append(validated_scene)

        return validated
