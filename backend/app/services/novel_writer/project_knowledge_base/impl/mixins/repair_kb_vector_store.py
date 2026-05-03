"""ProjectKnowledgeBase - RepairKbVectorStoreMixin

当 ChromaDB HNSW 索引因异常关闭而损坏时，从知识图谱 JSON 文件重建向量库。
这是"持久化图谱（JSON）→ 向量库"的修复通道，向量库仅作为缓存/索引存在。
"""
import os
import json
from datetime import datetime
from typing import Dict, Any


class RepairKbVectorStoreMixin:
    """repair_kb_vector_store 功能域"""

    async def repair_kb_vector_store(self, project_id: int) -> Dict[str, Any]:
        """
        从知识图谱 JSON 文件重建向量库

        适用场景：
        - ChromaDB HNSW 索引损坏（Nothing found on disk）
        - 后台终端异常关闭导致索引文件丢失

        Args:
            project_id: 项目ID

        Returns:
            修复结果
        """
        result = {
            "success": False,
            "entity_count": 0,
            "relation_count": 0,
            "action": "noop",
            "message": ""
        }

        collection_name = self.get_collection_name(project_id)
        graph_path = self.get_graph_path(project_id, unit_number=None)

        # 1. 检查 KG JSON 是否存在
        if not os.path.exists(graph_path):
            result["message"] = f"知识图谱 JSON 文件不存在: {graph_path}"
            self.logger.warning(f"[KB修复] {result['message']}")
            return result

        # 2. 加载知识图谱
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            result["message"] = f"知识图谱 JSON 文件读取失败: {e}"
            self.logger.error(f"[KB修复] {result['message']}")
            return result

        # 3. 提取实体和关系
        entities = graph_data.get("entities", graph_data.get("nodes", []))
        relations = graph_data.get("relations", graph_data.get("edges", []))

        if not entities:
            result["message"] = "知识图谱 JSON 中无实体数据"
            self.logger.warning(f"[KB修复] {result['message']}")
            return result

        # 统一格式：列表/字典兼容
        if isinstance(entities, dict):
            entities = [
                {"text": k, "type": v.get("type", "未知"), "description": v.get("description", "")}
                for k, v in entities.items()
            ]
        if isinstance(relations, dict):
            relations = [
                {"source": k, "target": v.get("target", ""), "relation": v.get("type", "相关"), "context": v.get("context", "")}
                for k, v in relations.items()
            ]

        self.logger.info(
            f"[KB修复] 从KG JSON加载: project_id={project_id}, "
            f"实体数={len(entities)}, 关系数={len(relations)}"
        )

        # 4. 删除旧向量集合（如果存在且损坏）
        try:
            self.vector_store.delete_collection(collection_name)
            self.logger.info(f"[KB修复] 已删除旧向量集合: {collection_name}")
        except Exception:
            self.logger.debug(f"[KB修复] 删除旧集合失败（可能已不存在）: {collection_name}")

        # 5. 重建向量文档
        documents = []
        metadatas = []
        ids = []

        for i, entity in enumerate(entities):
            entity_text = entity.get("text", entity.get("name", ""))
            entity_type = entity.get("type", "未知")
            entity_desc = entity.get("description", "")
            if not entity_text or not entity_text.strip():
                continue

            doc_content = f"【{entity_type}】{entity_text}"
            if entity_desc:
                doc_content += f"\n{entity_desc}"

            documents.append(doc_content)
            metadatas.append({
                "doc_type": "global",
                "entity_type": entity_type,
                "entity_name": entity_text,
                "unit_number": 0,
                "created_at": datetime.now().isoformat()
            })
            ids.append(f"global_entity_repair_{project_id}_{i}")

        for i, relation in enumerate(relations):
            source = relation.get("source", relation.get("head", ""))
            target = relation.get("target", relation.get("tail", ""))
            rel_type = relation.get("relation", relation.get("type", "相关"))
            context = relation.get("context", "")
            if not source or not target:
                continue

            doc_content = f"【关系】{source} --[{rel_type}]--> {target}"
            if context:
                doc_content += f"\n{context}"

            documents.append(doc_content)
            metadatas.append({
                "doc_type": "global",
                "entity_type": "relationship",
                "source": source,
                "target": target,
                "relation_type": rel_type,
                "unit_number": 0,
                "created_at": datetime.now().isoformat()
            })
            ids.append(f"global_relation_repair_{project_id}_{i}")

        if not documents:
            result["message"] = "无有效文档可写入向量库"
            return result

        # 6. 写入向量库
        add_result = self.vector_store.add_documents(
            collection_name=collection_name,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            verify=True
        )

        # 7. 清除修复标记
        if hasattr(self.vector_store, 'clear_repaired_flag'):
            self.vector_store.clear_repaired_flag(collection_name)

        result["success"] = True
        result["entity_count"] = len(entities)
        result["relation_count"] = len(relations)
        result["document_count"] = len(documents)
        result["action"] = "rebuilt"
        result["message"] = (
            f"向量库修复成功: {len(entities)}个实体, {len(relations)}个关系, "
            f"共{len(documents)}个文档"
        )

        self.logger.info(f"[KB修复] {result['message']}")
        return result
