"""
一致性管理器
维护角色状态、前文摘要等一致性保障机制

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
import json
import re
import aiofiles
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.logger import get_logger
from app.models import NovelProject, NovelChapter
from app.services.novel_writer.prompt_templates import (
    SUMMARY_UPDATE_PROMPT,
    CHARACTER_UPDATE_PROMPT,
    CONSISTENCY_CHECK_PROMPT
)


class ConsistencyManager:
    """一致性管理器

    负责维护小说/剧本的一致性：
    1. 角色状态表更新
    2. 前文摘要更新
    3. 一致性检查
    4. 伏笔追踪
    """

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider
        self.logger = get_logger("consistency_manager")

    def set_llm_provider(self, llm_provider):
        """设置LLM提供者"""
        self.llm_provider = llm_provider

    async def initialize_project_files(self, project: NovelProject) -> bool:
        """
        初始化项目文件（摘要、角色状态等）

        Args:
            project: 项目对象

        Returns:
            是否成功
        """
        try:
            # 创建项目目录
            project_dir = os.path.dirname(
                project.summary_file) if project.summary_file else None
            if project_dir and not os.path.exists(project_dir):
                os.makedirs(project_dir, exist_ok=True)

            # 初始化摘要文件
            if project.summary_file:
                async with aiofiles.open(project.summary_file, 'w', encoding='utf-8') as f:
                    await f.write("")  # 空文件

            # 初始化角色状态文件
            if project.characters_file:
                async with aiofiles.open(project.characters_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps({}))

            self.logger.info("项目文件初始化完成")
            return True

        except Exception as e:
            self.logger.error(f"初始化项目文件失败: {str(e)}")
            return False

    async def update_summary(
        self,
        project: NovelProject,
        chapter_number: int,
        chapter_title: str,
        chapter_content: str
    ) -> str:
        """
        更新前文摘要

        Args:
            project: 项目对象
            chapter_number: 章节号
            chapter_title: 章节标题
            chapter_content: 章节内容

        Returns:
            更新后的摘要
        """
        try:
            # 读取当前摘要
            current_summary = ""
            if project.summary_file and os.path.exists(project.summary_file):
                async with aiofiles.open(project.summary_file, 'r', encoding='utf-8') as f:
                    current_summary = await f.read()

            # 如果有LLM，使用AI更新摘要
            if self.llm_provider:
                # 核心约束：禁止对chapter_content做字符串切片
                # 完整传入章节内容，由LLM自行处理关键信息提取
                prompt = SUMMARY_UPDATE_PROMPT.format(
                    current_summary=current_summary or "（暂无前文摘要）",
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    chapter_content=chapter_content  # 完整传入，不做切片
                )

                llm_response = await self.llm_provider.generate(prompt)

                # 提取响应内容（LLMResponse是Pydantic模型）
                new_summary = llm_response.content if hasattr(
                    llm_response, 'content') else str(llm_response)

                # 清理可能的markdown标记
                new_summary = self._clean_llm_output(new_summary)
            else:
                # 无LLM时简单追加（完整内容，不再截断）
                new_summary = current_summary + \
                    f"\n第{chapter_number}章: {chapter_title}\n{chapter_content}"

            # 保存新摘要
            if project.summary_file:
                async with aiofiles.open(project.summary_file, 'w', encoding='utf-8') as f:
                    await f.write(new_summary)

            self.logger.info(f"摘要更新完成: 第{chapter_number}章")
            return new_summary

        except Exception as e:
            self.logger.error(f"更新摘要失败: {str(e)}")
            return ""

    async def update_character_state(
        self,
        project: NovelProject,
        chapter_number: int,
        chapter_title: str,
        chapter_content: str
    ) -> Dict[str, Any]:
        """
        更新角色状态表

        Args:
            project: 项目对象
            chapter_number: 章节号
            chapter_title: 章节标题
            chapter_content: 章节内容

        Returns:
            更新后的角色状态
        """
        try:
            # 读取当前角色状态（增强错误处理）
            current_state = {}
            if project.characters_file:
                if os.path.exists(project.characters_file):
                    try:
                        async with aiofiles.open(project.characters_file, 'r', encoding='utf-8') as f:
                            content = await f.read()
                        current_state = json.loads(content)
                    except json.JSONDecodeError as je:
                        self.logger.warning(f"角色状态文件JSON格式错误: {je}")
                        current_state = {}
                else:
                    # 文件不存在时自动创建
                    self.logger.info("角色状态文件不存在，自动创建")
                    project_dir = os.path.dirname(project.characters_file)
                    if project_dir and not os.path.exists(project_dir):
                        os.makedirs(project_dir, exist_ok=True)
                    async with aiofiles.open(project.characters_file, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps({}))

            # 如果有LLM，使用AI更新角色状态
            if self.llm_provider:
                try:
                    # 核心约束：禁止对chapter_content做字符串切片
                    # 完整传入章节内容，由LLM自行处理
                    prompt = CHARACTER_UPDATE_PROMPT.format(
                        current_state=json.dumps(
                            current_state, ensure_ascii=False, indent=2),
                        chapter_number=chapter_number,
                        chapter_title=chapter_title,
                        chapter_content=chapter_content  # 完整传入，不做切片
                    )

                    response = await self.llm_provider.generate(prompt)

                    # 提取响应内容（LLMResponse是Pydantic模型）
                    response_text = response.content if hasattr(
                        response, 'content') else str(response)

                    # 解析JSON响应
                    new_state = self._parse_json_response(response_text)

                    if new_state:
                        current_state = new_state
                    else:
                        self.logger.warning(
                            f"第{chapter_number}章角色状态LLM响应解析失败，保留原状态")
                except Exception as llm_error:
                    self.logger.warning(
                        f"第{chapter_number}章角色状态LLM调用失败: {llm_error}，使用简单提取")
                    # LLM失败时回退到简单提取
                    self._simple_character_extraction(
                        chapter_content, current_state)
            else:
                # 无LLM时尝试提取角色名
                self._simple_character_extraction(
                    chapter_content, current_state)

            # 保存新状态
            if project.characters_file:
                async with aiofiles.open(project.characters_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(current_state, ensure_ascii=False, indent=2))

            self.logger.info(f"角色状态更新完成: 第{chapter_number}章")
            return current_state

        except Exception as e:
            self.logger.error(f"更新角色状态失败: {str(e)}")
            return {}

    async def check_consistency(
        self,
        project: NovelProject,
        chapter_number: int,
        chapter_title: str,
        chapter_content: str
    ) -> Dict[str, Any]:
        """
        一致性检查

        Args:
            project: 项目对象
            chapter_number: 章节号
            chapter_title: 章节标题
            chapter_content: 章节内容

        Returns:
            检查结果
        """
        result = {
            "has_conflict": False,
            "conflicts": [],
            "warnings": [],
            "suggestions": []
        }

        if not self.llm_provider:
            return result

        try:
            # 获取必要的上下文
            novel_setting = project.outline_content or ""

            character_state = ""
            if project.characters_file and os.path.exists(project.characters_file):
                async with aiofiles.open(project.characters_file, 'r', encoding='utf-8') as f:
                    character_state = await f.read()

            global_summary = ""
            if project.summary_file and os.path.exists(project.summary_file):
                async with aiofiles.open(project.summary_file, 'r', encoding='utf-8') as f:
                    global_summary = await f.read()

            # 执行一致性检查
            # 注意：novel_setting/character_state/global_summary的[:1000]切片
            # 用于一致性检查的上下文构建，非正文生成提示词，属于可接受范围
            # 但仍建议未来使用SemanticCompressor替代
            prompt = CONSISTENCY_CHECK_PROMPT.format(
                novel_setting=novel_setting,
                character_state=character_state or "暂无角色状态",
                global_summary=global_summary or "暂无前文摘要",
                plot_arcs="暂无记录的未解决冲突",
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_content=chapter_content
            )

            response = await self.llm_provider.generate(prompt)

            # 提取响应内容（LLMResponse是Pydantic模型）
            response_text = response.content if hasattr(
                response, 'content') else str(response)

            # 解析检查结果
            result = self._parse_consistency_result(response_text)

            self.logger.info(f"一致性检查完成: 第{chapter_number}章")
            return result

        except Exception as e:
            self.logger.error(f"一致性检查失败: {str(e)}")
            return result

    def _clean_llm_output(self, text: str) -> str:
        """清理LLM输出"""
        # 移除可能的markdown代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return text.strip()

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析JSON响应"""
        try:
            result = json.loads(response)
            if isinstance(result, dict):
                return result
            return None
        except json.JSONDecodeError as e:
            self.logger.warning(f"一致性检查JSON解析失败: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"一致性检查JSON解析失败: {e}")
            return None

    def _simple_character_extraction(self, content: str, current_state: Dict[str, Any]):
        """简单的角色名提取（无LLM时使用）"""
        # 使用简单的模式匹配提取可能的角色名
        import re

        # 匹配引号中的对话前的名字
        patterns = [
            r'"([^"]+)"[^\w]*?说',  # 中文双引号
            r'"([^"]+)"[^\w]*?说',  # 中文双引号（另一方向）
            r'"([^"]+)"[^\w]*?说',  # 英文引号
        ]

        for pattern in patterns:
            try:
                matches = re.findall(pattern, content)
                for name in matches:
                    if name and name not in current_state:
                        current_state[name] = {
                            "状态": {"心理状态": "未知"},
                            "关系网": {}
                        }
            except re.error as e:
                self.logger.warning(f"正则表达式匹配失败: {str(e)}")

    def _parse_consistency_result(self, response: str) -> Dict[str, Any]:
        """解析一致性检查结果"""
        result = {
            "has_conflict": False,
            "conflicts": [],
            "warnings": [],
            "suggestions": []
        }

        if "无明显冲突" in response:
            return result

        result["has_conflict"] = True

        # 尝试解析冲突列表
        lines = response.split("\n")
        current_conflict = {}

        for line in lines:
            line = line.strip()
            if line.startswith("冲突类型:"):
                if current_conflict:
                    result["conflicts"].append(current_conflict)
                current_conflict = {"type": line.replace("冲突类型:", "").strip()}
            elif line.startswith("冲突描述:"):
                current_conflict["description"] = line.replace(
                    "冲突描述:", "").strip()
            elif line.startswith("涉及内容:"):
                current_conflict["content"] = line.replace("涉及内容:", "").strip()
            elif line.startswith("建议修改:"):
                current_conflict["suggestion"] = line.replace(
                    "建议修改:", "").strip()
                if current_conflict not in result["conflicts"]:
                    result["conflicts"].append(current_conflict)
                current_conflict = {}

        return result

    async def finalize_chapter(
        self,
        project: NovelProject,
        chapter: NovelChapter,
        chapter_content: str
    ) -> Dict[str, Any]:
        """
        章节定稿处理

        执行所有一致性相关的更新操作

        Args:
            project: 项目对象
            chapter: 章节对象
            chapter_content: 章节内容

        Returns:
            处理结果
        """
        results = {
            "summary_updated": False,
            "characters_updated": False,
            "consistency_check": None
        }

        try:
            # 1. 更新前文摘要
            new_summary = await self.update_summary(
                project,
                chapter.chapter_number,
                chapter.chapter_title or f"第{chapter.chapter_number}章",
                chapter_content
            )
            results["summary_updated"] = bool(new_summary)

            # 2. 更新角色状态
            new_characters = await self.update_character_state(
                project,
                chapter.chapter_number,
                chapter.chapter_title or f"第{chapter.chapter_number}章",
                chapter_content
            )
            results["characters_updated"] = bool(new_characters)

            # 3. 一致性检查（可选）
            if project.generation_config and project.generation_config.get("consistency_check_enabled"):
                results["consistency_check"] = await self.check_consistency(
                    project,
                    chapter.chapter_number,
                    chapter.chapter_title or f"第{chapter.chapter_number}章",
                    chapter_content
                )

            self.logger.info(f"章节定稿处理完成: 第{chapter.chapter_number}章")
            return results

        except Exception as e:
            self.logger.error(f"章节定稿处理失败: {str(e)}")
            return results
