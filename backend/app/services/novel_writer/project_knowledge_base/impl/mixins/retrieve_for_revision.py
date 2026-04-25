"""ProjectKnowledgeBase - retrieve_for_revisionMixin"""
from typing import Dict
from typing import Any
import re
import time


class RetrieveForRevisionMixin:
    """retrieve_for_revision功能域"""

    async def retrieve_for_revision(
        self,
        project_id: int,
        current_unit: int,
        query_text: str,
        n_results: int = 10
    ) -> Dict[str, Any]:
        """
        检索知识库内容用于正文修正

        检索范围：
        1. 全局大纲图谱（世界观、人物设定、关键事件）
        2. 当前单元大纲图谱（本单元情节、角色、场景）

        严禁引入其他单元大纲内容

        Args:
            project_id: 项目ID
            current_unit: 当前单元号
            query_text: 查询文本
            n_results: 返回结果数量

        Returns:
            检索结果
        """
        result = {
            "global_entities": [],
            "global_relations": [],
            "unit_entities": [],
            "unit_relations": [],
            "combined_context": ""
        }

        try:
            collection_name = self.get_collection_name(project_id)

            # 诊断：检查向量库集合状态
            try:
                doc_count = self.vector_store.count_documents(collection_name)
                self.logger.info(
                    f"向量库集合状态: collection={collection_name}, doc_count={doc_count}")
            except Exception as count_err:
                self.logger.warning(
                    f"无法获取向量库文档数: {count_err}")
                doc_count = 0

            # 1. 检索全局大纲内容
            global_results = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query_text],
                n_results=n_results,
                where={"doc_type": self.DOC_TYPE_GLOBAL}
            )

            # 诊断：记录查询结果
            if global_results:
                docs_count = len(global_results.get("documents", [[]])[
                                 0]) if global_results.get("documents") else 0
                self.logger.info(
                    f"全局大纲查询结果: collection={collection_name}, docs_found={docs_count}")
            else:
                self.logger.warning(
                    f"全局大纲查询返回空结果: collection={collection_name}")

            if global_results and global_results.get("documents"):
                for i, doc in enumerate(global_results["documents"][0]):
                    metadata = global_results.get("metadatas", [[]])[
                        0][i] if global_results.get("metadatas") else {}
                    entity_type = metadata.get("entity_type", "unknown")

                    if entity_type == "relationship":
                        result["global_relations"].append({
                            "content": doc,
                            "metadata": metadata
                        })
                    else:
                        result["global_entities"].append({
                            "content": doc,
                            "metadata": metadata
                        })

            # 2. 检索当前单元大纲内容（严禁其他单元）
            unit_results = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query_text],
                n_results=n_results,
                where={
                    "$and": [
                        {"doc_type": self.DOC_TYPE_UNIT},
                        {"unit_number": current_unit}
                    ]
                }
            )

            if unit_results and unit_results.get("documents"):
                for i, doc in enumerate(unit_results["documents"][0]):
                    metadata = unit_results.get("metadatas", [[]])[
                        0][i] if unit_results.get("metadatas") else {}
                    entity_type = metadata.get("entity_type", "unknown")

                    if entity_type == "relationship":
                        result["unit_relations"].append({
                            "content": doc,
                            "metadata": metadata
                        })
                    else:
                        result["unit_entities"].append({
                            "content": doc,
                            "metadata": metadata
                        })

            # 3. 构建组合上下文
            context_parts = []

            if result["global_entities"]:
                context_parts.append("【全局设定 - 人物与实体】")
                context_parts.extend([e["content"]
                                     for e in result["global_entities"][:5]])

            if result["global_relations"]:
                context_parts.append("\n【全局设定 - 关系网络】")
                context_parts.extend([r["content"]
                                     for r in result["global_relations"][:3]])

            if result["unit_entities"]:
                context_parts.append("\n【本单元 - 人物与实体】")
                context_parts.extend([e["content"]
                                     for e in result["unit_entities"][:5]])

            if result["unit_relations"]:
                context_parts.append("\n【本单元 - 关系动态】")
                context_parts.extend([r["content"]
                                     for r in result["unit_relations"][:3]])

            # 4. 获取事件时间线（通过图关系查询）
            timeline_context = self._get_event_timeline(
                project_id, current_unit)
            if timeline_context:
                context_parts.append("\n【事件时间线】")
                context_parts.append(timeline_context)

            result["combined_context"] = "\n".join(context_parts)

            # 5. 如果向量库检索结果为空，尝试从图谱文件直接读取
            # 修复：只要 combined_context 为空就触发备选方案，不依赖 doc_count
            # 因为向量库可能有数据但查询条件不匹配（如 metadata 格式问题）
            if not result["combined_context"]:
                self.logger.info(
                    f"向量库检索结果为空，尝试从图谱文件直接读取: project_id={project_id}, "
                    f"doc_count={doc_count}"
                )
                result = self._retrieve_from_graph_files(
                    project_id, current_unit, result)

            self.logger.info(
                f"知识库检索完成: project_id={project_id}, unit={current_unit}, "
                f"global_entities={len(result['global_entities'])}, "
                f"unit_entities={len(result['unit_entities'])}, "
                f"has_context={bool(result['combined_context'])}"
            )

            return result

        except Exception as e:
            self.logger.error(
                f"知识库检索失败: project_id={project_id}, error={str(e)}")
            # 修复：即使向量库查询异常，也尝试从图谱文件读取数据
            try:
                result = self._retrieve_from_graph_files(
                    project_id, current_unit, result)
                if result["combined_context"]:
                    self.logger.info(
                        f"从图谱文件恢复成功: project_id={project_id}, "
                        f"global_entities={len(result['global_entities'])}, "
                        f"unit_entities={len(result['unit_entities'])}")
            except Exception as fallback_error:
                self.logger.error(
                    f"从图谱文件读取也失败: project_id={project_id}, error={str(fallback_error)}")
            return result


