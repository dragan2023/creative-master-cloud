"""ProjectKnowledgeBase - inherit_knowledge_graphMixin

知识图谱继承机制：
从源项目复制知识图谱到目标项目，无需LLM，秒级完成。
用于四阶段流程构建的知识图谱继承到写作工作台新建项目中。
"""
from typing import Dict, Any
from datetime import datetime
import json
import os
import shutil


class InheritKnowledgeGraphMixin:
    """inherit_knowledge_graph功能域"""

    # 文档类型常量（与其他Mixin保持一致）
    DOC_TYPE_GLOBAL = "global"

    async def inherit_knowledge_graph(
        self,
        src_project_id: int,
        dst_project_id: int
    ) -> Dict[str, Any]:
        """
        继承源项目的知识图谱到目标项目（无需LLM，秒级完成）

        执行流程:
        1. 复制图谱文件 project_{src}_global_graph.json → project_{dst}_global_graph.json
        2. 初始化目标项目KB（创建ChromaDB集合）
        3. 加载源图谱JSON，提取实体（nodes）和关系（edges）
        4. 将实体/关系向量化后添加到目标ChromaDB集合
        5. 返回 { entity_count, relation_count }

        Args:
            src_project_id: 源项目ID
            dst_project_id: 目标项目ID

        Returns:
            {"success": True/False, "entity_count": N, "relation_count": N, "error": "..."}
        """
        result: Dict[str, Any] = {
            "success": False,
            "entity_count": 0,
            "relation_count": 0,
            "error": None
        }

        try:
            src_graph_path = self.get_graph_path(src_project_id)
            dst_graph_path = self.get_graph_path(dst_project_id)

            # 1. 检查源图谱文件是否存在
            if not os.path.exists(src_graph_path):
                result["error"] = f"源项目知识图谱文件不存在: {src_graph_path}"
                self.logger.warning(result["error"])
                return result

            self.logger.info(
                f"[图谱继承] 开始: src={src_project_id} → dst={dst_project_id}, "
                f"src_path={src_graph_path}")

            # 2. 复制图谱文件
            os.makedirs(os.path.dirname(dst_graph_path), exist_ok=True)
            shutil.copy2(src_graph_path, dst_graph_path)
            self.logger.info(
                f"[图谱继承] 图谱文件已复制: {os.path.basename(dst_graph_path)}")

            # 3. 加载源图谱JSON
            with open(src_graph_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)

            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])

            self.logger.info(
                f"[图谱继承] 加载完成: nodes={len(nodes)}, edges={len(edges)}")

            # 4. 初始化目标项目KB
            await self.initialize_project_kb(dst_project_id)

            # 5. 构建向量文档
            collection_name = self.get_collection_name(dst_project_id)
            documents = []
            metadatas = []
            ids = []

            # 处理实体（nodes）
            for i, node in enumerate(nodes):
                entity_text = node.get("text", node.get("name", ""))
                entity_type = node.get("type", "未知")
                entity_desc = node.get("description", "")

                doc_content = f"【{entity_type}】{entity_text}"
                if entity_desc:
                    doc_content += f"\n{entity_desc}"

                documents.append(doc_content)
                metadatas.append({
                    "doc_type": self.DOC_TYPE_GLOBAL,
                    "entity_type": entity_type,
                    "entity_name": entity_text,
                    "unit_number": 0,
                    "created_at": datetime.now().isoformat()
                })
                ids.append(f"global_entity_{i}")

            # 处理关系（edges）
            for i, edge in enumerate(edges):
                source = edge.get("source", "")
                target = edge.get("target", "")
                rel_type = edge.get("relation", edge.get("type", "相关"))
                context = edge.get("context", "")

                doc_content = f"【关系】{source} --[{rel_type}]--> {target}"
                if context:
                    doc_content += f"\n{context}"

                documents.append(doc_content)
                metadatas.append({
                    "doc_type": self.DOC_TYPE_GLOBAL,
                    "entity_type": "relationship",
                    "source": source,
                    "target": target,
                    "relation_type": rel_type,
                    "unit_number": 0,
                    "created_at": datetime.now().isoformat()
                })
                ids.append(f"global_relation_{i}")

            # 6. 批量添加到向量库
            if documents:
                vector_result = self.vector_store.add_documents(
                    collection_name=collection_name,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                    verify=True
                )

                if not vector_result.get("success"):
                    self.logger.warning(
                        f"[图谱继承] 向量库写入失败: dst={dst_project_id}, "
                        f"error={vector_result.get('error')}")
                    result["vector_store_error"] = vector_result.get(
                        "error", "Unknown error")
                else:
                    self.logger.info(
                        f"[图谱继承] 向量库写入成功: dst={dst_project_id}, "
                        f"count={vector_result.get('count', 0)}")

            result["success"] = True
            result["entity_count"] = len(nodes)
            result["relation_count"] = len(edges)

            self.logger.info(
                f"[图谱继承] 完成: src={src_project_id} → dst={dst_project_id}, "
                f"entities={len(nodes)}, relations={len(edges)}")

        except json.JSONDecodeError as e:
            result["error"] = f"源图谱JSON解析失败: {str(e)}"
            self.logger.error(f"[图谱继承] JSON解析错误: {e}")
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(
                f"[图谱继承] 异常: src={src_project_id} → dst={dst_project_id}, "
                f"error={e!r}")

        return result
