"""ProjectKnowledgeBase - build_unit_outline_graphMixin"""
from typing import Dict
from typing import Any
from datetime import datetime
import re
import time


class BuildUnitOutlineGraphMixin:
    """build_unit_outline_graph功能域"""

    async def build_unit_outline_graph(
        self,
        project_id: int,
        unit_number: int,
        unit_outline_content: str,
        llm_provider=None
    ) -> Dict[str, Any]:
        """
        构建单元大纲的知识图谱

        Args:
            project_id: 项目ID
            unit_number: 单元号（章节号/集数/场景号）
            unit_outline_content: 单元大纲内容
            llm_provider: LLM提供者

        Returns:
            构建结果
        """
        result = {
            "success": False,
            "entity_count": 0,
            "relation_count": 0,
            "graph_path": None,
            "error": None
        }

        try:
            self.logger.info(
                f"开始构建单元大纲图谱: project_id={project_id}, unit={unit_number}")

            # 1. 创建单元知识图谱（使用正文板块专属的独立系统）
            graph_path = self.get_graph_path(
                project_id, unit_number=unit_number)
            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)

            # 2. 提取实体和关系（使用正文板块专属的独立提取器）
            if llm_provider:
                extractor = NovelEntityExtractor(llm_provider=llm_provider)

                extraction_result = await extractor.extract_with_llm(unit_outline_content)
                entities = extraction_result.get("entities", [])
                relations = extraction_result.get("relations", [])
            else:
                # 没有LLM提供者时，返回空结果
                self.logger.warning("没有LLM提供者，无法提取实体和关系")
                entities = []
                relations = []

            # 3. 添加实体到图谱
            for entity in entities:
                knowledge_graph.add_entity({
                    "text": entity.get("text", entity.get("name", "")),
                    "type": entity.get("type", "未知"),
                    "description": entity.get("description", "")
                }, doc_id=f"unit_{unit_number}")

            # 4. 添加关系到图谱（过滤非正文板块专用关系类型）
            # 定义正文板块专用的关系类型（与文档定义一致）
            valid_relation_types = {
                # 宏观层内部关系
                "体现于", "属于", "包含", "影响",
                # 宏观与微观之间的桥梁关系
                "经历", "参与", "展开为", "约束", "渗透于", "定位", "发生于",
                # 微观层内部关系
                "前序", "导致", "包含冲突", "触发于", "发生于事件", "包含事件", "关联", "关联人物"
            }

            # 定义禁止使用的关系类型（公共知识库专用）
            # 这些关系类型会连接到公共知识库，必须严格过滤
            forbidden_relation_types = {
                "体现了", "应用了", "符合", "违背了",
                "衍生自", "互补于", "应用于", "限制于",
                # 额外禁止的关系类型（确保完全过滤）
                "基于", "理论依据", "科学基础", "核心技能支撑"
            }

            self.logger.info(f"[单元图谱] 开始过滤关系: 共{len(relations)}个关系")

            filtered_relations = 0
            added_relations = 0
            for relation in relations:
                rel_type = relation.get("relation", relation.get("type", "相关"))

                # 过滤禁止的关系类型
                if rel_type in forbidden_relation_types:
                    self.logger.warning(
                        f"[单元图谱] 过滤禁止的关系类型: '{rel_type}' (公共知识库专用)")
                    filtered_relations += 1
                    continue

                knowledge_graph.add_relation({
                    "source": relation.get("source", relation.get("head", "")),
                    "target": relation.get("target", relation.get("tail", "")),
                    "relation": rel_type,
                    "context": relation.get("context", "")
                }, doc_id=f"unit_{unit_number}")
                added_relations += 1

            self.logger.info(
                f"[单元图谱] 关系过滤完成: 共{len(relations)}个, 过滤{filtered_relations}个, 添加{added_relations}个")

            # 5. 保存图谱
            knowledge_graph.save()

            # 6. 存入向量数据库（带单元标签）
            collection_name = self.get_collection_name(project_id)

            documents = []
            metadatas = []
            ids = []

            for i, entity in enumerate(entities):
                entity_text = entity.get("text", entity.get("name", ""))
                entity_type = entity.get("type", "未知")
                entity_desc = entity.get("description", "")

                doc_content = f"【{entity_type}】{entity_text}"
                if entity_desc:
                    doc_content += f"\n{entity_desc}"

                documents.append(doc_content)
                metadatas.append({
                    "doc_type": self.DOC_TYPE_UNIT,
                    "entity_type": entity_type,
                    "entity_name": entity_text,
                    "unit_number": unit_number,
                    "created_at": datetime.now().isoformat()
                })
                ids.append(f"unit_{unit_number}_entity_{i}")

            # 添加关系文档
            for i, relation in enumerate(relations):
                source = relation.get("source", relation.get("head", ""))
                target = relation.get("target", relation.get("tail", ""))
                rel_type = relation.get("relation", relation.get("type", "相关"))
                context = relation.get("context", "")

                doc_content = f"【关系】{source} --[{rel_type}]--> {target}"
                if context:
                    doc_content += f"\n{context}"

                documents.append(doc_content)
                metadatas.append({
                    "doc_type": self.DOC_TYPE_UNIT,
                    "entity_type": "relationship",
                    "source": source,
                    "target": target,
                    "relation_type": rel_type,
                    "unit_number": unit_number,
                    "created_at": datetime.now().isoformat()
                })
                ids.append(f"unit_{unit_number}_relation_{i}")

            # 批量添加到向量库（使用异步版本，带串行化、重试和验证机制）
            if documents:
                try:
                    vector_result = await self.vector_store.add_documents_async(
                        collection_name=collection_name,
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids,
                        verify=True  # 启用写入验证
                    )

                    if not vector_result.get("success"):
                        self.logger.error(
                            f"单元大纲向量库写入失败: project_id={project_id}, unit={unit_number}, "
                            f"error={vector_result.get('error')}"
                        )
                        result["vector_store_error"] = vector_result.get(
                            "error", "Unknown error")
                    elif not vector_result.get("verified"):
                        self.logger.warning(
                            f"单元大纲向量库写入验证失败（图谱数据已保存）: project_id={project_id}, "
                            f"unit={unit_number}"
                        )
                        result["vector_store_warning"] = "写入验证失败"
                    else:
                        self.logger.info(
                            f"单元大纲向量库写入验证通过: project_id={project_id}, unit={unit_number}, "
                            f"count={vector_result.get('count', 0)}"
                        )

                except Exception as vec_error:
                    # 向量库写入失败不影响图谱数据保存
                    self.logger.warning(
                        f"单元大纲向量存储异常（图谱数据已保存）: project_id={project_id}, "
                        f"unit={unit_number}, error={str(vec_error)[:100]}"
                    )
                    result["vector_store_error"] = str(vec_error)

            result["success"] = True
            result["entity_count"] = len(entities)
            result["relation_count"] = len(relations)
            result["graph_path"] = graph_path

            self.logger.info(
                f"单元大纲图谱构建完成: project_id={project_id}, unit={unit_number}, "
                f"entities={len(entities)}, relations={len(relations)}"
            )

            return result

        except Exception as e:
            self.logger.error(
                f"构建单元大纲图谱失败: project_id={project_id}, unit={unit_number}, error={str(e)}"
            )
            result["error"] = str(e)
            return result


