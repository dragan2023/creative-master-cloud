"""
正文板块专属知识图谱系统
完全独立于公共知识库，不复用任何公共知识库代码
确保实体类型、关系类型、提示词工程等方面完全隔离
"""
import os
import json
import re
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
import networkx as nx
from collections import defaultdict

from app.core.logger import get_logger


# ============================================================================
# 正文板块专属配置（完全独立，不与公共知识库共享）
# ============================================================================

# 分块配置 - 更保守的策略确保JSON不被截断
NOVEL_CHUNK_SIZE = 1500  # 约1000 tokens，确保输出可控
NOVEL_MAX_ENTITIES_PER_CHUNK = 10  # 每个chunk最多提取10个实体
NOVEL_MAX_RELATIONS_PER_CHUNK = 15  # 每个chunk最多提取15个关系

# 实体类型定义（正文板块专用）
NOVEL_ENTITY_TYPES = {
    # 宏观层实体
    "主题": {"level": "macro", "description": "小说核心主题、思想内核"},
    "世界观规则": {"level": "macro", "description": "世界设定、规则体系、背景设定"},
    "人物": {"level": "macro", "description": "故事中的角色人物"},
    "故事结构": {"level": "macro", "description": "整体叙事结构、情节框架"},
    "章节概要": {"level": "macro", "description": "章节/单元的故事概要"},
    "地点": {"level": "macro", "description": "故事发生的场景地点"},
    # 微观层实体
    "详细事件": {"level": "micro", "description": "具体的情节事件"},
    "核心冲突": {"level": "micro", "description": "矛盾冲突点"},
    "角色发展弧": {"level": "micro", "description": "角色的成长变化轨迹"},
    "关键对话": {"level": "micro", "description": "重要的对话内容"},
    "情节线": {"level": "micro", "description": "情节发展线索"},
    "场景": {"level": "micro", "description": "具体的场景描写"}
}

# 关系类型定义（正文板块专用，与公共知识库完全不同）
NOVEL_RELATION_TYPES = {
    # 宏观层内部关系
    "体现于": "主题/规则体现于具体内容",
    "属于": "实体属于某个类别或整体",
    "包含": "整体包含部分",
    "影响": "一个实体对另一个实体产生影响",
    # 宏观与微观之间的桥梁关系
    "经历": "人物经历某个事件",
    "参与": "人物参与某个活动/事件",
    "展开为": "宏观概念展开为具体内容",
    "约束": "规则约束具体行为",
    "渗透于": "主题渗透于具体情节",
    "定位": "确定位置或关系",
    "发生于": "事件发生的地点/时间",
    # 微观层内部关系
    "前序": "事件的前序事件",
    "导致": "一个事件导致另一个事件",
    "包含冲突": "事件包含的冲突",
    "触发于": "由某事触发",
    "发生于事件": "在某事件中发生",
    "包含事件": "包含的具体事件",
    "关联": "一般关联关系",
    "关联人物": "与人物相关"
}

# 禁止使用的关系类型（这些是公共知识库专用的）
FORBIDDEN_RELATION_TYPES = {
    "体现了", "应用了", "符合", "违背了",
    "衍生自", "互补于", "应用于", "限制于",
    "基于", "理论依据", "科学基础", "核心技能支撑",
    "理论基础", "方法论", "实践应用", "案例"
}

# 正文板块专用提取提示词（精简版，减少token消耗）
NOVEL_EXTRACTION_PROMPT = """你是小说知识图谱专家。从以下内容中提取实体和关系。

**严格限制：**
- 实体数量不超过{max_entities}个
- 关系数量不超过{max_relations}个
- 只提取最核心、最重要的实体和关系

**禁止使用的关系类型：** 体现了、应用了、符合、违背了、衍生自、互补于、应用于、限制于、基于、理论依据

**实体类型：**
- 宏观层：主题、世界观规则、人物、故事结构、章节概要、地点
- 微观层：详细事件、核心冲突、角色发展弧、关键对话、情节线、场景

**关系类型：**
- 宏观层：体现于、属于、包含、影响
- 桥梁：经历、参与、展开为、约束、渗透于、定位、发生于
- 微观层：前序、导致、包含冲突、触发于、发生于事件、包含事件、关联、关联人物

**输出格式（严格JSON）：**
```json
{{
  "entities": [
    {{"text": "名称", "type": "类型", "level": "macro或micro", "description": "简短描述"}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation": "关系类型"}}
  ]
}}
```

待分析内容：
{content}

请直接输出JSON，不要有其他说明："""


# ============================================================================
# 正文板块专属知识图谱类
# ============================================================================

class NovelKnowledgeGraph:
    """
    正文板块专属知识图谱
    完全独立于公共知识库的KnowledgeGraph类
    """

    def __init__(self, persist_path: str = None):
        """
        初始化知识图谱

        Args:
            persist_path: 持久化文件路径
        """
        self.graph = nx.DiGraph()
        self.persist_path = persist_path
        self.logger = get_logger("novel_knowledge_graph")
        self.entity_index = {}  # 实体文本到节点ID的映射

    def load(self) -> bool:
        """加载图谱"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return False

        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.graph.clear()
            self.entity_index.clear()

            # 加载节点
            for node in data.get("nodes", []):
                node_id = node.get("id")
                self.graph.add_node(
                    node_id, **{k: v for k, v in node.items() if k != "id"})
                # 建立索引
                text = node.get("text", "")
                if text:
                    self.entity_index[text] = node_id

            # 加载边
            for edge in data.get("edges", []):
                source = edge.get("source")
                target = edge.get("target")
                if source and target:
                    self.graph.add_edge(
                        source, target, **{k: v for k, v in edge.items() if k not in ["source", "target"]})

            self.logger.info(
                f"正文板块图谱已加载: {self.persist_path}, 节点数: {self.graph.number_of_nodes()}, 边数: {self.graph.number_of_edges()}")
            return True

        except Exception as e:
            self.logger.error(f"加载正文板块图谱失败: {e}")
            return False

    def save(self) -> bool:
        """保存图谱"""
        if not self.persist_path:
            return False

        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)

            data = {
                "nodes": [
                    {"id": node_id, **data}
                    for node_id, data in self.graph.nodes(data=True)
                ],
                "edges": [
                    {"source": source, "target": target, **data}
                    for source, target, data in self.graph.edges(data=True)
                ]
            }

            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(
                f"正文板块图谱已保存: {self.persist_path}, 节点数: {self.graph.number_of_nodes()}, 边数: {self.graph.number_of_edges()}")
            return True

        except Exception as e:
            self.logger.error(f"保存正文板块图谱失败: {e}")
            return False

    def add_entity(self, entity_data: Dict[str, Any], doc_id: str = "") -> str:
        """
        添加实体到图谱

        Args:
            entity_data: 实体数据，包含 text, type, level, description 等
            doc_id: 文档ID

        Returns:
            节点ID
        """
        import uuid

        text = entity_data.get("text", "")

        # 检查是否已存在相同文本的实体
        if text in self.entity_index:
            # 更新现有节点
            node_id = self.entity_index[text]
            # 合并属性
            existing_data = dict(self.graph.nodes[node_id])
            existing_data.update(entity_data)
            existing_data["doc_ids"] = existing_data.get("doc_ids", [])
            if doc_id and doc_id not in existing_data["doc_ids"]:
                existing_data["doc_ids"].append(doc_id)
            self.graph.nodes[node_id].update(existing_data)
            return node_id

        # 创建新节点
        node_id = str(uuid.uuid4())
        node_data = {
            **entity_data,
            "doc_ids": [doc_id] if doc_id else []
        }
        self.graph.add_node(node_id, **node_data)
        self.entity_index[text] = node_id

        return node_id

    def add_relation(self, relation_data: Dict[str, Any], doc_id: str = "") -> bool:
        """
        添加关系到图谱

        Args:
            relation_data: 关系数据，包含 source, target, relation 等
            doc_id: 文档ID

        Returns:
            是否成功
        """
        source_text = relation_data.get("source", "")
        target_text = relation_data.get("target", "")
        relation_type = relation_data.get("relation", "关联")

        # 过滤禁止的关系类型
        if relation_type in FORBIDDEN_RELATION_TYPES:
            self.logger.warning(f"过滤禁止的关系类型: {relation_type}")
            return False

        # 查找或创建节点
        if source_text not in self.entity_index:
            self.add_entity({"text": source_text, "type": "未知"}, doc_id)
        if target_text not in self.entity_index:
            self.add_entity({"text": target_text, "type": "未知"}, doc_id)

        source_id = self.entity_index[source_text]
        target_id = self.entity_index[target_text]

        # 添加边
        edge_data = {
            "relation": relation_type,
            "context": relation_data.get("context", ""),
            "doc_ids": [doc_id] if doc_id else []
        }

        # 如果边已存在，更新doc_ids
        if self.graph.has_edge(source_id, target_id):
            existing_data = self.graph.edges[source_id, target_id]
            edge_data["doc_ids"] = list(
                set(existing_data.get("doc_ids", []) + edge_data["doc_ids"]))

        self.graph.add_edge(source_id, target_id, **edge_data)
        return True

    def get_entity_by_text(self, text: str) -> Optional[Dict[str, Any]]:
        """根据文本获取实体"""
        if text in self.entity_index:
            node_id = self.entity_index[text]
            return {"id": node_id, **self.graph.nodes[node_id]}
        return None

    def get_related_entities(self, entity_text: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """获取相关实体"""
        if entity_text not in self.entity_index:
            return []

        node_id = self.entity_index[entity_text]
        related = []
        visited = {node_id}

        # BFS遍历
        current_level = [node_id]
        for depth in range(max_depth):
            next_level = []
            for current_id in current_level:
                # 出边
                for _, target, edge_data in self.graph.edges(current_id, data=True):
                    if target not in visited:
                        visited.add(target)
                        target_data = self.graph.nodes[target]
                        related.append({
                            "id": target,
                            "text": target_data.get("text", ""),
                            "type": target_data.get("type", ""),
                            "relation": edge_data.get("relation", ""),
                            "depth": depth + 1
                        })
                        next_level.append(target)

                # 入边
                for source, _, edge_data in self.graph.edges(data=True):
                    if source == current_id and source not in visited:
                        continue
                    # 简化处理，只查出边

            current_level = next_level

        return related


# ============================================================================
# 正文板块专属实体提取器
# ============================================================================

class NovelEntityExtractor:
    """
    正文板块专属实体提取器
    完全独立于公共知识库的LLMEntityExtractor类
    """

    def __init__(self, llm_provider):
        """
        初始化提取器

        Args:
            llm_provider: LLM提供者
        """
        self.llm_provider = llm_provider
        self.logger = get_logger("novel_entity_extractor")

        # 使用正文板块专属配置
        self.chunk_size = NOVEL_CHUNK_SIZE
        self.max_entities_per_chunk = NOVEL_MAX_ENTITIES_PER_CHUNK
        self.max_relations_per_chunk = NOVEL_MAX_RELATIONS_PER_CHUNK

    async def extract_with_llm(self, text: str, max_retries: int = 2) -> Dict[str, Any]:
        """
        使用LLM提取实体和关系

        Args:
            text: 输入文本
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...]}
        """
        # 检查文本长度，决定是否分块
        if len(text) > self.chunk_size:
            return await self._extract_from_long_text(text)

        return await self._extract_single_chunk(text, max_retries)

    async def _extract_from_long_text(self, text: str) -> Dict[str, Any]:
        """
        处理长文本，分段提取后合并
        """
        all_entities = []
        all_relations = []
        success_count = 0
        fail_count = 0

        # 智能分块
        chunks = self._smart_split_text(text)
        total_chunks = len(chunks)

        self.logger.info(
            f"正文板块长文本分块: 总长度={len(text)}, chunk大小={self.chunk_size}, 分成{total_chunks}块")

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            self.logger.debug(f"处理第 {i+1}/{total_chunks} 块, 长度={len(chunk)}")
            result = await self._extract_single_chunk(chunk)

            if result.get("entities") or result.get("relations"):
                all_entities.extend(result.get("entities", []))
                all_relations.extend(result.get("relations", []))
                success_count += 1
            else:
                fail_count += 1

        # 去重
        unique_entities = self._deduplicate_entities(all_entities)
        unique_relations = self._deduplicate_relations(all_relations)

        self.logger.info(
            f"正文板块长文本处理完成: {total_chunks}个chunk, 成功{success_count}个, 失败{fail_count}个")

        return {
            "entities": unique_entities,
            "relations": unique_relations
        }

    def _smart_split_text(self, text: str) -> List[str]:
        """
        智能分块：优先按段落分割，如果段落过长则按句子分割
        """
        chunks = []

        # 1. 首先尝试按双换行符分割（段落）
        paragraphs = text.split('\n\n')

        # 如果只有一个段落（没有双换行符），尝试单换行符
        if len(paragraphs) == 1:
            paragraphs = text.split('\n')
            self.logger.debug(f"使用单换行符分割，得到 {len(paragraphs)} 个段落")
        else:
            self.logger.debug(f"使用双换行符分割，得到 {len(paragraphs)} 个段落")

        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前段落加上新段落不超过限制，合并
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n" + para
                else:
                    current_chunk = para
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果单个段落超过限制，需要进一步分割
                if len(para) > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(para)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = para

        # 保存最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        # 如果仍然没有分块（极端情况），强制按字符数分割
        if not chunks:
            for i in range(0, len(text), self.chunk_size):
                chunks.append(text[i:i+self.chunk_size])

        return chunks

    def _split_long_paragraph(self, para: str) -> List[str]:
        """分割过长的段落（按句子分割）"""
        chunks = []

        # 按中文句号、问号、感叹号分割句子
        sentences = re.split(r'([。！？!?\.]+)', para)

        # 重新组合句子和标点
        combined_sentences = []
        for i in range(0, len(sentences)-1, 2):
            if i+1 < len(sentences):
                combined_sentences.append(sentences[i] + sentences[i+1])
            else:
                combined_sentences.append(sentences[i])
        if len(sentences) % 2 == 1 and sentences[-1]:
            combined_sentences.append(sentences[-1])

        current_chunk = ""

        for sentence in combined_sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # 如果单个句子超过限制，强制截断
                if len(sentence) > self.chunk_size:
                    for i in range(0, len(sentence), self.chunk_size):
                        chunks.append(sentence[i:i+self.chunk_size])
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def _extract_single_chunk(self, text: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        提取单个文本块的实体和关系

        增强的重试机制：
        - 针对429错误（服务器过载）使用指数退避
        - 区分不同类型的错误
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                # 使用正文板块专用提示词
                prompt = NOVEL_EXTRACTION_PROMPT.format(
                    max_entities=self.max_entities_per_chunk,
                    max_relations=self.max_relations_per_chunk,
                    content=text
                )

                # 获取模型支持的最大输出token
                max_output_tokens = self.llm_provider.get_max_output_tokens()

                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=max_output_tokens
                )

                # 调试日志
                self.logger.debug(
                    f"LLM响应长度: {len(response.content) if response and hasattr(response, 'content') and response.content else 0}")

                if not response or not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"LLM返回无效响应，尝试 {attempt+1}/{max_retries}")
                    continue

                # 解析响应
                result = self._parse_llm_response(response.content)
                if result:
                    return result

                self.logger.warning(f"JSON解析失败，尝试 {attempt+1}/{max_retries}")

            except Exception as e:
                error_str = str(e)
                last_error = e

                # 检测429错误（服务器过载/限流）
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower(
                ) or 'overload' in error_str.lower()

                if is_rate_limit:
                    # 指数退避：10秒 -> 20秒 -> 40秒
                    wait_time = 10 * (2 ** attempt)
                    self.logger.warning(
                        f"API限流/服务器过载(429)，等待 {wait_time}秒 后重试... (尝试 {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                else:
                    # 其他错误：较短等待
                    self.logger.warning(f"LLM实体提取异常: {error_str[:200]}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)

        self.logger.error(
            f"所有重试失败，返回空结果。最后错误: {str(last_error)[:200] if last_error else 'None'}")
        return {"entities": [], "relations": []}

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析LLM响应为JSON
        """
        if not response:
            return None

        # 清理响应
        response = response.strip()

        # 移除markdown代码块标记
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        # 清理中文引号
        response = response.replace('"', '"').replace('"', '"')
        response = response.replace(''', "'").replace(''', "'")

        # 尝试直接解析
        try:
            result = json.loads(response)
            if self._validate_result(result):
                self.logger.info(
                    f"JSON解析成功: {len(result.get('entities', []))}个实体, {len(result.get('relations', []))}个关系")
                return result
        except json.JSONDecodeError as e:
            self.logger.debug(f"直接解析失败: {e}")

        # 尝试提取JSON对象
        try:
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end != -1:
                json_str = response[start:end+1]
                result = json.loads(json_str)
                if self._validate_result(result):
                    self.logger.info(
                        f"提取JSON对象成功: {len(result.get('entities', []))}个实体")
                    return result
        except json.JSONDecodeError as e:
            self.logger.debug(f"提取JSON对象失败: {e}")

        # 尝试修复截断的JSON
        fixed = self._try_fix_truncated_json(response)
        if fixed:
            try:
                result = json.loads(fixed)
                if self._validate_result(result):
                    self.logger.info(
                        f"修复截断JSON成功: {len(result.get('entities', []))}个实体")
                    return result
            except:
                pass

        self.logger.warning(f"无法解析LLM响应为有效JSON")
        return None

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """验证解析结果"""
        if not isinstance(result, dict):
            return False
        if "entities" not in result:
            return False
        if not isinstance(result["entities"], list):
            return False
        return True

    def _try_fix_truncated_json(self, response: str) -> Optional[str]:
        """
        尝试修复被截断的JSON
        """
        # 找到entities和relations数组
        entities_start = response.find('"entities"')
        relations_start = response.find('"relations"')

        if entities_start == -1:
            return None

        # 提取entities数组
        entities_array_start = response.find('[', entities_start)
        if entities_array_start == -1:
            return None

        entities_result = self._extract_complete_array(
            response, entities_array_start)

        if relations_start != -1:
            relations_array_start = response.find('[', relations_start)
            if relations_array_start != -1:
                relations_result = self._extract_complete_array(
                    response, relations_array_start)
                return '{"entities": ' + entities_result + ', "relations": ' + relations_result + '}'

        return '{"entities": ' + entities_result + ', "relations": []}'

    def _extract_complete_array(self, json_str: str, array_start: int) -> str:
        """从JSON字符串中提取完整的数组内容"""
        depth = 0
        in_string = False
        escape_next = False
        last_complete_pos = array_start

        for i, char in enumerate(json_str[array_start:], start=array_start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\' and in_string:
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '[':
                    depth += 1
                elif char == ']':
                    depth -= 1
                    if depth == 0:
                        return json_str[array_start:i+1]
                elif char == '}':
                    if depth == 1:
                        last_complete_pos = i

        # 数组不完整，截断到最后一个完整元素
        if last_complete_pos > array_start:
            truncated = json_str[array_start:last_complete_pos+1]
            truncated = truncated.rstrip().rstrip(',')
            return truncated + ']'

        return '[]'

    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """实体去重"""
        seen = set()
        result = []
        for e in entities:
            key = (e.get("text", ""), e.get("type", ""))
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
