"""CharacterStateTracker - extract_knowledge_graph_from_contentMixin"""
from __future__ import annotations
from typing import Dict
from typing import Any
import re


class ExtractKnowledgeGraphFromContentMixin:
    """extract_knowledge_graph_from_content功能域"""

    async def extract_knowledge_graph_from_content(
        self,
        content: str,
        chapter_num: int,
        llm_provider=None
    ) -> Dict[str, Any]:
        """从前文内容中提取知识图谱信息（架构优化新增）

        使用NovelKnowledgeGraph工具从前文正文中提取实体和关系信息，
        包括人物、地点、事件、人物状态变化等。

        Args:
            content: 前文正文内容
            chapter_num: 章节号
            llm_provider: LLM提供者（用于提取）

        Returns:
            提取的知识图谱信息字典
        """
        try:
            from app.tools.novel_graph_rag import NovelKnowledgeGraph

            # 创建临时知识图谱用于提取
            temp_graph_path = None  # 不持久化
            knowledge_graph = NovelKnowledgeGraph(persist_path=temp_graph_path)

            # 使用LLM提取实体和关系
            if llm_provider:
                extraction_result = await knowledge_graph.extract_from_content(
                    content=content,
                    chapter_num=chapter_num,
                    llm_provider=llm_provider
                )

                # 将提取结果同步到追踪器
                if extraction_result:
                    self._sync_extraction_to_tracker(
                        extraction_result, chapter_num)

                return extraction_result
            else:
                # 无LLM提供者，使用简单的规则提取
                return self._simple_extraction(content, chapter_num)

        except Exception as e:
            self.logger.error(f"从前文内容提取知识图谱失败: {e}")
            return {}


    def _sync_extraction_to_tracker(
        self,
        extraction_result: Dict[str, Any],
        chapter_num: int
    ) -> None:
        """将知识图谱提取结果同步到追踪器"""
        try:
            entities = extraction_result.get("entities", [])

            for entity in entities:
                entity_type = entity.get("type", "")
                character = entity.get("character", "")
                text = entity.get("text", "")
                description = entity.get("description", "")

                # 只处理人物状态相关实体
                if entity_type == "身份变化" and character:
                    self.update_character_state(
                        character,
                        {"identity": text, "status_change": description},
                        chapter_num=chapter_num
                    )
                elif entity_type == "位置变化" and character:
                    self.update_character_state(
                        character,
                        {"location": text},
                        chapter_num=chapter_num
                    )
                elif entity_type == "关系变化" and character:
                    self._parse_relationship_change(
                        character, text, description)

        except Exception as e:
            self.logger.error(f"同步知识图谱提取结果失败: {e}")


    def _simple_extraction(self, content: str, chapter_num: int) -> Dict[str, Any]:
        """简单的规则提取（无LLM时的备选方案）"""
        result = {
            "entities": [],
            "relations": []
        }

        # 使用已有的人物检测方法
        new_chars = self.detect_new_characters(content)

        for char_name in new_chars:
            result["entities"].append({
                "text": char_name,
                "type": "人物",
                "level": "macro",
                "chapter": chapter_num,
                "description": f"第{chapter_num}章新登场人物"
            })

        return result


