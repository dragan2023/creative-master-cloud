"""
项目专属知识库管理器
管理正文生成板块的独立知识库系统，支持GraphRAG知识图谱生成与检索

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
import json
import re
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.vector_store import get_vector_store
# 使用正文板块专属的独立GraphRAG系统，不复用公共知识库代码
from app.tools.novel_graph_rag import NovelKnowledgeGraph, NovelEntityExtractor


class ProjectKnowledgeBase:
    """项目专属知识库管理器

    每个项目拥有独立的知识库，用于存储：
    1. 全局大纲的GraphRAG知识图谱
    2. 单元大纲的GraphRAG知识图谱（带单元标签）

    检索时支持：
    - 全局图谱检索
    - 指定单元图谱检索
    - 全局+指定单元组合检索（用于正文修正）
    """

    # 文档类型常量
    DOC_TYPE_GLOBAL = "global_outline"
    DOC_TYPE_UNIT = "unit_outline"

    # 实体类型常量 - 按照分层设计重新定义
    # 宏观层实体类型
    MACRO_ENTITY_TYPES = ["主题", "世界观规则", "人物",
                          "故事结构", "章节概要", "地点"]
    # 微观层实体类型
    MICRO_ENTITY_TYPES = ["详细事件", "核心冲突",
                          "角色发展弧", "关键对话", "情节线", "场景"]
    # 人物状态追踪实体类型
    CHARACTER_STATE_ENTITY_TYPES = [
        "身份变化", "位置变化", "关系变化", "性格发展",
        "能力成长", "心理状态", "行为模式"
    ]
    # 所有实体类型
    ENTITY_TYPES = MACRO_ENTITY_TYPES + \
        MICRO_ENTITY_TYPES + CHARACTER_STATE_ENTITY_TYPES

    def __init__(self, db: AsyncSession = None, persist_dir: str = None):
        """
        初始化项目知识库管理器

        Args:
            db: 数据库会话
            persist_dir: 持久化目录
        """
        self.db = db
        self.settings = get_settings()
        self.persist_dir = persist_dir or self.settings.get_knowledge_graph_dir()
        self.vector_store = get_vector_store()
        self.logger = get_logger("project_knowledge_base")

        # GraphRAG实例缓存（使用正文板块专属类型）
        self._graph_instances: Dict[int, NovelKnowledgeGraph] = {}

    def get_collection_name(self, project_id: int) -> str:
        """获取项目知识库的集合名称"""
        return f"project_{project_id}_kb"

    def get_graph_path(self, project_id: int, unit_number: Optional[int] = None) -> str:
        """
        获取知识图谱文件路径

        Args:
            project_id: 项目ID
            unit_number: 单元号，None表示全局大纲图谱

        Returns:
            图谱文件路径
        """
        if unit_number is None:
            filename = f"project_{project_id}_global_graph.json"
        else:
            filename = f"project_{project_id}_unit_{unit_number}_graph.json"
        return os.path.join(self.persist_dir, filename)

    async def initialize_project_kb(self, project_id: int) -> bool:
        """
        初始化项目专属知识库

        Args:
            project_id: 项目ID

        Returns:
            是否成功
        """
        try:
            collection_name = self.get_collection_name(project_id)

            # 创建向量集合
            self.vector_store.get_or_create_collection(collection_name)

            # 确保持久化目录存在
            os.makedirs(self.persist_dir, exist_ok=True)

            self.logger.info(
                f"项目知识库初始化完成: project_id={project_id}, collection={collection_name}")
            return True

        except Exception as e:
            self.logger.error(
                f"初始化项目知识库失败: project_id={project_id}, error={str(e)}")
            return False

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

    async def retrieve_global_only(
        self,
        project_id: int,
        query_text: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        仅检索全局大纲图谱内容

        用于获取世界观、人物设定等基础信息

        Args:
            project_id: 项目ID
            query_text: 查询文本
            n_results: 返回结果数量

        Returns:
            检索结果
        """
        result = {
            "entities": [],
            "relations": [],
            "combined_context": ""
        }

        try:
            collection_name = self.get_collection_name(project_id)

            query_result = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query_text],
                n_results=n_results,
                where={"doc_type": self.DOC_TYPE_GLOBAL}
            )

            if query_result and query_result.get("documents"):
                for i, doc in enumerate(query_result["documents"][0]):
                    metadata = query_result.get("metadatas", [[]])[
                        0][i] if query_result.get("metadatas") else {}
                    entity_type = metadata.get("entity_type", "unknown")

                    if entity_type == "relationship":
                        result["relations"].append(
                            {"content": doc, "metadata": metadata})
                    else:
                        result["entities"].append(
                            {"content": doc, "metadata": metadata})

            # 构建上下文
            context_parts = []
            if result["entities"]:
                context_parts.append("【人物与实体】")
                context_parts.extend([e["content"]
                                     for e in result["entities"]])
            if result["relations"]:
                context_parts.append("\n【关系网络】")
                context_parts.extend([r["content"]
                                     for r in result["relations"]])

            result["combined_context"] = "\n".join(context_parts)

            return result

        except Exception as e:
            self.logger.error(
                f"全局图谱检索失败: project_id={project_id}, error={str(e)}")
            return result

    def _retrieve_from_graph_files(
        self,
        project_id: int,
        current_unit: int,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        从图谱文件直接读取数据（向量库为空时的备选方案）

        Args:
            project_id: 项目ID
            current_unit: 当前单元号
            result: 已有的结果字典

        Returns:
            填充后的结果字典
        """
        try:
            context_parts = []

            # 1. 读取全局图谱
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if os.path.exists(global_graph_path):
                global_graph = NovelKnowledgeGraph(
                    persist_path=global_graph_path)
                if global_graph.load():
                    self.logger.info(
                        f"从全局图谱文件读取成功: {global_graph_path}, "
                        f"nodes={global_graph.graph.number_of_nodes()}")

                    # 提取实体
                    for node_id, node_data in global_graph.graph.nodes(data=True):
                        node_type = node_data.get("type", "未知")
                        node_text = node_data.get("text", "")
                        node_desc = node_data.get("description", "")

                        if node_type == "relationship":
                            continue

                        doc_content = f"【{node_type}】{node_text}"
                        if node_desc:
                            doc_content += f"\n{node_desc}"

                        result["global_entities"].append({
                            "content": doc_content,
                            "metadata": {"entity_type": node_type, "entity_name": node_text}
                        })

                    # 提取关系
                    for source, target, edge_data in global_graph.graph.edges(data=True):
                        source_data = global_graph.graph.nodes.get(source, {})
                        target_data = global_graph.graph.nodes.get(target, {})
                        source_text = source_data.get("text", source)
                        target_text = target_data.get("text", target)
                        rel_type = edge_data.get("relation", "关联")

                        doc_content = f"【关系】{source_text} --[{rel_type}]--> {target_text}"
                        result["global_relations"].append({
                            "content": doc_content,
                            "metadata": {"entity_type": "relationship"}
                        })

                    # 构建上下文
                    if result["global_entities"]:
                        context_parts.append("【全局设定 - 人物与实体】")
                        context_parts.extend(
                            [e["content"] for e in result["global_entities"][:10]])

                    if result["global_relations"]:
                        context_parts.append("\n【全局设定 - 关系网络】")
                        context_parts.extend(
                            [r["content"] for r in result["global_relations"][:5]])

            # 2. 读取当前单元图谱
            unit_graph_path = self.get_graph_path(project_id, current_unit)
            if os.path.exists(unit_graph_path):
                unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
                if unit_graph.load():
                    self.logger.info(
                        f"从单元图谱文件读取成功: {unit_graph_path}, "
                        f"nodes={unit_graph.graph.number_of_nodes()}")

                    # 提取实体
                    for node_id, node_data in unit_graph.graph.nodes(data=True):
                        node_type = node_data.get("type", "未知")
                        node_text = node_data.get("text", "")
                        node_desc = node_data.get("description", "")

                        if node_type == "relationship":
                            continue

                        doc_content = f"【{node_type}】{node_text}"
                        if node_desc:
                            doc_content += f"\n{node_desc}"

                        result["unit_entities"].append({
                            "content": doc_content,
                            "metadata": {"entity_type": node_type, "entity_name": node_text}
                        })

                    # 提取关系
                    for source, target, edge_data in unit_graph.graph.edges(data=True):
                        source_data = unit_graph.graph.nodes.get(source, {})
                        target_data = unit_graph.graph.nodes.get(target, {})
                        source_text = source_data.get("text", source)
                        target_text = target_data.get("text", target)
                        rel_type = edge_data.get("relation", "关联")

                        doc_content = f"【关系】{source_text} --[{rel_type}]--> {target_text}"
                        result["unit_relations"].append({
                            "content": doc_content,
                            "metadata": {"entity_type": "relationship"}
                        })

                    # 构建上下文
                    if result["unit_entities"]:
                        context_parts.append("\n【本单元 - 人物与实体】")
                        context_parts.extend(
                            [e["content"] for e in result["unit_entities"][:10]])

                    if result["unit_relations"]:
                        context_parts.append("\n【本单元 - 关系动态】")
                        context_parts.extend(
                            [r["content"] for r in result["unit_relations"][:5]])

            # 3. 获取时间线
            timeline_context = self._get_event_timeline(
                project_id, current_unit)
            if timeline_context:
                context_parts.append("\n【事件时间线】")
                context_parts.append(timeline_context)

            result["combined_context"] = "\n".join(context_parts)

            self.logger.info(
                f"图谱文件读取完成: project_id={project_id}, unit={current_unit}, "
                f"global_entities={len(result['global_entities'])}, "
                f"unit_entities={len(result['unit_entities'])}, "
                f"has_context={bool(result['combined_context'])}"
            )

        except Exception as e:
            self.logger.error(
                f"从图谱文件读取失败: project_id={project_id}, error={str(e)}")

        return result

    def _get_event_timeline(
        self,
        project_id: int,
        current_unit: int
    ) -> Optional[str]:
        """
        获取事件时间线（通过图关系查询）

        通过"前序"和"导致"关系获取当前单元前后的事件，确保情节连贯性。

        查询逻辑：
        1. 从当前单元图谱中查找详细事件节点
        2. 通过"前序"关系获取前序事件
        3. 通过"导致"关系获取后序事件
        4. 跨单元查询：获取前一个单元的结尾事件

        Args:
            project_id: 项目ID
            current_unit: 当前单元号

        Returns:
            时间线上下文文本，或 None
        """
        try:
            timeline_parts = []

            # 1. 跨单元查询：获取前一个单元的结尾事件
            if current_unit > 1:
                prev_unit_events = self._get_unit_ending_events(
                    project_id, current_unit - 1)
                if prev_unit_events:
                    timeline_parts.append("【前序单元结尾事件】")
                    for evt in prev_unit_events[:3]:
                        timeline_parts.append(f"  - {evt}")

            # 2. 加载当前单元图谱
            graph_path = self.get_graph_path(project_id, current_unit)
            if not os.path.exists(graph_path):
                self.logger.info(f"当前单元图谱不存在，跳过时间线")
                return "\n".join(timeline_parts) if timeline_parts else None

            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
            knowledge_graph.load()

            # 时间线关系类型
            timeline_relations = {"前序", "导致"}

            # 存储时间线事件
            prev_events = []  # 前序事件
            next_events = []  # 后序事件
            current_events = []  # 当前事件

            # 遍历所有边，查找时间线关系
            for source, target, edge_data in knowledge_graph.graph.edges(data=True):
                relation_type = edge_data.get("type", "")

                if relation_type not in timeline_relations:
                    continue

                # 获取源节点和目标节点信息
                source_data = knowledge_graph.graph.nodes.get(source, {})
                target_data = knowledge_graph.graph.nodes.get(target, {})

                source_type = source_data.get("type", "")
                target_type = target_data.get("type", "")

                # 只处理详细事件节点（使用中文类型名，与存储一致）
                if source_type != "详细事件" and target_type != "详细事件":
                    continue

                source_text = source_data.get("text", source)
                target_text = target_data.get("text", target)

                if relation_type == "前序":
                    # source -> target 表示 source 是 target 的前序事件
                    prev_events.append({
                        "event": source_text,
                        "leads_to": target_text
                    })
                elif relation_type == "导致":
                    # source -> target 表示 source 导致 target
                    next_events.append({
                        "event": source_text,
                        "causes": target_text
                    })

            # 收集当前单元的所有详细事件
            for node_id, node_data in knowledge_graph.graph.nodes(data=True):
                if node_data.get("type") == "详细事件":
                    current_events.append(node_data.get("text", node_id))

            # 构建时间线上下文
            if prev_events:
                timeline_parts.append("\n【前序事件关系】")
                for evt in prev_events[:3]:  # 最多3个
                    timeline_parts.append(
                        f"  - {evt['event']} → {evt['leads_to']}")

            if current_events:
                timeline_parts.append("\n【当前单元事件列表】")
                for evt in current_events[:5]:  # 最多5个
                    timeline_parts.append(f"  - {evt}")

            if next_events:
                timeline_parts.append("\n【后续事件关系】")
                for evt in next_events[:3]:  # 最多3个
                    timeline_parts.append(
                        f"  - {evt['event']} → {evt['causes']}")

            if not timeline_parts:
                self.logger.info(
                    f"未找到时间线信息: project_id={project_id}, unit={current_unit}")
                return None

            result = "\n".join(timeline_parts)
            self.logger.info(
                f"获取时间线成功: project_id={project_id}, unit={current_unit}")

            return result

        except Exception as e:
            self.logger.error(f"获取事件时间线失败: {str(e)}")
            return None

    def _get_unit_ending_events(
        self,
        project_id: int,
        unit_number: int,
        max_events: int = 3
    ) -> List[str]:
        """
        获取指定单元的结尾事件

        用于跨单元时间线，获取前一个单元的结尾事件作为当前单元的前序上下文。

        Args:
            project_id: 项目ID
            unit_number: 单元号
            max_events: 最多返回的事件数

        Returns:
            事件文本列表
        """
        events = []

        try:
            graph_path = self.get_graph_path(project_id, unit_number)
            if not os.path.exists(graph_path):
                return events

            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
            knowledge_graph.load()

            # 查找没有后继节点的详细事件（结尾事件）
            for node_id, node_data in knowledge_graph.graph.nodes(data=True):
                if node_data.get("type") != "详细事件":
                    continue

                # 检查是否有"导致"或"前序"出边
                has_outgoing = False
                for _, target, edge_data in knowledge_graph.graph.edges(node_id, data=True):
                    if edge_data.get("type") in {"导致", "前序"}:
                        has_outgoing = True
                        break

                # 如果没有出边，这是一个结尾事件
                if not has_outgoing:
                    events.append(node_data.get("text", node_id))
                    if len(events) >= max_events:
                        break

            self.logger.info(
                f"获取单元结尾事件: project_id={project_id}, unit={unit_number}, "
                f"events={len(events)}"
            )

        except Exception as e:
            self.logger.error(f"获取单元结尾事件失败: {str(e)}")

        return events

    def get_knowledge_graph_data(
        self,
        project_id: int,
        unit_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取知识图谱数据（用于可视化）

        Args:
            project_id: 项目ID
            unit_number: 单元号，None表示全局图谱

        Returns:
            图谱数据 {nodes: [], edges: [], stats: {}}
        """
        result = {
            "nodes": [],
            "edges": [],
            "stats": {
                "node_count": 0,
                "edge_count": 0,
                "entity_types": {}
            }
        }

        try:
            graph_path = self.get_graph_path(project_id, unit_number)

            if not os.path.exists(graph_path):
                self.logger.warning(f"图谱文件不存在: {graph_path}")
                return result

            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
            knowledge_graph.load()

            # 提取节点数据（支持分层结构）
            entity_types = {}
            macro_count = 0
            micro_count = 0
            for node_id, node_data in knowledge_graph.graph.nodes(data=True):
                node_type = node_data.get("type", "未知")
                node_level = node_data.get("level", "macro")
                entity_types[node_type] = entity_types.get(node_type, 0) + 1

                if node_level == "macro":
                    macro_count += 1
                else:
                    micro_count += 1

                result["nodes"].append({
                    "id": node_id,
                    "name": node_data.get("text", ""),  # 前端使用 name
                    "label": node_data.get("text", ""),  # 兼容公共知识库格式
                    "type": node_type,
                    "level": node_level,  # 宏观层或微观层
                    "description": node_data.get("description", ""),
                    "attributes": node_data.get("attributes", {}),  # 额外属性
                    "doc_id": node_data.get("doc_id", "")
                })

            # 提取边数据
            for source, target, edge_data in knowledge_graph.graph.edges(data=True):
                result["edges"].append({
                    "source": source,
                    "target": target,
                    "relation": edge_data.get("relation", ""),
                    "context": edge_data.get("context", "")
                })

            result["stats"]["node_count"] = len(result["nodes"])
            result["stats"]["edge_count"] = len(result["edges"])
            result["stats"]["entity_types"] = list(
                entity_types.keys())  # 返回类型列表，前端用 join 显示
            result["stats"]["entity_type_counts"] = entity_types  # 同时保留类型数量统计
            # 添加分层统计
            result["stats"]["macro_count"] = macro_count  # 宏观层节点数
            result["stats"]["micro_count"] = micro_count  # 微观层节点数

            return result

        except Exception as e:
            self.logger.error(
                f"获取图谱数据失败: project_id={project_id}, error={str(e)}")
            return result

    async def delete_project_kb(self, project_id: int) -> bool:
        """
        删除项目知识库

        Args:
            project_id: 项目ID

        Returns:
            是否成功
        """
        try:
            # 1. 删除向量集合
            collection_name = self.get_collection_name(project_id)
            self.vector_store.delete_collection(collection_name)

            # 2. 删除图谱文件
            # 删除全局图谱
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if os.path.exists(global_graph_path):
                os.remove(global_graph_path)

            # 删除所有单元图谱
            for filename in os.listdir(self.persist_dir):
                if filename.startswith(f"project_{project_id}_unit_") and filename.endswith("_graph.json"):
                    os.remove(os.path.join(self.persist_dir, filename))

            self.logger.info(f"项目知识库已删除: project_id={project_id}")
            return True

        except Exception as e:
            self.logger.error(
                f"删除项目知识库失败: project_id={project_id}, error={str(e)}")
            return False

    def get_kb_stats(self, project_id: int) -> Dict[str, Any]:
        """
        获取知识库统计信息

        Args:
            project_id: 项目ID

        Returns:
            统计信息
        """
        try:
            collection_name = self.get_collection_name(project_id)
            doc_count = self.vector_store.count_documents(collection_name)

            # 检查图谱文件
            global_graph_exists = os.path.exists(
                self.get_graph_path(project_id, unit_number=None))

            return {
                "collection_name": collection_name,
                "document_count": doc_count,
                "global_graph_exists": global_graph_exists,
                "status": "ready" if doc_count > 0 else "empty"
            }

        except Exception as e:
            return {
                "collection_name": self.get_collection_name(project_id),
                "document_count": 0,
                "status": "error",
                "error": str(e)
            }

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

    def get_character_states_for_writing(
        self,
        project_id: int,
        character_name: str,
        current_unit: int = None
    ) -> str:
        """
        获取人物状态信息用于写作提示词

        整合全局图谱和当前章节之前所有单元图谱中的人物状态信息。

        Args:
            project_id: 项目ID
            character_name: 人物名称
            current_unit: 当前章节号（只获取此章节之前的状态）

        Returns:
            格式化的人物状态文本
        """
        try:
            context_parts = [f"## {character_name} 人物状态追踪", ""]

            # 1. 从全局图谱获取人物基础信息
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if os.path.exists(global_graph_path):
                global_graph = NovelKnowledgeGraph(
                    persist_path=global_graph_path)
                if global_graph.load():
                    # 获取人物基础信息
                    character = global_graph.get_entity_by_text(character_name)
                    if character:
                        context_parts.append("### 基础设定")
                        context_parts.append(
                            f"- 类型: {character.get('type', '人物')}")
                        if character.get("description"):
                            context_parts.append(
                                f"- 描述: {character.get('description')}")
                        attrs = character.get("attributes", {})
                        if attrs:
                            for key, value in attrs.items():
                                if value:
                                    context_parts.append(f"- {key}: {value}")
                        context_parts.append("")

            # 2. 遍历所有已完成的单元图谱，收集人物状态
            all_state_entities = {
                "identity_changes": [],
                "location_changes": [],
                "relationship_changes": [],
                "character_development": [],
                "ability_growth": [],
                "mental_states": [],
                "behavior_patterns": []
            }

            # 确定要遍历的单元范围
            max_unit = current_unit - 1 if current_unit else 1000

            for unit in range(1, max_unit + 1):
                unit_graph_path = self.get_graph_path(project_id, unit)
                if not os.path.exists(unit_graph_path):
                    continue

                unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
                if not unit_graph.load():
                    continue

                # 获取该单元的人物状态实体
                unit_states = unit_graph.get_character_state_entities(
                    character_name=character_name,
                    chapter_num=unit
                )

                # 合并到总状态中
                for key in all_state_entities:
                    all_state_entities[key].extend(unit_states.get(key, []))

            # 3. 格式化输出
            if all_state_entities["identity_changes"]:
                context_parts.append("### 身份变化轨迹")
                for entity in all_state_entities["identity_changes"]:
                    chapter = entity.get("chapter", "")
                    context_parts.append(
                        f"- 第{chapter}章: {entity.get('text')}")
                    if entity.get("description"):
                        context_parts.append(f"  {entity.get('description')}")
                context_parts.append("")

            if all_state_entities["location_changes"]:
                context_parts.append("### 位置变化轨迹")
                locations = []
                for entity in all_state_entities["location_changes"]:
                    locations.append(entity.get("text", ""))
                context_parts.append(" → ".join(locations))
                context_parts.append("")

            if all_state_entities["relationship_changes"]:
                context_parts.append("### 关系变化")
                for entity in all_state_entities["relationship_changes"]:
                    chapter = entity.get("chapter", "")
                    context_parts.append(
                        f"- 第{chapter}章: {entity.get('text')}")
                context_parts.append("")

            if all_state_entities["ability_growth"]:
                context_parts.append("### 能力成长")
                for entity in all_state_entities["ability_growth"]:
                    chapter = entity.get("chapter", "")
                    context_parts.append(
                        f"- 第{chapter}章: {entity.get('text')}")
                context_parts.append("")

            if all_state_entities["mental_states"]:
                context_parts.append("### 心理状态演变")
                for entity in all_state_entities["mental_states"][-5:]:  # 只显示最近5条
                    chapter = entity.get("chapter", "")
                    context_parts.append(
                        f"- 第{chapter}章: {entity.get('text')}")
                context_parts.append("")

            return "\n".join(context_parts)

        except Exception as e:
            self.logger.error(
                f"获取人物状态失败: character={character_name}, error={str(e)}")
            return f"人物 {character_name} 暂无状态追踪信息"

    def get_all_character_states_for_chapter(
        self,
        project_id: int,
        current_unit: int
    ) -> str:
        """
        获取所有人物的状态摘要，用于章节写作提示词

        Args:
            project_id: 项目ID
            current_unit: 当前章节号

        Returns:
            所有人物的状态摘要文本
        """
        try:
            # 1. 从全局图谱获取所有人物
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if not os.path.exists(global_graph_path):
                return ""

            global_graph = NovelKnowledgeGraph(persist_path=global_graph_path)
            if not global_graph.load():
                return ""

            characters = global_graph.get_entities_by_type("人物")
            if not characters:
                return ""

            # 2. 获取每个人物的状态摘要
            context_parts = ["# 人物状态追踪摘要", ""]
            context_parts.append("以下是各主要人物到目前为止的状态变化，请在写作时保持一致性：")
            context_parts.append("")

            for char in characters[:10]:  # 最多10个人物
                char_name = char.get("name", "")
                if not char_name:
                    continue

                state_text = self.get_character_states_for_writing(
                    project_id, char_name, current_unit
                )
                if state_text and len(state_text) > 50:  # 有实质内容
                    context_parts.append(state_text)
                    context_parts.append("---")
                    context_parts.append("")

            return "\n".join(context_parts)

        except Exception as e:
            self.logger.error(
                f"获取所有人物状态失败: project_id={project_id}, error={str(e)}")
            return ""

    def _resolve_entity_coreference(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        context_content: str = None
    ) -> Dict[str, Any]:
        """
        实体消歧和指代关系解析（后处理步骤）

        解决LLM提取时未能正确处理的指代关系问题：
        - "现代医生" 和 "孙昭龙" 应该是同一个实体
        - 职业称谓 + 人名 格式应该合并为单一实体
        - 同一人物的不同称谓应该统一

        Args:
            entities: LLM提取的实体列表
            relations: LLM提取的关系列表
            context_content: 原始文本内容（可选，用于辅助判断）

        Returns:
            {
                "entities": 消歧后的实体列表,
                "relations": 更新后的关系列表（source/target已更新）,
                "merge_log": 合并日志
            }
        """
        import re

        merge_log = []
        entity_map = {}  # 原始text -> 规范化后的text
        canonical_names = {}  # 规范化text -> 实体数据

        # 第一步：识别人物实体并建立候选合并组
        person_entities = []
        non_person_entities = []

        for entity in entities:
            entity_text = entity.get("text", "")
            entity_type = entity.get("type", "")

            if entity_type == "人物":
                person_entities.append(entity)
            else:
                non_person_entities.append(entity)

        self.logger.info(
            f"实体消歧开始: 人物实体={len(person_entities)}, 非人物实体={len(non_person_entities)}")

        # 第二步：识别需要合并的称谓实体
        alias_patterns = [
            r'^现代医生$',
            r'^古代医生$',
            r'^穿越者$',
            r'^现代人$',
            r'^(?:将军|皇帝|王爷|太子|公主|尚书|丞相|大夫|郎中|秀才|举人|进士|状元)$',
            r'^(?:医生|护士|老师|学生|商人|农民|工匠|武士|侠客|刺客|间谍)$',
            r'^(?:少爷|小姐|夫人|老爷|太太|公子|千金|掌柜|店小二)$',
            r'^[A-Za-z\s]+$'
        ]

        to_merge = []  # (alias_entity, target_entity) 对
        aliases_to_remove = set()

        for i, person_a in enumerate(person_entities):
            text_a = person_a.get("text", "").strip()

            if not text_a or text_a in aliases_to_remove:
                continue

            # 检查是否为称谓/别名模式
            is_alias = False
            for pattern in alias_patterns:
                if re.match(pattern, text_a):
                    is_alias = True
                    break

            if not is_alias:
                continue

            # 查找可能的目标实体（正式名称）
            best_match = None
            best_score = 0

            for j, person_b in enumerate(person_entities):
                if i == j:
                    continue

                text_b = person_b.get("text", "").strip()

                if not text_b or text_b in aliases_to_remove:
                    continue

                # 排除其他别名
                is_b_alias = False
                for pattern in alias_patterns:
                    if re.match(pattern, text_b):
                        is_b_alias = True
                        break

                if is_b_alias:
                    continue

                # 计算匹配分数
                score = self._calculate_alias_match_score(
                    text_a, text_b, context_content)

                if score > best_score and score > 0.3:  # 阈值
                    best_score = score
                    best_match = person_b

            if best_match:
                to_merge.append((person_a, best_match))
                aliases_to_remove.add(text_a)
                merge_log.append(
                    f"合并别名 '{text_a}' → '{best_match.get('text', '')}' (置信度={best_score:.2f})"
                )

        # 第三步：执行合并
        merged_entities = list(non_person_entities)  # 先加入非人物实体

        # 加入未被合并的人物实体
        merged_target_ids = set()
        for _, target in to_merge:
            merged_target_ids.add(id(target))

        for entity in person_entities:
            if entity.get("text", "").strip() not in aliases_to_remove:
                merged_entities.append(entity)

        # 第四步：更新关系的 source/target
        updated_relations = []
        alias_to_canonical = {}

        for alias, target in to_merge:
            alias_text = alias.get("text", "").strip()
            target_text = target.get("text", "").strip()
            alias_to_canonical[alias_text] = target_text

        for relation in relations:
            source = relation.get("source", relation.get("head", ""))
            target = relation.get("target", relation.get("tail", ""))

            # 更新 source
            if source in alias_to_canonical:
                old_source = source
                source = alias_to_canonical[source]
                merge_log.append(f"更新关系源: {old_source} → {source}")

            # 更新 target
            if target in alias_to_canonical:
                old_target = target
                target = alias_to_canonical[target]
                merge_log.append(f"更新关系目标: {old_target} → {target}")

            # 更新关系字典
            if "source" in relation:
                relation["source"] = source
            elif "head" in relation:
                relation["head"] = source

            if "target" in relation:
                relation["target"] = target
            elif "tail" in relation:
                relation["tail"] = target

            updated_relations.append(relation)

        # 第五步：记录结果
        if merge_log:
            self.logger.info(f"实体消歧完成: 合并了{len(to_merge)}个别名实体")
            for log_entry in merge_log[:10]:  # 只记录前10条
                self.logger.debug(f"  - {log_entry}")
        else:
            self.logger.info("实体消歧完成: 未发现需要合并的别名实体")

        return {
            "entities": merged_entities,
            "relations": updated_relations,
            "merge_count": len(to_merge),
            "merge_log": merge_log
        }

    def _calculate_alias_match_score(
        self,
        alias_text: str,
        candidate_text: str,
        context_content: str = None
    ) -> float:
        """
        计算别名与候选实体的匹配分数

        基于以下特征计算：
        1. 文本共现（是否在原文中相邻出现）
        2. 语义相似度（基于关键词）
        3. 实体类型一致性

        Args:
            alias_text: 别名文本（如"现代医生"）
            candidate_text: 候选正式名称（如"孙昭龙"）
            context_content: 原始文本内容

        Returns:
            匹配分数 (0.0 - 1.0)
        """
        score = 0.0

        # 特征1：文本共现检查
        if context_content:
            cooccurrence_patterns = [
                f"{alias_text}{candidate_text}",
                f"{candidate_text}{alias_text}",
                f"{alias_text}，{candidate_text}",
                f"{candidate_text}，{alias_text}",
                f"{alias_text}（{candidate_text}",
                f"{candidate_text}（{alias_text}",
                f"{alias_text}的{candidate_text}",
                f"{alias_text}名为{candidate_text}"
            ]

            for pattern in cooccurrence_patterns:
                if pattern in context_content:
                    score += 0.4
                    break

            # 同一句子中出现
            sentences = re.split(r'[。！？；\n]', context_content)
            for sentence in sentences:
                if alias_text in sentence and candidate_text in sentence:
                    score += 0.3
                    break

        # 特征2：长度合理性（正式名称通常比别长）
        if len(candidate_text) >= len(alias_text):
            score += 0.1

        # 特征3：候选名称不是通用词
        common_words = {"人", "物", "事", "地", "时"}
        if candidate_text not in common_words:
            score += 0.1

        return min(score, 1.0)

    # ==================== 全局知识图谱增量更新方法 ====================

    async def sync_unit_entities_to_global(
        self,
        project_id: int,
        unit_number: int,
        character_tracker=None
    ) -> Dict[str, Any]:
        """
        将单元图谱的实体增量同步到全局知识图谱

        在章节生成后自动调用，确保新出现的实体和关系及时同步到全局图谱。
        实现"正文优先"原则：以正文内容为准更新全局知识。

        Args:
            project_id: 项目ID
            unit_number: 单元号（章节号）
            character_tracker: 人物状态追踪器（可选，用于更智能的同步）

        Returns:
            同步结果摘要
        """
        result = {
            "success": False,
            "project_id": project_id,
            "unit_number": unit_number,
            "entities_synced": 0,
            "relations_synced": 0,
            "new_entities": [],
            "extended_entities": {
                "facilities": 0,
                "events": 0,
                "groups": 0,
                "items": 0,
                "foreshadows": 0,
                "world_rules": 0,
                "time_nodes": 0
            },
            "error": None
        }

        try:
            # 1. 加载全局图谱
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if not os.path.exists(global_graph_path):
                self.logger.warning(f"全局图谱不存在: {global_graph_path}")
                result["error"] = "全局图谱不存在"
                return result

            global_graph = NovelKnowledgeGraph(persist_path=global_graph_path)
            if not global_graph.load():
                result["error"] = "加载全局图谱失败"
                return result

            # 2. 加载单元图谱
            unit_graph_path = self.get_graph_path(project_id, unit_number)
            if not os.path.exists(unit_graph_path):
                self.logger.info(f"单元图谱不存在，跳过同步: {unit_graph_path}")
                result["error"] = "单元图谱不存在"
                return result

            unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
            if not unit_graph.load():
                result["error"] = "加载单元图谱失败"
                return result

            # 3. 使用CharacterStateTracker进行智能同步
            if character_tracker:
                sync_result = character_tracker.sync_unit_to_global_graph(
                    global_graph=global_graph,
                    unit_graph=unit_graph,
                    chapter_num=unit_number,
                    sync_extended_entities=True
                )
                result["entities_synced"] = sync_result.get(
                    "entities_synced", 0)
                result["relations_synced"] = sync_result.get(
                    "relations_synced", 0)
                result["new_entities"] = sync_result.get("new_entities", [])
                result["extended_entities"] = sync_result.get(
                    "extended_entities_synced", {})
            else:
                # 简单同步逻辑（无追踪器时）
                result = self._simple_sync_entities(
                    global_graph, unit_graph, unit_number, result)

            result["success"] = True

            self.logger.info(
                f"单元图谱增量同步完成: project={project_id}, unit={unit_number}, "
                f"实体={result['entities_synced']}, 关系={result['relations_synced']}, "
                f"新实体={len(result['new_entities'])}")

        except Exception as e:
            self.logger.error(
                f"增量同步失败: project={project_id}, unit={unit_number}, error={str(e)}")
            result["error"] = str(e)

        return result

    def _simple_sync_entities(
        self,
        global_graph,
        unit_graph,
        unit_number: int,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        简单实体同步逻辑（无追踪器时使用）

        Args:
            global_graph: 全局知识图谱
            unit_graph: 单元知识图谱
            unit_number: 单元号
            result: 结果字典

        Returns:
            更新后的结果字典
        """
        try:
            # 遍历单元图谱中的所有实体
            for node_id, node_data in unit_graph.graph.nodes(data=True):
                entity_text = node_data.get("text", "")
                entity_type = node_data.get("type", "")

                # 检查是否为新实体
                is_new = entity_text not in global_graph.entity_index

                # 同步到全局图谱
                entity_data = {
                    "text": entity_text,
                    "type": entity_type,
                    "level": node_data.get("level", "micro"),
                    "description": node_data.get("description", ""),
                    "attributes": node_data.get("attributes", {}),
                    "chapter": node_data.get("chapter", unit_number)
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{unit_number}")
                result["entities_synced"] += 1

                if is_new:
                    result["new_entities"].append({
                        "text": entity_text,
                        "type": entity_type,
                        "chapter": unit_number
                    })

                # 统计扩展实体
                self._count_extended_entity_type(result, entity_type)

            # 遍历单元图谱中的所有关系
            for source, target, edge_data in unit_graph.graph.edges(data=True):
                source_data = unit_graph.graph.nodes.get(source, {})
                target_data = unit_graph.graph.nodes.get(target, {})

                relation_data = {
                    "source": source_data.get("text", source),
                    "target": target_data.get("text", target),
                    "relation": edge_data.get("relation", "关联"),
                    "context": edge_data.get("context", "")
                }
                global_graph.add_relation(
                    relation_data, doc_id=f"chapter_{unit_number}")
                result["relations_synced"] += 1

            # 保存全局图谱
            global_graph.save()

        except Exception as e:
            self.logger.error(f"简单同步失败: {e}")

        return result

    def _count_extended_entity_type(self, result: Dict[str, Any], entity_type: str) -> None:
        """统计扩展实体类型"""
        extended = result["extended_entities"]

        type_mapping = {
            # 设施
            ("设施", "设施状态变化", "设施归属变更", "设施物理状态"): "facilities",
            # 事件
            ("事件", "事件状态变化", "事件影响", "事件因果链", "详细事件"): "events",
            # 群体
            ("群体组织", "群体状态变化", "群体成员变动", "群体关系变化"): "groups",
            # 道具
            ("道具物品", "道具状态变化", "道具归属变更", "道具功能使用"): "items",
            # 伏笔
            ("伏笔", "伏笔回收"): "foreshadows",
            # 世界规则
            ("世界规则", "规则引用", "规则例外", "世界观规则"): "world_rules",
            # 时间节点
            ("时间节点", "时间流逝"): "time_nodes"
        }

        for types, key in type_mapping.items():
            if entity_type in types:
                extended[key] += 1
                break

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
