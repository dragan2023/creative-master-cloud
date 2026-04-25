"""ProjectKnowledgeBase - build_global_outline_graphMixin"""
from typing import Dict
from typing import Optional
from typing import Any
from datetime import datetime
import re
import time


class BuildGlobalOutlineGraphMixin:
    """build_global_outline_graph功能域"""

    async def build_global_outline_graph(
        self,
        project_id: int,
        outline_content: str = None,
        llm_provider=None,
        progress_callback: Optional[callable] = None,
        project=None
    ) -> Dict[str, Any]:
        """
        构建全局大纲的知识图谱

        支持两阶段大纲生成机制：
        - 优先使用 global_outline_content（新版两阶段大纲）
        - 回退使用 outline_content（旧版兼容）

        Args:
            project_id: 项目ID
            outline_content: 全局大纲内容（可选，优先从project对象获取）
            llm_provider: LLM提供者（用于实体提取）
            progress_callback: 进度回调函数，签名为 async def callback(stage, progress, message)
            project: 项目对象（可选，用于获取两阶段大纲数据）

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

        async def report_progress(stage: str, progress: int, message: str):
            """内部进度报告辅助函数"""
            self.logger.info(f"[知识库构建] {stage}: {progress}% - {message}")
            if progress_callback:
                try:
                    await progress_callback(stage, progress, message)
                except Exception as e:
                    self.logger.warning(f"进度回调失败: {e}")

        try:
            await report_progress("initializing", 5, "正在初始化知识库...")
            self.logger.info(f"开始构建全局大纲图谱: project_id={project_id}")

            # 1. 初始化知识库（如果尚未初始化）
            await self.initialize_project_kb(project_id)
            await report_progress("initialized", 10, "知识库初始化完成")

            # 1.5 获取大纲内容（支持两阶段大纲机制）
            actual_outline_content = None
            outline_source = "unknown"

            # 优先使用传入的project对象（新版两阶段大纲）
            if project is not None:
                if hasattr(project, 'global_outline_content') and project.global_outline_content:
                    actual_outline_content = project.global_outline_content
                    outline_source = "global_outline_content"
                    self.logger.info(
                        f"使用两阶段全局大纲: global_outline_content, 长度={len(actual_outline_content)}")
                elif hasattr(project, 'outline_content') and project.outline_content:
                    actual_outline_content = project.outline_content
                    outline_source = "outline_content"
                    self.logger.info(
                        f"使用旧版大纲: outline_content, 长度={len(actual_outline_content)}")

            # 回退使用传入的outline_content参数
            if not actual_outline_content and outline_content:
                actual_outline_content = outline_content
                outline_source = "parameter"
                self.logger.info(
                    f"使用参数传入的大纲: 长度={len(actual_outline_content)}")

            # 最终检查
            if not actual_outline_content:
                error_msg = "无法获取大纲内容：project对象和outline_content参数均为空"
                self.logger.error(error_msg)
                result["error"] = error_msg
                await report_progress("failed", 0, error_msg)
                return result

            self.logger.info(
                f"大纲来源: {outline_source}, 内容长度: {len(actual_outline_content)}")

            # 2. 创建知识图谱（使用正文板块专属的独立系统）
            await report_progress("creating_graph", 15, "正在创建知识图谱结构...")
            graph_path = self.get_graph_path(project_id, unit_number=None)
            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)

            # 3. 使用LLM提取实体和关系（使用正文板块专属的独立提取器）
            await report_progress("extracting", 20, "正在提取实体和关系...")
            if llm_provider:
                # 使用正文板块专属的LLM实体提取器
                await report_progress("llm_extraction", 25, "正在使用LLM提取实体...")
                extractor = NovelEntityExtractor(llm_provider=llm_provider)

                extraction_result = await extractor.extract_with_llm(actual_outline_content)
                entities = extraction_result.get("entities", [])
                relations = extraction_result.get("relations", [])

                await report_progress("llm_extraction_done", 50,
                                      f"LLM提取完成: 发现{len(entities)}个实体, {len(relations)}个关系")
                self.logger.info(
                    f"LLM提取完成: entities={len(entities)}, relations={len(relations)}")
            else:
                # 没有LLM提供者时，返回空结果（正文板块不支持规则提取回退）
                self.logger.warning("没有LLM提供者，无法提取实体和关系")
                entities = []
                relations = []

            # 4.5 实体消歧和指代关系解析（后处理步骤）
            if entities and len(entities) > 1:
                await report_progress("entity_resolution", 52, "正在执行实体消歧...")

                resolution_result = self._resolve_entity_coreference(
                    entities=entities,
                    relations=relations,
                    context_content=actual_outline_content
                )

                original_entity_count = len(entities)
                entities = resolution_result.get("entities", [])
                relations = resolution_result.get("relations", [])
                merge_count = resolution_result.get("merge_count", 0)

                if merge_count > 0:
                    self.logger.info(
                        f"实体消歧完成: 原始{original_entity_count}个实体 → 消歧后{len(entities)}个实体 "
                        f"(合并了{merge_count}个别名实体)"
                    )
                    await report_progress(
                        "entity_resolution_done", 54,
                        f"实体消歧完成: 合并了{merge_count}个别名实体"
                    )
                else:
                    self.logger.info("实体消歧完成: 未发现需要合并的别名实体")

            # 5. 添加实体到图谱（支持分层结构）
            await report_progress("adding_entities", 55, f"正在添加{len(entities)}个实体到图谱...")
            entity_map = {}
            for i, entity in enumerate(entities):
                # 提取实体属性
                entity_text = entity.get("text", entity.get("name", ""))
                entity_type = entity.get("type", "未知")
                entity_level = entity.get(
                    "level", "macro" if entity_type in self.MACRO_ENTITY_TYPES else "micro")
                entity_desc = entity.get("description", "")
                entity_attrs = entity.get("attributes", {})

                # 构建实体数据，包含分层信息和属性
                entity_data = {
                    "text": entity_text,
                    "type": entity_type,
                    "level": entity_level,  # 宏观层或微观层
                    "description": entity_desc,
                    "attributes": entity_attrs  # 额外属性
                }

                node_id = knowledge_graph.add_entity(
                    entity_data, doc_id=f"global_outline")
                entity_map[entity_text] = node_id

                # 每处理20%的实体报告一次进度
                if (i + 1) % max(1, len(entities) // 5) == 0:
                    progress = 55 + (i + 1) * 5 // len(entities)
                    await report_progress("adding_entities_progress", progress,
                                          f"已添加{i + 1}/{len(entities)}个实体")

            # 5. 添加关系到图谱（过滤非正文板块专用关系类型）
            await report_progress("adding_relations", 60, f"正在添加{len(relations)}个关系到图谱...")

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

            self.logger.info(f"开始过滤关系: 共{len(relations)}个关系")
            self.logger.info(f"禁止关系类型: {forbidden_relation_types}")

            filtered_relations = 0
            added_relations = 0
            for relation in relations:
                relation_type = relation.get(
                    "relation", relation.get("type", "关联"))

                # 过滤禁止的关系类型
                if relation_type in forbidden_relation_types:
                    self.logger.warning(
                        f"[关系过滤] 过滤禁止的关系类型: '{relation_type}' (公共知识库专用)")
                    filtered_relations += 1
                    continue

                # 如果关系类型不在有效列表中，记录警告但仍然添加（允许自定义关系）
                if relation_type not in valid_relation_types:
                    self.logger.info(
                        f"[关系过滤] 使用非标准关系类型: '{relation_type}'")

                knowledge_graph.add_relation({
                    "source": relation.get("source", relation.get("head", "")),
                    "target": relation.get("target", relation.get("tail", "")),
                    "relation": relation_type,
                    "context": relation.get("context", "")
                }, doc_id="global_outline")
                added_relations += 1

            self.logger.info(
                f"关系过滤完成: 共{len(relations)}个, 过滤{filtered_relations}个, 添加{added_relations}个")

            # 6. 保存图谱
            await report_progress("saving_graph", 70, "正在保存知识图谱...")
            knowledge_graph.save()
            await report_progress("graph_saved", 75, "知识图谱保存完成")

            # 7. 存入向量数据库（用于语义检索）
            await report_progress("vectorizing", 80, "正在将知识向量化...")
            collection_name = self.get_collection_name(project_id)

            # 将实体和关系转为文档存入向量库
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
                    "doc_type": self.DOC_TYPE_GLOBAL,
                    "entity_type": entity_type,
                    "entity_name": entity_text,
                    "unit_number": 0,  # 全局大纲用0表示
                    "created_at": datetime.now().isoformat()
                })
                ids.append(f"global_entity_{i}")

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
                    "doc_type": self.DOC_TYPE_GLOBAL,
                    "entity_type": "relationship",
                    "source": source,
                    "target": target,
                    "relation_type": rel_type,
                    "unit_number": 0,  # 全局大纲用0表示
                    "created_at": datetime.now().isoformat()
                })
                ids.append(f"global_relation_{i}")

            # 批量添加到向量库（带验证）
            await report_progress("storing_vectors", 85, f"正在存储{len(documents)}个文档到向量库...")
            vector_result = {"success": True, "verified": False}
            if documents:
                try:
                    vector_result = self.vector_store.add_documents(
                        collection_name=collection_name,
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids,
                        verify=True  # 启用写入验证
                    )

                    if not vector_result.get("success"):
                        self.logger.error(
                            f"向量库写入失败: project_id={project_id}, error={vector_result.get('error')}"
                        )
                        result["vector_store_error"] = vector_result.get(
                            "error", "Unknown error")
                    elif not vector_result.get("verified"):
                        self.logger.warning(
                            f"向量库写入验证失败，但图谱数据已保存: project_id={project_id}"
                        )
                        result["vector_store_warning"] = "写入验证失败，数据可能需要重新构建"
                    else:
                        self.logger.info(
                            f"向量库写入验证通过: project_id={project_id}, count={vector_result.get('count', 0)}"
                        )

                except Exception as vec_error:
                    # 向量库写入失败不影响图谱数据保存
                    self.logger.warning(
                        f"向量库写入异常（图谱数据已保存）: project_id={project_id}, "
                        f"error={str(vec_error)[:200]}"
                    )
                    result["vector_store_error"] = str(vec_error)

            await report_progress("vectors_stored", 95, f"向量库存储完成: {len(documents)}个文档")

            result["success"] = True
            result["entity_count"] = len(entities)
            result["relation_count"] = len(relations)
            result["graph_path"] = graph_path

            await report_progress("completed", 100,
                                  f"知识库构建完成: {len(entities)}个实体, {len(relations)}个关系")
            self.logger.info(
                f"全局大纲图谱构建完成: project_id={project_id}, "
                f"entities={len(entities)}, relations={len(relations)}"
            )

            return result

        except Exception as e:
            self.logger.error(
                f"构建全局大纲图谱失败: project_id={project_id}, error={str(e)}")
            result["error"] = str(e)
            return result


