"""
GraphRAG 检索增强工具
将知识图谱与大语言模型结合，生成更准确、更具可解释性的答案
"""
from typing import List, Dict, Any, Optional, Tuple
import json
import re
import os
import networkx as nx
from collections import defaultdict

from app.core.logger import get_logger
from app.core.vector_store import get_vector_store
from app.core.config import get_settings


class EntityExtractor:
    """实体提取器（基于规则和关键词）"""

    def __init__(self):
        # 预定义的实体类型和关键词
        self.entity_patterns = {
            "人物": [
                "导演", "编剧", "演员", "主角", "配角", "主持人", "创作者",
                "用户", "观众", "读者", "客户", "消费者", "目标受众"
            ],
            "作品": [
                "电影", "电视剧", "短视频", "小说", "剧本", "广告", "文案",
                "视频", "文章", "故事", "脚本", "作品"
            ],
            "风格": [
                "幽默", "搞笑", "温馨", "感人", "悬疑", "科幻", "爱情",
                "动作", "励志", "治愈", "反差", "复古", "现代"
            ],
            "平台": [
                "抖音", "快手", "B站", "小红书", "视频号", "微博",
                "YouTube", "TikTok", "微信公众号"
            ],
            "品牌": [
                "品牌", "产品", "服务", "公司", "企业", "商标"
            ],
            "场景": [
                "开场", "结尾", "高潮", "转折", "冲突", "悬念",
                "场景", "情节", "桥段"
            ],
            "情感": [
                "快乐", "悲伤", "愤怒", "恐惧", "惊讶", "期待",
                "共鸣", "感动", "紧张"
            ],
            "技术": [
                "运镜", "剪辑", "配乐", "特效", "字幕", "滤镜",
                "转场", "节奏", "画面"
            ]
        }

        # 关系模式
        self.relation_patterns = [
            (r"(.+?)是(.+?)的(.+)", "属性关系"),
            (r"(.+?)包含(.+)", "包含关系"),
            (r"(.+?)属于(.+)", "属于关系"),
            (r"(.+?)导致(.+)", "因果关系"),
            (r"(.+?)影响(.+)", "影响关系"),
            (r"(.+?)与(.+?)相关", "相关关系"),
        ]

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取实体

        Args:
            text: 输入文本

        Returns:
            实体列表 [{"text": "导演", "type": "人物", "start": 0, "end": 2}]
        """
        entities = []

        for entity_type, keywords in self.entity_patterns.items():
            for keyword in keywords:
                start = 0
                while True:
                    pos = text.find(keyword, start)
                    if pos == -1:
                        break
                    entities.append({
                        "text": keyword,
                        "type": entity_type,
                        "start": pos,
                        "end": pos + len(keyword)
                    })
                    start = pos + 1

        # 去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e["text"], e["start"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        return unique_entities

    def extract_relations(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从文本中提取实体间关系

        Args:
            text: 输入文本
            entities: 已提取的实体列表

        Returns:
            关系列表 [{"source": "实体1", "target": "实体2", "relation": "关系类型"}]
        """
        relations = []

        # 基于模式匹配
        for pattern, relation_type in self.relation_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    relations.append({
                        "source": groups[0].strip(),
                        "target": groups[-1].strip() if len(groups) > 2 else groups[1].strip(),
                        "relation": relation_type,
                        "context": match.group(0)
                    })

        # 基于实体共现（同一句中的实体存在关联）
        sentences = re.split(r'[。！？\n]', text)
        for sentence in sentences:
            sentence_entities = []
            for e in entities:
                if e["start"] >= text.find(sentence) and e["end"] <= text.find(sentence) + len(sentence):
                    sentence_entities.append(e["text"])

            # 句中相邻实体建立关联
            for i in range(len(sentence_entities) - 1):
                relations.append({
                    "source": sentence_entities[i],
                    "target": sentence_entities[i + 1],
                    "relation": "共现关系",
                    "context": sentence[:50]
                })

        return relations


class KnowledgeGraph:
    """知识图谱存储和查询"""

    def __init__(self, persist_path: str = None):
        self.graph = nx.DiGraph()
        self.entity_index = defaultdict(list)  # 实体名 -> 节点ID列表
        self._node_counter = 0
        self.persist_path = persist_path
        self.logger = get_logger("knowledge_graph")

        # 初始化时尝试加载已保存的图谱
        if persist_path:
            self.load()

    def add_entity(self, entity: Dict[str, Any], doc_id: str = None) -> str:
        """
        添加实体节点

        Args:
            entity: 实体信息
            doc_id: 文档ID

        Returns:
            节点ID
        """
        node_id = f"entity_{self._node_counter}"
        self._node_counter += 1

        self.graph.add_node(
            node_id,
            text=entity["text"],
            type=entity["type"],
            doc_id=doc_id
        )

        self.entity_index[entity["text"]].append(node_id)
        return node_id

    def add_relation(self, relation: Dict[str, Any], doc_id: str = None):
        """
        添加关系边

        Args:
            relation: 关系信息
            doc_id: 文档ID
        """
        source_nodes = self.entity_index.get(relation["source"], [])
        target_nodes = self.entity_index.get(relation["target"], [])

        # 如果节点不存在，创建新节点
        if not source_nodes:
            source_id = self.add_entity(
                {"text": relation["source"], "type": "未知"}, doc_id)
        else:
            source_id = source_nodes[0]

        if not target_nodes:
            target_id = self.add_entity(
                {"text": relation["target"], "type": "未知"}, doc_id)
        else:
            target_id = target_nodes[0]

        self.graph.add_edge(
            source_id,
            target_id,
            relation=relation["relation"],
            context=relation.get("context", ""),
            doc_id=doc_id
        )

    def get_related_entities(self, entity_text: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        获取相关实体

        Args:
            entity_text: 实体文本
            max_depth: 最大搜索深度

        Returns:
            相关实体列表
        """
        results = []
        node_ids = self.entity_index.get(entity_text, [])

        for node_id in node_ids:
            # BFS 遍历相关节点
            visited = set()
            queue = [(node_id, 0)]

            while queue:
                current_id, depth = queue.pop(0)

                if current_id in visited or depth > max_depth:
                    continue

                visited.add(current_id)
                node_data = self.graph.nodes.get(current_id, {})

                if depth > 0:  # 不包括起始节点
                    results.append({
                        "text": node_data.get("text"),
                        "type": node_data.get("type"),
                        "depth": depth
                    })

                # 遍历邻居
                for neighbor in self.graph.successors(current_id):
                    edge_data = self.graph.edges.get(
                        (current_id, neighbor), {})
                    results.append({
                        "text": self.graph.nodes[neighbor].get("text"),
                        "type": self.graph.nodes[neighbor].get("type"),
                        "relation": edge_data.get("relation"),
                        "depth": depth + 1
                    })
                    queue.append((neighbor, depth + 1))

                for neighbor in self.graph.predecessors(current_id):
                    edge_data = self.graph.edges.get(
                        (neighbor, current_id), {})
                    queue.append((neighbor, depth + 1))

        return results

    def get_entity_paths(self, entity1: str, entity2: str) -> List[List[str]]:
        """
        获取两个实体之间的路径

        Args:
            entity1: 实体1
            entity2: 实体2

        Returns:
            路径列表
        """
        paths = []
        nodes1 = self.entity_index.get(entity1, [])
        nodes2 = self.entity_index.get(entity2, [])

        for n1 in nodes1:
            for n2 in nodes2:
                try:
                    path = nx.shortest_path(self.graph, n1, n2)
                    path_texts = [
                        self.graph.nodes[n].get("text", "")
                        for n in path
                    ]
                    paths.append(path_texts)
                except nx.NetworkXNoPath:
                    continue

        return paths

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                **data
            })

        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                **data
            })

        return {
            "nodes": nodes,
            "edges": edges
        }

    def from_dict(self, data: Dict[str, Any]):
        """从字典导入"""
        self.graph.clear()
        self.entity_index.clear()
        self._node_counter = 0

        for node in data.get("nodes", []):
            node_id = node.pop("id")
            self.graph.add_node(node_id, **node)
            self.entity_index[node.get("text", "")].append(node_id)
            self._node_counter = max(
                self._node_counter, int(node_id.split("_")[-1]) + 1)

        for edge in data.get("edges", []):
            source = edge.pop("source")
            target = edge.pop("target")
            self.graph.add_edge(source, target, **edge)

    def save(self, path: str = None) -> bool:
        """
        保存知识图谱到文件

        Args:
            path: 保存路径（可选，默认使用初始化时的路径）

        Returns:
            是否保存成功
        """
        save_path = path or self.persist_path
        if not save_path:
            return False

        try:
            # 确保目录存在
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)

            # 导出为字典并保存
            data = self.to_dict()
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(
                f"知识图谱已保存: {save_path}, 节点数: {len(data['nodes'])}, 边数: {len(data['edges'])}")
            return True
        except Exception as e:
            self.logger.error(f"保存知识图谱失败: {str(e)}")
            return False

    def load(self, path: str = None) -> bool:
        """
        从文件加载知识图谱

        Args:
            path: 加载路径（可选，默认使用初始化时的路径）

        Returns:
            是否加载成功
        """
        load_path = path or self.persist_path
        if not load_path or not os.path.exists(load_path):
            return False

        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.from_dict(data)
            self.logger.info(
                f"知识图谱已加载: {load_path}, 节点数: {len(data.get('nodes', []))}, 边数: {len(data.get('edges', []))}")
            return True
        except Exception as e:
            self.logger.error(f"加载知识图谱失败: {str(e)}")
            return False

    def save_for_knowledge_base(self, kb_id: int, base_dir: str):
        """
        为特定知识库保存图谱

        Args:
            kb_id: 知识库ID
            base_dir: 基础目录
        """
        kb_graph_path = os.path.join(base_dir, f"kb_{kb_id}_graph.json")
        self.save(kb_graph_path)

    def load_for_knowledge_base(self, kb_id: int, base_dir: str) -> bool:
        """
        加载特定知识库的图谱

        Args:
            kb_id: 知识库ID
            base_dir: 基础目录

        Returns:
            是否加载成功
        """
        kb_graph_path = os.path.join(base_dir, f"kb_{kb_id}_graph.json")
        return self.load(kb_graph_path)

    def get_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "entity_types": self._count_entity_types()
        }

    def _count_entity_types(self) -> Dict[str, int]:
        """统计各类型实体数量"""
        type_counts = defaultdict(int)
        for _, data in self.graph.nodes(data=True):
            entity_type = data.get("type", "未知")
            type_counts[entity_type] += 1
        return dict(type_counts)


class GraphRAG:
    """GraphRAG 检索增强

    支持双轨知识库架构：
    - 通用知识库（general）: 创意理论，固定调用
    - 垂直领域知识库: 应用案例，按需调用
    - 主动建立垂直实体与通用理论的连接
    """

    def __init__(self, persist_dir: str = None, kb_category: str = "general"):
        """
        初始化 GraphRAG

        Args:
            persist_dir: 持久化目录
            kb_category: 知识库类别 (general/short-video/script/novel/print-ad/tvc)
        """
        self.extractor = EntityExtractor()
        self.settings = get_settings()
        self.kb_category = kb_category

        # 设置持久化目录
        self.persist_dir = persist_dir or self.settings.get_knowledge_graph_dir()

        # 初始化知识图谱（全局图谱）
        global_graph_path = os.path.join(self.persist_dir, "global_graph.json")
        self.knowledge_graph = KnowledgeGraph(persist_path=global_graph_path)

        # 知识库图谱缓存
        self._kb_graphs: Dict[int, KnowledgeGraph] = {}

        self.vector_store = get_vector_store()
        self.logger = get_logger("graph_rag")

        # LLM提取器（延迟初始化）
        self._llm_extractor = None

    def get_llm_extractor(self, llm_provider=None):
        """获取或创建LLM提取器"""
        if self._llm_extractor is None:
            if llm_provider is None:
                # 尝试获取默认LLM提供者
                from app.agents.llm_manager import llm_manager
                llm_provider = llm_manager.get_default_provider()
            self._llm_extractor = LLMEntityExtractor(
                llm_provider=llm_provider,
                kb_category=self.kb_category
            )
        return self._llm_extractor

    def get_kb_graph(self, kb_id: int) -> KnowledgeGraph:
        """
        获取特定知识库的知识图谱

        Args:
            kb_id: 知识库ID

        Returns:
            知识图谱实例
        """
        if kb_id not in self._kb_graphs:
            kb_graph_path = os.path.join(
                self.persist_dir, f"kb_{kb_id}_graph.json")
            self._kb_graphs[kb_id] = KnowledgeGraph(persist_path=kb_graph_path)
            # 尝试加载已存在的图谱
            if os.path.exists(kb_graph_path):
                self._kb_graphs[kb_id].load()
        return self._kb_graphs[kb_id]

    async def index_document(self, collection_name: str, doc_id: str, content: str, kb_id: int = None):
        """
        索引文档，提取实体和关系

        Args:
            collection_name: 集合名称
            doc_id: 文档ID
            content: 文档内容
            kb_id: 知识库ID（用于持久化）
        """
        # 提取实体和关系
        entities = self.extractor.extract_entities(content)
        relations = self.extractor.extract_relations(content, entities)

        # 添加到全局知识图谱
        entity_map = {}
        for entity in entities:
            node_id = self.knowledge_graph.add_entity(entity, doc_id)
            entity_map[entity["text"]] = node_id

        for relation in relations:
            self.knowledge_graph.add_relation(relation, doc_id)

        # 如果指定了知识库ID，同时添加到知识库专属图谱
        if kb_id:
            kb_graph = self.get_kb_graph(kb_id)
            for entity in entities:
                kb_graph.add_entity(entity, doc_id)
            for relation in relations:
                kb_graph.add_relation(relation, doc_id)
            # 保存知识库图谱
            kb_graph.save()

        # 保存全局图谱
        self.knowledge_graph.save()

        self.logger.info(
            f"索引文档 {doc_id}: 提取 {len(entities)} 个实体, {len(relations)} 个关系")

        # 更新向量存储的元数据
        metadata = {
            "entities": [e["text"] for e in entities],
            "entity_types": list(set(e["type"] for e in entities)),
            "doc_id": doc_id
        }

        return metadata

    async def retrieve_with_graph(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        结合知识图谱的检索

        Args:
            collection_name: 集合名称
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            检索结果，包含向量检索和图谱增强信息
        """
        # 1. 向量检索
        try:
            vector_results = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results
            )
        except Exception as e:
            self.logger.warning(f"向量检索失败: {str(e)}")
            vector_results = {"documents": [[]], "metadatas": [[]]}

        # 2. 提取查询中的实体
        query_entities = self.extractor.extract_entities(query)
        query_entity_texts = [e["text"] for e in query_entities]

        # 3. 知识图谱增强
        graph_context = []
        for entity_text in query_entity_texts:
            related = self.knowledge_graph.get_related_entities(entity_text)
            if related:
                graph_context.append({
                    "query_entity": entity_text,
                    "related_entities": related[:5]  # 限制数量
                })

        # 4. 格式化结果
        results = []
        if vector_results["documents"] and vector_results["documents"][0]:
            for i, doc in enumerate(vector_results["documents"][0]):
                result = {
                    "content": doc,
                    "metadata": {}
                }

                if vector_results.get("metadatas") and vector_results["metadatas"][0]:
                    result["metadata"] = vector_results["metadatas"][0][i]

                if vector_results.get("distances") and vector_results["distances"][0]:
                    result["distance"] = vector_results["distances"][0][i]

                results.append(result)

        return {
            "vector_results": results,
            "graph_context": graph_context,
            "query_entities": query_entity_texts
        }

    def format_for_context(self, retrieval_result: Dict[str, Any]) -> str:
        """
        格式化检索结果用于 LLM 上下文

        Args:
            retrieval_result: 检索结果

        Returns:
            格式化的上下文文本
        """
        parts = ["以下是知识库中检索到的相关内容：\n"]

        # 向量检索结果
        for i, result in enumerate(retrieval_result.get("vector_results", [])[:3], 1):
            content = result.get("content", "")
            entities = result.get("metadata", {}).get("entities", [])

            parts.append(f"[参考文档 {i}]")
            if entities:
                parts.append(f"关键实体: {', '.join(entities[:5])}")
            parts.append(f"内容:\n{content}\n")

        # 知识图谱上下文
        graph_context = retrieval_result.get("graph_context", [])
        if graph_context:
            parts.append("\n## 相关实体关系")
            for ctx in graph_context:
                parts.append(f"\n「{ctx['query_entity']}」的相关信息:")
                for rel in ctx.get("related_entities", [])[:3]:
                    if rel.get("relation"):
                        parts.append(f"  - {rel['text']} ({rel['relation']})")
                    else:
                        parts.append(f"  - {rel['text']}")

        return "\n".join(parts)

    def get_graph_data(self, kb_id: int = None, max_nodes: int = 100) -> Dict[str, Any]:
        """
        获取知识图谱数据（用于可视化）

        Args:
            kb_id: 知识库ID（可选，不指定则返回全局图谱）
            max_nodes: 最大返回节点数

        Returns:
            图谱数据 {"nodes": [...], "edges": [...]}
        """
        graph = self.get_kb_graph(kb_id) if kb_id else self.knowledge_graph

        # 获取所有节点和边
        all_nodes = []
        for node_id, data in graph.graph.nodes(data=True):
            all_nodes.append({
                "id": node_id,
                "label": data.get("text", ""),
                "type": data.get("type", "未知"),
                "doc_id": data.get("doc_id")
            })

        all_edges = []
        for source, target, data in graph.graph.edges(data=True):
            all_edges.append({
                "source": source,
                "target": target,
                "relation": data.get("relation", "相关"),
                "context": data.get("context", "")
            })

        # 如果节点太多，进行裁剪（优先保留有更多连接的节点）
        if len(all_nodes) > max_nodes:
            # 计算节点度数
            node_degrees = {}
            for edge in all_edges:
                node_degrees[edge["source"]] = node_degrees.get(
                    edge["source"], 0) + 1
                node_degrees[edge["target"]] = node_degrees.get(
                    edge["target"], 0) + 1

            # 按度数排序，保留度数高的节点
            sorted_nodes = sorted(
                all_nodes, key=lambda n: node_degrees.get(n["id"], 0), reverse=True)
            kept_node_ids = set(n["id"] for n in sorted_nodes[:max_nodes])

            # 过滤节点和边
            all_nodes = [n for n in all_nodes if n["id"] in kept_node_ids]
            all_edges = [e for e in all_edges if e["source"]
                         in kept_node_ids and e["target"] in kept_node_ids]

        return {
            "nodes": all_nodes,
            "edges": all_edges,
            "stats": graph.get_stats()
        }

    def add_llm_entities_to_graph(self, entities: List[Dict], relations: List[Dict], kb_id: int = None, doc_id: str = None):
        """
        将LLM提取的实体和关系添加到图谱

        Args:
            entities: 实体列表
            relations: 关系列表
            kb_id: 知识库ID
            doc_id: 文档ID
        """
        # 添加到全局图谱
        for entity in entities:
            entity_data = {
                "text": entity.get("name", ""),
                "type": entity.get("type", "未知")
            }
            self.knowledge_graph.add_entity(entity_data, doc_id)

        for relation in relations:
            relation_data = {
                "source": relation.get("source", ""),
                "target": relation.get("target", ""),
                "relation": relation.get("relation", "相关关系"),
                "context": relation.get("context", "")
            }
            self.knowledge_graph.add_relation(relation_data, doc_id)

        # 添加到知识库专属图谱
        if kb_id:
            kb_graph = self.get_kb_graph(kb_id)
            for entity in entities:
                entity_data = {
                    "text": entity.get("name", ""),
                    "type": entity.get("type", "未知")
                }
                kb_graph.add_entity(entity_data, doc_id)

            for relation in relations:
                relation_data = {
                    "source": relation.get("source", ""),
                    "target": relation.get("target", ""),
                    "relation": relation.get("relation", "相关关系"),
                    "context": relation.get("context", "")
                }
                kb_graph.add_relation(relation_data, doc_id)

            # 保存知识库图谱
            kb_graph.save()

        # 保存全局图谱
        self.knowledge_graph.save()


# 全局 GraphRAG 实例
graph_rag = GraphRAG()


def get_graph_rag() -> GraphRAG:
    """获取 GraphRAG 实例"""
    return graph_rag


class LLMEntityExtractor:
    """基于LLM的实体提取器 - 用于深度理解知识库内容

    支持双轨知识库架构：
    - 通用知识库（创意理论层）
    - 垂直领域知识库（应用案例层）
    - 主动建立垂直实体与通用理论的连接
    """

    def __init__(self, llm_provider, kb_category: str = "general"):
        """
        初始化LLM实体提取器

        Args:
            llm_provider: LLM提供者实例
            kb_category: 知识库类别 (general/short-video/script/novel/print-ad/tvc)
        """
        self.llm_provider = llm_provider
        self.kb_category = kb_category
        self.logger = get_logger("llm_entity_extractor")

        # 导入配置
        from app.tools.graph_rag_config import get_extraction_prompt
        self.get_extraction_prompt = get_extraction_prompt

    def _get_prompt(self, text: str) -> str:
        """根据知识库类别获取对应的提取提示词"""
        return self.get_extraction_prompt(self.kb_category, text)

    async def extract_with_llm(self, text: str, max_retries: int = 2) -> Dict[str, Any]:
        """
        使用LLM提取实体和关系

        Args:
            text: 输入文本
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...]}
        """
        # 截断过长的文本（减小到3000字符以避免API限制）
        max_chars = 3000  # 约2000 tokens，避免超出模型限制
        if len(text) > max_chars:
            # 分段处理长文本
            return await self._extract_from_long_text(text, max_chars)

        # 直接调用内部方法处理短文本
        return await self._extract_single_chunk(text, max_retries)

    async def _extract_from_long_text(self, text: str, chunk_size: int) -> Dict[str, Any]:
        """
        处理长文本，分段提取后合并

        Args:
            text: 长文本
            chunk_size: 分段大小

        Returns:
            合并后的实体和关系
        """
        all_entities = []
        all_relations = []
        success_count = 0
        fail_count = 0

        # 按段落分割
        paragraphs = text.split('\n\n')
        current_chunk = ""
        total_chunks = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) > chunk_size:
                if current_chunk.strip():
                    total_chunks += 1
                    # 直接调用内部方法，避免递归
                    result = await self._extract_single_chunk(current_chunk)
                    if result.get("entities") or result.get("relations"):
                        all_entities.extend(result.get("entities", []))
                        all_relations.extend(result.get("relations", []))
                        success_count += 1
                    else:
                        fail_count += 1
                current_chunk = para
            else:
                current_chunk += "\n\n" + para

        # 处理最后一段
        if current_chunk.strip():
            total_chunks += 1
            result = await self._extract_single_chunk(current_chunk)
            if result.get("entities") or result.get("relations"):
                all_entities.extend(result.get("entities", []))
                all_relations.extend(result.get("relations", []))
                success_count += 1
            else:
                fail_count += 1

        # 去重
        unique_entities = self._deduplicate_entities(all_entities)
        unique_relations = self._deduplicate_relations(all_relations)

        # 输出总结日志
        self.logger.info(
            f"长文本处理完成: {total_chunks}个chunk, 成功{success_count}个, 失败{fail_count}个")

        return {
            "entities": unique_entities,
            "relations": unique_relations
        }

    async def _extract_single_chunk(self, text: str, max_retries: int = 2) -> Dict[str, Any]:
        """
        提取单个文本块的实体和关系（内部方法，不检查长度）

        Args:
            text: 输入文本
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...]}
        """
        for attempt in range(max_retries):
            try:
                prompt = self._get_prompt(text)
                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=3000
                )

                # 调试：打印 LLM 原始响应
                self.logger.info(f"=== LLM RAW RESPONSE START ===")
                if response and hasattr(response, 'content'):
                    self.logger.info(
                        f"Content: {response.content[:500] if response.content else 'None'}")
                else:
                    self.logger.info(f"Response: {response}")
                self.logger.info(f"=== LLM RAW RESPONSE END ===")

                # 检查响应是否有效
                if not response:
                    self.logger.warning(
                        f"LLM返回None，尝试 {attempt+1}/{max_retries}")
                    continue

                if not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"LLM响应格式错误，尝试 {attempt+1}/{max_retries}")
                    continue

                content = response.content
                if not content or not content.strip():
                    self.logger.warning(
                        f"LLM返回空内容，尝试 {attempt+1}/{max_retries}")
                    continue

                # 解析JSON响应
                result = self._parse_llm_response(content)

                # 调试：打印结果类型和内容
                self.logger.info(
                    f"DEBUG: result type={type(result).__name__}, value={str(result)[:500]}")

                if result and isinstance(result, dict) and (result.get("entities") or result.get("relations")):
                    return result
                else:
                    # 记录解析失败的原因（使用info级别确保可见）
                    preview = content[:500] if len(content) > 500 else content
                    self.logger.info(f"JSON解析失败，响应内容: {preview}")

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)[:200]
                import traceback
                self.logger.warning(
                    f"LLM实体提取异常({error_type}): {error_msg}\n{traceback.format_exc()}")

        return {"entities": [], "relations": []}

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析LLM响应，提取JSON"""
        if not response:
            return None

        # 清理响应内容
        response = response.strip()

        def validate_result(result):
            """验证结果是否为有效字典"""
            if not isinstance(result, dict):
                return None
            if "entities" in result or "relations" in result:
                return result
            return None

        # 1. 尝试直接解析
        try:
            result = json.loads(response)
            validated = validate_result(result)
            if validated:
                return validated
        except json.JSONDecodeError:
            pass

        # 2. 尝试提取markdown代码块中的JSON
        code_block_patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
            r'```\s*([\s\S]*?)\s*```',  # ``` ... ```
        ]
        for pattern in code_block_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                try:
                    result = json.loads(match.strip())
                    validated = validate_result(result)
                    if validated:
                        return validated
                except json.JSONDecodeError:
                    continue

        # 3. 尝试提取完整的JSON对象
        json_pattern = r'\{[\s\S]*\}'
        matches = re.findall(json_pattern, response)
        for match in matches:
            try:
                result = json.loads(match)
                validated = validate_result(result)
                if validated:
                    return validated
            except json.JSONDecodeError:
                continue

        # 4. 尝试修复常见的JSON格式问题
        try:
            # 移除可能的前后文本
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx+1]
                result = json.loads(json_str)
                validated = validate_result(result)
                if validated:
                    return validated
        except json.JSONDecodeError:
            pass

        self.logger.warning(f"无法解析LLM响应为有效JSON，响应长度: {len(response)}")
        return None

    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """实体去重"""
        seen = set()
        result = []
        for e in entities:
            key = (e.get("name", ""), e.get("type", ""))
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result

    def _deduplicate_relations(self, relations: List[Dict]) -> List[Dict]:
        """关系去重"""
        seen = set()
        result = []
        for r in relations:
            key = (r.get("source", ""), r.get(
                "target", ""), r.get("relation", ""))
            if key not in seen:
                seen.add(key)
                result.append(r)
        return result


class DualTrackGraphRAG:
    """双轨知识库 GraphRAG 检索器

    实现通用知识库与垂直领域知识库的协同检索
    """

    def __init__(self, persist_dir: str = None):
        self.settings = get_settings()
        self.persist_dir = persist_dir or self.settings.get_knowledge_graph_dir()
        self.logger = get_logger("dual_track_graph_rag")

        # 通用知识库（创意理论层）
        self.general_graph_rag = GraphRAG(
            persist_dir=self.persist_dir,
            kb_category="general"
        )

        # 垂直领域知识库缓存
        self._vertical_rags: Dict[str, GraphRAG] = {}

        self.vector_store = get_vector_store()

    def get_vertical_rag(self, category: str) -> GraphRAG:
        """获取或创建垂直领域 GraphRAG"""
        if category not in self._vertical_rags:
            self._vertical_rags[category] = GraphRAG(
                persist_dir=self.persist_dir,
                kb_category=category
            )
        return self._vertical_rags[category]

    async def retrieve_dual_track(
        self,
        query: str,
        general_kb_id: int = None,
        vertical_kb_id: int = None,
        vertical_category: str = None,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        双轨知识库检索

        Args:
            query: 查询文本
            general_kb_id: 通用知识库ID（固定调用）
            vertical_kb_id: 垂直领域知识库ID
            vertical_category: 垂直领域类别
            n_results: 返回结果数量

        Returns:
            {
                "general_results": 通用知识库结果,
                "vertical_results": 垂直领域结果,
                "connections": 理论连接,
                "enhanced_context": 增强后的上下文
            }
        """
        results = {
            "general_results": None,
            "vertical_results": None,
            "connections": [],
            "enhanced_context": ""
        }

        # 1. 检索通用知识库（创意理论）
        if general_kb_id:
            try:
                general_collection = f"kb_{general_kb_id}"
                results["general_results"] = await self.general_graph_rag.retrieve_with_graph(
                    collection_name=general_collection,
                    query=query,
                    n_results=n_results
                )
                self.logger.info(f"通用知识库检索完成: {general_kb_id}")
            except Exception as e:
                self.logger.warning(f"通用知识库检索失败: {e}")

        # 2. 检索垂直领域知识库
        if vertical_kb_id and vertical_category:
            try:
                vertical_rag = self.get_vertical_rag(vertical_category)
                vertical_collection = f"kb_{vertical_kb_id}"
                results["vertical_results"] = await vertical_rag.retrieve_with_graph(
                    collection_name=vertical_collection,
                    query=query,
                    n_results=n_results
                )
                self.logger.info(f"垂直知识库检索完成: {vertical_kb_id}")
            except Exception as e:
                self.logger.warning(f"垂直知识库检索失败: {e}")

        # 3. 分析理论连接
        results["connections"] = self._analyze_connections(results)

        # 4. 生成增强上下文
        results["enhanced_context"] = self._format_dual_track_context(results)

        return results

    def _analyze_connections(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析垂直实体与通用理论的连接"""
        connections = []

        general_results = results.get("general_results", {})
        vertical_results = results.get("vertical_results", {})

        if not general_results or not vertical_results:
            return connections

        # 获取通用理论实体
        general_entities = set()
        for ctx in general_results.get("graph_context", []):
            general_entities.add(ctx.get("query_entity", ""))
            for rel in ctx.get("related_entities", []):
                general_entities.add(rel.get("text", ""))

        # 获取垂直领域实体并匹配理论
        for ctx in vertical_results.get("graph_context", []):
            vertical_entity = ctx.get("query_entity", "")
            for rel in ctx.get("related_entities", []):
                related_text = rel.get("text", "")
                relation_type = rel.get("relation", "")

                # 检查是否与通用理论相关
                if related_text in general_entities:
                    connections.append({
                        "vertical_entity": vertical_entity,
                        "general_theory": related_text,
                        "relation": relation_type,
                        "confidence": rel.get("weight", 0.8)
                    })

        return connections

    def _format_dual_track_context(self, results: Dict[str, Any]) -> str:
        """格式化双轨检索结果为上下文"""
        parts = []

        # 添加通用理论部分
        general_results = results.get("general_results", {})
        if general_results and general_results.get("vector_results"):
            parts.append("## 通用创意理论\n")
            for i, result in enumerate(general_results["vector_results"][:3], 1):
                content = result.get("content", "")
                parts.append(f"[理论 {i}] {content[:300]}...\n")

        # 添加垂直领域案例部分
        vertical_results = results.get("vertical_results", {})
        if vertical_results and vertical_results.get("vector_results"):
            parts.append("\n## 垂直领域案例\n")
            for i, result in enumerate(vertical_results["vector_results"][:3], 1):
                content = result.get("content", "")
                parts.append(f"[案例 {i}] {content[:300]}...\n")

        # 添加理论连接部分
        connections = results.get("connections", [])
        if connections:
            parts.append("\n## 理论-案例连接\n")
            for conn in connections[:5]:
                parts.append(
                    f"- 「{conn['vertical_entity']}」{conn['relation']}「{conn['general_theory']}」"
                    f" (置信度: {conn['confidence']:.2f})"
                )

        return "\n".join(parts) if parts else ""
