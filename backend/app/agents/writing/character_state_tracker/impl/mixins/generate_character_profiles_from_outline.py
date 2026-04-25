"""CharacterStateTracker - generate_character_profiles_from_outlineMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
import json
import re


class GenerateCharacterProfilesFromOutlineMixin:
    """generate_character_profiles_from_outline功能域"""

    async def generate_character_profiles_from_outline(
        self,
        outline: Dict[str, Any],
        llm_provider=None
    ) -> List[Dict[str, Any]]:
        """从全局大纲中提取并生成人物设定

        根据全局大纲中的人物简述，自动生成完整的人物设定。
        适用于初始化时的人物设定补充。

        Args:
            outline: 全局大纲字典
            llm_provider: LLM提供者（用于生成人物设定）

        Returns:
            生成的人物设定列表
        """
        generated_profiles = []

        try:
            # 1. 从大纲中提取人物简述
            character_mentions = self._extract_character_mentions_from_outline(
                outline)

            for char_name, char_info in character_mentions.items():
                # 检查是否已有完整设定
                if char_name in self._character_states:
                    existing = self._character_states[char_name]
                    # 如果已有较完整的设定，跳过
                    if existing.attributes.get("personality") and existing.attributes.get("background"):
                        continue

                # 2. 使用LLM生成完整设定
                if llm_provider:
                    profile = await self._generate_profile_with_llm(
                        char_name=char_name,
                        char_info=char_info,
                        llm_provider=llm_provider,
                        outline_context=outline
                    )
                else:
                    # 无LLM时使用简单模板
                    profile = self._generate_simple_profile(
                        char_name, char_info)

                if profile:
                    generated_profiles.append(profile)

                    # 同步到追踪器
                    self.update_character_state(
                        char_name,
                        {
                            "identity": profile.get("role", ""),
                            "location": profile.get("initial_location", ""),
                            "attributes": {
                                "personality": profile.get("personality", ""),
                                "background": profile.get("background", ""),
                                "age": profile.get("age", ""),
                                "gender": profile.get("gender", "")
                            }
                        }
                    )

            self.logger.info(f"从大纲生成人物设定完成: {len(generated_profiles)}个人物")

        except Exception as e:
            self.logger.error(f"从大纲生成人物设定失败: {e}")

        return generated_profiles


    def _extract_character_mentions_from_outline(self, outline: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """从大纲中提取人物提及信息

        Args:
            outline: 全局大纲字典

        Returns:
            人物名称 -> 人物信息的映射
        """
        character_mentions = {}

        # 检查多种可能的大纲结构
        # 结构1: outline.characters
        if outline.get("characters"):
            for char in outline.get("characters", []):
                if isinstance(char, dict):
                    name = char.get("name", "")
                    if name:
                        character_mentions[name] = char
                elif isinstance(char, str):
                    character_mentions[char] = {"name": char}

        # 结构2: outline.人物设定
        if outline.get("人物设定"):
            for char in outline.get("人物设定", []):
                if isinstance(char, dict):
                    name = char.get("name", char.get("姓名", ""))
                    if name:
                        character_mentions[name] = char

        # 结构3: outline.main_characters
        if outline.get("main_characters"):
            for char in outline.get("main_characters", []):
                if isinstance(char, dict):
                    name = char.get("name", "")
                    if name:
                        character_mentions[name] = char

        # 结构4: 从章节大纲中提取
        chapters = outline.get("chapters", outline.get("章节大纲", []))
        if isinstance(chapters, list):
            for chapter in chapters:
                if isinstance(chapter, dict):
                    # 检查章节中的人物字段
                    chars = chapter.get("characters", chapter.get("出场人物", []))
                    if isinstance(chars, list):
                        for char in chars:
                            if isinstance(char, str) and char not in character_mentions:
                                character_mentions[char] = {
                                    "name": char, "source": "章节提及"}
                            elif isinstance(char, dict):
                                name = char.get("name", "")
                                if name and name not in character_mentions:
                                    character_mentions[name] = char

        return character_mentions


    async def _generate_profile_with_llm(
        self,
        char_name: str,
        char_info: Dict[str, Any],
        llm_provider,
        outline_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """使用LLM生成人物设定

        Args:
            char_name: 人物名称
            char_info: 已有的人物信息
            llm_provider: LLM提供者
            outline_context: 全局大纲上下文

        Returns:
            生成的人物设定字典
        """
        try:
            # 构建提示词
            prompt = f"""请根据以下信息生成一个完整的人物设定。

人物名称：{char_name}
已有信息：{json.dumps(char_info, ensure_ascii=False, indent=2)}

全局大纲背景：
{json.dumps(outline_context.get("synopsis", outline_context.get("简介", "未知")), ensure_ascii=False)}

请生成以下人物设定信息（JSON格式）：
{{
  "name": "人物名称",
  "role": "角色定位（主角/重要配角/次要配角）",
  "identity": "身份/职业",
  "personality": "性格特点（3-5个关键词）",
  "background": "背景故事（50-100字）",
  "age": "年龄范围",
  "gender": "性别",
  "initial_location": "初始位置",
  "goals": "目标/动机",
  "relationships": {{"其他人物": "关系描述"}}
}}

只输出JSON，不要其他说明文字。"""

            # 调用LLM
            if hasattr(llm_provider, 'generate'):
                response = await llm_provider.generate(prompt)
            elif hasattr(llm_provider, 'call'):
                response = await llm_provider.call(prompt)
            else:
                # 尝试作为可调用对象
                response = await llm_provider(prompt)

            # 解析响应
            if isinstance(response, dict):
                content = response.get("content", response.get("text", ""))
            else:
                content = str(response)

            # 提取JSON
            profile = self._parse_json_from_response(content)

            if profile:
                profile["name"] = char_name  # 确保名称正确
                return profile

        except Exception as e:
            self.logger.error(f"LLM生成人物设定失败: {char_name}, 错误: {e}")

        return None


    def _generate_simple_profile(self, char_name: str, char_info: Dict[str, Any]) -> Dict[str, Any]:
        """生成简单的人物设定（无LLM时的备选方案）

        Args:
            char_name: 人物名称
            char_info: 已有的人物信息

        Returns:
            简单的人物设定字典
        """
        return {
            "name": char_name,
            "role": char_info.get("role", char_info.get("身份", "角色")),
            "identity": char_info.get("identity", char_info.get("身份", "")),
            "personality": char_info.get("personality", char_info.get("性格", "待补充")),
            "background": char_info.get("background", char_info.get("背景", "待补充")),
            "age": char_info.get("age", char_info.get("年龄", "未知")),
            "gender": char_info.get("gender", char_info.get("性别", "未知")),
            "initial_location": char_info.get("location", char_info.get("初始位置", "")),
            "relationships": char_info.get("relationships", {})
        }


