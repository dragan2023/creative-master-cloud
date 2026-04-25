"""CharacterStateTracker - generate_profile_for_new_characterMixin"""
from __future__ import annotations
from typing import Dict
from typing import Optional
from typing import Any
import json
import re


class GenerateProfileForNewCharacterMixin:
    """generate_profile_for_new_character功能域"""

    async def generate_profile_for_new_character(
        self,
        char_name: str,
        content: str,
        chapter_num: int,
        llm_provider=None
    ) -> Optional[Dict[str, Any]]:
        """为新发现的人物生成设定

        当检测到新人物时，根据上下文自动生成人物设定。

        Args:
            char_name: 人物名称
            content: 章节内容（用于提取上下文）
            chapter_num: 章节号
            llm_provider: LLM提供者

        Returns:
            生成的人物设定
        """
        try:
            # 提取人物在内容中的上下文
            char_context = self._extract_character_context(char_name, content)

            if llm_provider:
                # 使用LLM生成设定
                profile = await self._generate_new_character_profile_with_llm(
                    char_name=char_name,
                    char_context=char_context,
                    chapter_num=chapter_num,
                    llm_provider=llm_provider
                )
            else:
                # 使用简单模板
                profile = {
                    "name": char_name,
                    "role": "配角",
                    "first_appearance": chapter_num,
                    "source": "自动检测"
                }

            if profile:
                # 添加到追踪器
                self.update_character_state(
                    char_name,
                    {
                        "identity": profile.get("identity", ""),
                        "location": profile.get("location", profile.get("initial_location", "")),
                        "attributes": {
                            "personality": profile.get("personality", ""),
                            "background": profile.get("background", ""),
                            "role": profile.get("role", "配角")
                        }
                    },
                    chapter_num=chapter_num
                )

                self.logger.info(f"为新人物生成设定: {char_name}")

            return profile

        except Exception as e:
            self.logger.error(f"生成新人物设定失败: {char_name}, 错误: {e}")
            return None


    def _extract_character_context(self, char_name: str, content: str) -> str:
        """提取人物在内容中的上下文

        Args:
            char_name: 人物名称
            content: 完整内容

        Returns:
            包含该人物的上下文片段
        """
        # 查找人物名称出现的位置
        contexts = []

        # 使用正则查找人物名称及其周围的上下文
        pattern = rf'.{{0,100}}{re.escape(char_name)}.{{0,100}}'
        matches = re.findall(pattern, content)

        # 最多取前3个匹配
        for match in matches[:3]:
            contexts.append(match)

        return "...".join(contexts)


    async def _generate_new_character_profile_with_llm(
        self,
        char_name: str,
        char_context: str,
        chapter_num: int,
        llm_provider
    ) -> Optional[Dict[str, Any]]:
        """使用LLM为新人物生成设定"""
        try:
            prompt = f"""请根据以下文本片段中的人物上下文，生成一个简要的人物设定。

人物名称：{char_name}
首次出场章节：第{chapter_num}章
人物上下文：
{char_context}

请生成以下人物设定信息（JSON格式）：
{{
  "name": "人物名称",
  "role": "角色定位（主角/重要配角/次要配角/路人）",
  "identity": "身份/职业（根据上下文推断）",
  "personality": "性格特点（根据上下文推断）",
  "background": "可能的背景（根据上下文推断，如不确定可填'待补充'）",
  "location": "当前位置（根据上下文推断）"
}}

只输出JSON，不要其他说明文字。"""

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

            return self._parse_json_from_response(content)

        except Exception as e:
            self.logger.error(f"LLM生成新人物设定失败: {e}")
            return None


    def _parse_json_from_response(self, content: str) -> Optional[Dict[str, Any]]:
        """从LLM响应中解析JSON

        Args:
            content: LLM响应内容

        Returns:
            解析出的JSON字典
        """
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON代码块
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取花括号内容
        brace_pattern = r'\{[\s\S]*\}'
        match = re.search(brace_pattern, content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None


