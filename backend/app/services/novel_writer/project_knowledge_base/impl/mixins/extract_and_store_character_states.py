"""ProjectKnowledgeBase - extract_and_store_character_statesMixin"""
from typing import Dict
from typing import List
from typing import Any
import re


class ExtractAndStoreCharacterStatesMixin:
    """extract_and_store_character_states功能域"""

    async def extract_and_store_character_states(
        self,
        project_id: int,
        unit_number: int,
        chapter_content: str,
        llm_provider=None,
        known_characters: List[str] = None
    ) -> Dict[str, Any]:
        """
        提取并存储章节中的人物状态实体

        在章节生成后调用，提取人物状态变化实体并存储到单元图谱中。

        Args:
            project_id: 项目ID
            unit_number: 单元号（章节号）
            chapter_content: 章节内容
            llm_provider: LLM提供者
            known_characters: 已知人物列表

        Returns:
            提取结果
        """
        result = {
            "success": False,
            "entity_count": 0,
            "relation_count": 0,
            "error": None
        }

        try:
            if not llm_provider:
                result["error"] = "缺少LLM提供者"
                return result

            # 加载单元图谱
            graph_path = self.get_graph_path(project_id, unit_number)
            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
            knowledge_graph.load()

            # 提取人物状态实体
            extractor = NovelEntityExtractor(llm_provider=llm_provider)
            state_result = await extractor.extract_character_states(
                chapter_content=chapter_content,
                chapter_num=unit_number,
                known_characters=known_characters
            )

            entities = state_result.get("entities", [])
            relations = state_result.get("relations", [])

            # 添加实体到图谱
            for entity in entities:
                knowledge_graph.add_entity({
                    "text": entity.get("text", ""),
                    "type": entity.get("type", "未知"),
                    "level": "micro",
                    "description": entity.get("description", ""),
                    "character": entity.get("character", ""),
                    "chapter": entity.get("chapter", unit_number)
                }, doc_id=f"unit_{unit_number}_state")

            # 添加关系到图谱
            for relation in relations:
                knowledge_graph.add_relation({
                    "source": relation.get("source", ""),
                    "target": relation.get("target", ""),
                    "relation": relation.get("relation", "关联"),
                    "context": relation.get("context", "")
                }, doc_id=f"unit_{unit_number}_state")

            # 保存图谱
            knowledge_graph.save()

            result["success"] = True
            result["entity_count"] = len(entities)
            result["relation_count"] = len(relations)

            self.logger.info(
                f"人物状态实体提取完成: project_id={project_id}, unit={unit_number}, "
                f"entities={len(entities)}, relations={len(relations)}")

            return result

        except Exception as e:
            self.logger.error(
                f"提取人物状态实体失败: project_id={project_id}, unit={unit_number}, error={str(e)}")
            result["error"] = str(e)
            return result


