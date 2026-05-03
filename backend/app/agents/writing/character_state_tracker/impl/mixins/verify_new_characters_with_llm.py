"""CharacterStateTracker - verify_new_characters_with_llmMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
from typing import Any
import json
import re


class VerifyNewCharactersWithLlmMixin:
    """verify_new_characters_with_llm功能域"""

    async def verify_new_characters_with_llm(
        self,
        character_names: List[str],
        content: str,
        llm_provider
    ) -> List[str]:
        """使用LLM验证检测到的新人物

        对规则检测到的新人物进行语义验证，排除误检。

        Args:
            character_names: 检测到的人物名称列表
            content: 章节内容
            llm_provider: LLM提供者

        Returns:
            验证后确认的人物名称列表
        """
        if not character_names:
            return []

        try:
            # 提取每个人物的上下文
            char_contexts = []
            for name in character_names:
                context = self._extract_character_context(name, content)
                char_contexts.append(f"{name}: {context}")  # 不再截断人物上下文

            prompt = f"""请判断以下名称是否是真实的人物角色名称。

名称列表及其上下文：
{chr(10).join(char_contexts)}

请返回一个JSON数组，包含所有确实是人物角色的名称。
例如：["张三", "李四"]

只输出JSON数组，不要其他说明文字。"""

            # 调用LLM
            if hasattr(llm_provider, 'generate'):
                response = await llm_provider.generate(prompt)
            elif hasattr(llm_provider, 'call'):
                response = await llm_provider.call(prompt)
            else:
                response = await llm_provider(prompt)

            # 解析响应
            if isinstance(response, dict):
                content = response.get("content", response.get("text", ""))
            else:
                content = str(response)

            # 解析JSON数组
            result = self._parse_json_from_response(
                f"{{\"result\": {content}}}")
            if result and isinstance(result.get("result"), list):
                return result["result"]

            # 尝试直接解析为数组
            try:
                verified = json.loads(content)
                if isinstance(verified, list):
                    return verified
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.debug(f"JSON回退解析失败: {e}")

        except Exception as e:
            self.logger.error(f"LLM验证新人物失败: {e}")

        # 验证失败时，返回原始列表
        return character_names


    def _infer_speech_style_from_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """根据人物档案推断台词风格

        Args:
            profile: 人物档案字典

        Returns:
            speech_style字典
        """
        personality = profile.get("personality", "").lower()
        background = profile.get("background", "").lower()
        traits = profile.get("traits", [])
        identity = profile.get("identity", "").lower()

        speech_style = {
            "vocabulary_level": "通俗",  # 默认
            "sentence_pattern": "混合",
            "tone": "平静",
            "catchphrase": [],
            "style_influences": [],
            "special_habits": []
        }

        # 根据身份推断词汇层次
        if any(word in identity for word in [" scholar", "老师", "教授", "博士", "文人"]):
            speech_style["vocabulary_level"] = "文雅"
        elif any(word in identity for word in ["农民", "工人", "市民", "小贩"]):
            speech_style["vocabulary_level"] = "市井"
        elif any(word in identity for word in ["医生", "律师", "工程师", "专家"]):
            speech_style["vocabulary_level"] = "专业"

        # 根据性格推断语气基调
        if "幽默" in personality or "开朗" in personality:
            speech_style["tone"] = "幽默"
        elif "严肃" in personality or "冷静" in personality:
            speech_style["tone"] = "严肃"
        elif "温柔" in personality or "温和" in personality:
            speech_style["tone"] = "温婉"
        elif "尖锐" in personality or "刻薄" in personality:
            speech_style["tone"] = "讽刺"
        elif "冷酷" in personality or "冷漠" in personality:
            speech_style["tone"] = "冷峻"

        # 根据特征推断句式
        if "急躁" in traits or "直率" in traits:
            speech_style["sentence_pattern"] = "短句"
        elif "沉稳" in traits or "深思" in traits:
            speech_style["sentence_pattern"] = "长句"
        elif "诗意" in traits or "文艺" in traits:
            speech_style["sentence_pattern"] = "断句"  # 类似古龙风格

        # 根据背景推断文风影响
        if "北京" in background or "北方" in background:
            speech_style["style_influences"].append("老舍式京味")
        if "江湖" in background or "武侠" in background:
            speech_style["style_influences"].append("古龙式冷艳")
        if "上海" in background or "都市" in background:
            speech_style["style_influences"].append("张爱玲式苍凉")

        return speech_style


