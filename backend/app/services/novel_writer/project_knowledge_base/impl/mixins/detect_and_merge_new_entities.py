"""ProjectKnowledgeBase - detect_and_merge_new_entitiesMixin"""
from typing import Dict
from typing import Any
import re


class DetectAndMergeNewEntitiesMixin:
    """detect_and_merge_new_entities功能域"""

    async def detect_and_merge_new_entities(
        self,
        project_id: int,
        chapter_content: str,
        chapter_num: int,
        llm_provider=None
    ) -> Dict[str, Any]:
        """
        检测章节内容中的新实体并合并到全局知识图谱

        这是一个主动式的实体检测方法，在章节生成后调用。
        使用LLM提取新出现的实体（人物、地点、组织、物品等）。

        Args:
            project_id: 项目ID
            chapter_content: 章节内容
            chapter_num: 章节号
            llm_provider: LLM提供者

        Returns:
            检测和合并结果
        """
        result = {
            "success": False,
            "new_characters": [],
            "new_locations": [],
            "new_organizations": [],
            "new_items": [],
            "new_concepts": [],
            "entities_added": 0,
            "relations_added": 0,
            "error": None
        }

        try:
            # 1. 加载全局图谱，获取已知实体
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            global_graph = NovelKnowledgeGraph(persist_path=global_graph_path)
            global_graph.load()

            # 获取已知实体列表
            known_entities = set(global_graph.entity_index.keys())

            # 2. 使用LLM提取实体
            if llm_provider:
                extractor = NovelEntityExtractor(llm_provider=llm_provider)
                extraction_result = await extractor.extract_with_llm(chapter_content)

                entities = extraction_result.get("entities", [])
                relations = extraction_result.get("relations", [])

                # 3. 筛选新实体并分类
                for entity in entities:
                    entity_text = entity.get("text", "")
                    entity_type = entity.get("type", "")

                    if entity_text in known_entities:
                        continue

                    # 添加到全局图谱
                    global_graph.add_entity(
                        {
                            "text": entity_text,
                            "type": entity_type,
                            "level": "micro",
                            "description": entity.get("description", ""),
                            "attributes": entity.get("attributes", {}),
                            "first_appearance_chapter": chapter_num
                        },
                        doc_id=f"chapter_{chapter_num}"
                    )
                    result["entities_added"] += 1

                    # 分类记录
                    if entity_type == "人物":
                        result["new_characters"].append(entity_text)
                    elif entity_type in ["地点", "位置"]:
                        result["new_locations"].append(entity_text)
                    elif entity_type in ["组织", "群体组织"]:
                        result["new_organizations"].append(entity_text)
                    elif entity_type in ["道具", "物品", "道具物品"]:
                        result["new_items"].append(entity_text)
                    else:
                        result["new_concepts"].append(entity_text)

                # 4. 添加新关系
                for relation in relations:
                    source = relation.get("source", relation.get("head", ""))
                    target = relation.get("target", relation.get("tail", ""))

                    # 只添加涉及新实体的关系
                    if source in known_entities and target in known_entities:
                        continue

                    global_graph.add_relation(
                        {
                            "source": source,
                            "target": target,
                            "relation": relation.get("relation", "关联"),
                            "context": relation.get("context", "")
                        },
                        doc_id=f"chapter_{chapter_num}"
                    )
                    result["relations_added"] += 1

                # 5. 保存全局图谱
                global_graph.save()
                result["success"] = True

                self.logger.info(
                    f"新实体检测完成: project={project_id}, chapter={chapter_num}, "
                    f"新实体={result['entities_added']}, 新关系={result['relations_added']}")

        except Exception as e:
            self.logger.error(
                f"检测新实体失败: project={project_id}, chapter={chapter_num}, error={str(e)}")
            result["error"] = str(e)

        return result


