"""生成 writer_master T13: 质控/知识库/风格文档/WebSocket"""
import os

BASE = r'F:\python_project\writer_master\backend'


def write_file(rel_path, content):
    full_path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')
    print(f'  Created: {rel_path}')


# ==================== 1. 质控模块 ====================

# --- domain/services/quality_service.py ---
write_file('app/domain/services/quality_service.py', '''
"""质量管控领域服务 - 三维质控分析"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from app.core.constants import QualityConstants
from app.core.logger import get_logger

logger = get_logger("quality_service")


@dataclass
class QualityIssue:
    """质量问题"""
    id: str
    dimension: str
    category: str
    severity: str
    location: Dict
    description: str
    evidence: str
    suggestion: str
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class QualityReport:
    """质控报告"""
    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    issues: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    @property
    def grade(self) -> str:
        if self.overall_score >= QualityConstants.EXCELLENT_THRESHOLD:
            return "优秀"
        if self.overall_score >= QualityConstants.PASS_THRESHOLD:
            return "合格"
        return "需修正"

    @property
    def is_passed(self) -> bool:
        return self.overall_score >= QualityConstants.PASS_THRESHOLD


class QualityControlService:
    """质量管控服务

    协调多维度分析器,执行质量分析任务。
    支持三种分析深度: quick/standard/deep
    """

    # 维度常量
    DIMENSIONS_GLOBAL = [
        "global_structure",
        "global_character_worldview",
        "global_plot_consistency",
        "global_storyline_integrity",
    ]

    DIMENSIONS_UNIT = [
        "unit_structure",
        "unit_character",
        "unit_consistency",
        "unit_timeline_space",
        "unit_ooc",
    ]

    DIMENSIONS_CHAPTER = [
        "structure",
        "character",
        "scene",
        "prose",
        "experience",
        "technical",
    ]

    # 深度常量
    DEPTH_QUICK = "quick"
    DEPTH_STANDARD = "standard"
    DEPTH_DEEP = "deep"

    def __init__(self, db=None):
        self.db = db

    async def analyze_global_outline(
        self, content: str, project: Any = None,
        dimensions: Optional[List[str]] = None,
        depth: str = "standard", user_id: int = 0,
        llm_provider=None,
    ) -> QualityReport:
        """分析全局大纲质量"""
        if dimensions is None:
            dimensions = self.DIMENSIONS_GLOBAL

        report = QualityReport()
        total_score = 0.0

        for dim in dimensions:
            try:
                dim_result = await self._analyze_dimension(
                    dimension=dim, content=content,
                    project=project, depth=depth,
                    user_id=user_id, llm_provider=llm_provider,
                )
                score = dim_result.get("score", 0)
                issues = dim_result.get("issues", [])
                report.dimension_scores[dim] = score
                report.issues.extend(issues)
                total_score += score
            except Exception as e:
                logger.error(f"维度 {dim} 分析失败: {e}")
                report.dimension_scores[dim] = 0

        if report.dimension_scores:
            report.overall_score = total_score / len(report.dimension_scores)

        return report

    async def analyze_chapter(
        self, content: str, chapter_num: int = 0,
        dimensions: Optional[List[str]] = None,
        depth: str = "standard", user_id: int = 0,
        llm_provider=None, global_outline: str = "",
    ) -> QualityReport:
        """分析章节质量"""
        if dimensions is None:
            dimensions = self.DIMENSIONS_CHAPTER

        report = QualityReport()
        total_score = 0.0

        for dim in dimensions:
            try:
                dim_result = await self._analyze_dimension(
                    dimension=dim, content=content,
                    depth=depth, user_id=user_id,
                    llm_provider=llm_provider,
                    extra_context={"chapter_num": chapter_num,
                                   "global_outline": global_outline},
                )
                score = dim_result.get("score", 0)
                issues = dim_result.get("issues", [])
                report.dimension_scores[dim] = score
                report.issues.extend(issues)
                total_score += score
            except Exception as e:
                logger.error(f"维度 {dim} 分析失败: {e}")
                report.dimension_scores[dim] = 0

        if report.dimension_scores:
            report.overall_score = total_score / len(report.dimension_scores)

        return report

    async def analyze_unit_summaries(
        self, chapters_data: List[Dict],
        dimensions: Optional[List[str]] = None,
        depth: str = "deep", user_id: int = 0,
        global_outline: str = "", llm_provider=None,
    ) -> QualityReport:
        """分析单元概述质量"""
        if dimensions is None:
            dimensions = self.DIMENSIONS_UNIT

        report = QualityReport()
        total_score = 0.0

        for dim in dimensions:
            try:
                dim_result = await self._analyze_dimension(
                    dimension=dim,
                    content=json.dumps(chapters_data, ensure_ascii=False),
                    depth=depth, user_id=user_id,
                    llm_provider=llm_provider,
                    extra_context={"chapters_data": chapters_data,
                                   "global_outline": global_outline},
                )
                score = dim_result.get("score", 0)
                issues = dim_result.get("issues", [])
                report.dimension_scores[dim] = score
                report.issues.extend(issues)
                total_score += score
            except Exception as e:
                logger.error(f"维度 {dim} 分析失败: {e}")
                report.dimension_scores[dim] = 0

        if report.dimension_scores:
            report.overall_score = total_score / len(report.dimension_scores)

        return report

    async def auto_fix(
        self, content: str, issues: List[Dict],
        llm_provider=None, user_id: int = 0,
    ) -> Dict[str, Any]:
        """自动修正质控问题"""
        if not issues or not llm_provider:
            return {"success": False, "revised_content": None, "fixed_count": 0}

        issue_descriptions = []
        for issue in issues:
            issue_descriptions.append(
                f"- [{issue.get('severity', 'warning')}] "
                f"{issue.get('description', '')} "
                f"建议: {issue.get('suggestion', '')}"
            )

        prompt = (
            "请根据以下质控问题修正内容。\\n\\n"
            f"原文内容:\\n{content[:3000]}\\n\\n"
            f"质控问题:\\n{chr(10).join(issue_descriptions)}\\n\\n"
            "请输出修正后的完整内容。"
        )

        try:
            from app.core.constants import TokenConstants
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=TokenConstants.CHAPTER_CONTENT_MAX_TOKENS,
            )
            return {
                "success": True,
                "revised_content": response.content,
                "fixed_count": len(issues),
            }
        except Exception as e:
            logger.error(f"自动修正失败: {e}")
            return {"success": False, "revised_content": None, "fixed_count": 0}

    async def _analyze_dimension(
        self, dimension: str, content: str,
        project: Any = None, depth: str = "standard",
        user_id: int = 0, llm_provider=None,
        extra_context: Optional[Dict] = None,
    ) -> Dict:
        """执行单维度分析"""
        # 规则引擎快速分析
        score = await self._rule_based_analysis(dimension, content, extra_context)

        # 如果深度足够且有LLM,执行LLM深度分析
        if depth in (self.DEPTH_STANDARD, self.DEPTH_DEEP) and llm_provider:
            llm_score, llm_issues = await self._llm_analysis(
                dimension, content, depth, llm_provider, extra_context,
            )
            score = (score + llm_score) / 2 if llm_score else score
            issues = llm_issues
        else:
            issues = self._generate_rule_issues(dimension, content, score)

        return {"score": score, "issues": issues}

    async def _rule_based_analysis(
        self, dimension: str, content: str,
        extra_context: Optional[Dict] = None,
    ) -> float:
        """规则引擎分析"""
        if not content:
            return 0.0

        base_score = 70.0
        content_len = len(content)

        if content_len < 100:
            base_score -= 30
        elif content_len < 500:
            base_score -= 10

        return max(0, min(100, base_score))

    def _generate_rule_issues(
        self, dimension: str, content: str, score: float,
    ) -> List[Dict]:
        """根据规则分析生成问题列表"""
        issues = []
        if score < QualityConstants.PASS_THRESHOLD:
            issues.append({
                "id": f"R-{dimension[:3].upper()}-001",
                "dimension": dimension,
                "category": "内容质量",
                "severity": "warning",
                "description": f"{dimension} 维度得分偏低({score:.1f})",
                "evidence": content[:200] if content else "",
                "suggestion": "建议完善相关内容",
                "location": {},
            })
        return issues

    async def _llm_analysis(
        self, dimension: str, content: str, depth: str,
        llm_provider, extra_context: Optional[Dict] = None,
    ) -> tuple:
        """LLM深度分析"""
        dimension_labels = {
            "structure": "结构完整性", "character": "角色塑造",
            "scene": "场景描写", "prose": "文笔质量",
            "experience": "读者体验", "technical": "技术规范",
            "global_structure": "全局结构", "global_character_worldview": "角色与世界观",
            "global_plot_consistency": "情节一致性",
            "global_storyline_integrity": "主线完整性",
            "unit_structure": "单元结构", "unit_character": "单元角色",
            "unit_consistency": "单元一致性", "unit_timeline_space": "时空连贯",
            "unit_ooc": "角色崩坏检测",
        }

        label = dimension_labels.get(dimension, dimension)
        prompt = (
            f"请从「{label}」维度对以下内容进行质量评估。\\n\\n"
            f"分析深度: {depth}\\n\\n"
            f"内容:\\n{content[:3000]}\\n\\n"
            "请返回JSON格式:\\n"
            '{"score": 0-100分数, "issues": [{"id": "问题ID", '
            '"dimension": "维度", "category": "分类", '
            '"severity": "critical/warning/info", '
            '"description": "问题描述", "evidence": "原文证据", '
            '"suggestion": "修改建议"}]}'
        )

        try:
            from app.core.constants import TokenConstants
            response = await llm_provider.generate(
                prompt=prompt, temperature=0.3,
                max_tokens=TokenConstants.QUALITY_CHECK_MAX_TOKENS,
            )
            import json
            result = json.loads(response.content)
            score = float(result.get("score", 0))
            issues = result.get("issues", [])
            return score, issues
        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return 0, []

import json
''')

# --- infrastructure/knowledge/vector_store.py ---
write_file('app/infrastructure/knowledge/vector_store.py', '''
"""向量存储封装 - ChromaDB"""
from typing import List, Dict, Any, Optional
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("vector_store")
settings = get_settings()


class VectorStore:
    """ChromaDB向量存储封装"""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import chromadb
            chroma_dir = settings.get_chroma_dir()
            self._client = chromadb.PersistentClient(path=chroma_dir)
        return self._client

    def get_or_create_collection(self, name: str):
        client = self._get_client()
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(
        self, collection_name: str, documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        collection = self.get_or_create_collection(collection_name)
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"向集合 {collection_name} 添加 {len(documents)} 个文档")

    def query(
        self, collection_name: str, query_texts: List[str],
        n_results: int = 5, where: Optional[Dict] = None,
    ) -> Dict:
        collection = self.get_or_create_collection(collection_name)
        kwargs = {"query_texts": query_texts, "n_results": n_results}
        if where:
            kwargs["where"] = where
        return collection.query(**kwargs)

    def delete_collection(self, collection_name: str):
        client = self._get_client()
        try:
            client.delete_collection(collection_name)
            logger.info(f"已删除集合: {collection_name}")
        except Exception as e:
            logger.warning(f"删除集合失败 {collection_name}: {e}")

    def count_documents(self, collection_name: str) -> int:
        try:
            collection = self.get_or_create_collection(collection_name)
            return collection.count()
        except Exception:
            return 0


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
''')

# --- infrastructure/knowledge/knowledge_retrieval.py ---
write_file('app/infrastructure/knowledge/knowledge_retrieval.py', '''
"""知识检索工具 - 向量检索+图谱增强"""
from typing import List, Dict, Any, Optional
from app.infrastructure.knowledge.vector_store import get_vector_store
from app.core.logger import get_logger

logger = get_logger("knowledge_retrieval")


class KnowledgeRetrievalTool:
    """知识检索工具"""

    def __init__(self):
        self.vector_store = get_vector_store()

    async def retrieve(
        self, collection_name: str, query: str,
        n_results: int = 5, where_filter: Optional[Dict] = None,
    ) -> List[Dict]:
        """检索相关知识"""
        try:
            results = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            retrieved = []
            for i, doc in enumerate(documents):
                item = {
                    "content": doc,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else 0,
                }
                retrieved.append(item)

            return retrieved
        except Exception as e:
            logger.error(f"知识检索失败: {e}")
            return []

    async def add_documents(
        self, collection_name: str, documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        doc_id: Optional[str] = None,
    ):
        """添加文档到知识库"""
        ids = [doc_id] if doc_id else None
        self.vector_store.add_documents(
            collection_name=collection_name,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    async def add_documents_batch(
        self, collection_name: str, documents: List[str],
        metadatas: Optional[List[Dict]] = None,
    ):
        """批量添加文档"""
        self.vector_store.add_documents(
            collection_name=collection_name,
            documents=documents,
            metadatas=metadatas,
        )


_knowledge_tool: Optional[KnowledgeRetrievalTool] = None


def get_knowledge_retrieval_tool() -> KnowledgeRetrievalTool:
    global _knowledge_tool
    if _knowledge_tool is None:
        _knowledge_tool = KnowledgeRetrievalTool()
    return _knowledge_tool
''')

# --- infrastructure/knowledge/project_kb.py ---
write_file('app/infrastructure/knowledge/project_kb.py', '''
"""项目专属知识库管理"""
from typing import Optional, Dict, Any, List
from app.infrastructure.knowledge.knowledge_retrieval import get_knowledge_retrieval_tool
from app.core.logger import get_logger

logger = get_logger("project_kb")


class ProjectKnowledgeBase:
    """项目专属知识库"""

    def __init__(self, project_id: int, collection_name: str):
        self.project_id = project_id
        self.collection_name = collection_name
        self.retrieval_tool = get_knowledge_retrieval_tool()

    async def add_chapter_context(
        self, chapter_num: int, content: str, summary: str = "",
        metadata: Optional[Dict] = None,
    ):
        """添加章节上下文到知识库"""
        doc_id = f"project-{self.project_id}-chapter-{chapter_num}"
        meta = {
            "project_id": self.project_id,
            "chapter_num": chapter_num,
            "type": "chapter_context",
        }
        if metadata:
            meta.update(metadata)

        documents = [content]
        if summary:
            documents.append(summary)

        await self.retrieval_tool.add_documents(
            collection_name=self.collection_name,
            documents=documents,
            metadatas=[meta] * len(documents),
        )

    async def add_knowledge(
        self, content: str, doc_type: str = "reference",
        metadata: Optional[Dict] = None,
    ):
        """添加知识条目"""
        meta = {
            "project_id": self.project_id,
            "type": doc_type,
        }
        if metadata:
            meta.update(metadata)

        await self.retrieval_tool.add_documents(
            collection_name=self.collection_name,
            documents=[content],
            metadatas=[meta],
        )

    async def retrieve_context(
        self, query: str, n_results: int = 5,
    ) -> List[Dict]:
        """检索项目上下文"""
        return await self.retrieval_tool.retrieve(
            collection_name=self.collection_name,
            query=query,
            n_results=n_results,
            where_filter={"project_id": self.project_id},
        )

    async def build_chapter_summary(
        self, chapters: List[Dict],
    ) -> str:
        """构建章节摘要上下文"""
        summaries = []
        for ch in chapters:
            num = ch.get("chapter_number", 0)
            title = ch.get("chapter_title", "")
            summary = ch.get("summary", "")
            if summary:
                summaries.append(f"第{num}章 {title}: {summary}")

        return "\\n".join(summaries)
''')

# --- infrastructure/knowledge/__init__.py ---
write_file('app/infrastructure/knowledge/__init__.py', '''
"""知识库基础设施模块"""
from app.infrastructure.knowledge.vector_store import get_vector_store, VectorStore
from app.infrastructure.knowledge.knowledge_retrieval import (
    get_knowledge_retrieval_tool, KnowledgeRetrievalTool
)
from app.infrastructure.knowledge.project_kb import ProjectKnowledgeBase

__all__ = [
    "get_vector_store", "VectorStore",
    "get_knowledge_retrieval_tool", "KnowledgeRetrievalTool",
    "ProjectKnowledgeBase",
]
''')

# --- infrastructure/external/style_library.py ---
write_file('app/infrastructure/external/style_library.py', '''
"""风格库管理"""
import json
import os
from typing import Dict, Any, Optional, List
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("style_library")
settings = get_settings()


class StyleLibrary:
    """风格库管理器"""

    DEFAULT_STYLES = {
        "literary_fiction": {
            "id": "literary_fiction",
            "name": "纯文学风",
            "description": "注重文字美感，深度刻画人物内心世界",
            "features": ["长句为主", "心理描写丰富", "象征隐喻多", "叙事节奏舒缓"],
            "temperature": 0.8,
            "prompt_suffix": "请使用纯文学风格创作，注重文字美感和内心描写。",
        },
        "web_novel": {
            "id": "web_novel",
            "name": "网络小说风",
            "description": "节奏明快，情节紧凑，适合网络阅读",
            "features": ["短句为主", "情节推进快", "悬念设置多", "对话简洁有力"],
            "temperature": 0.7,
            "prompt_suffix": "请使用网络小说风格创作，节奏明快，情节紧凑。",
        },
        "suspense": {
            "id": "suspense",
            "name": "悬疑推理风",
            "description": "逻辑严密，伏笔交织，反转精妙",
            "features": ["伏笔精心布局", "逻辑严密", "反转设计精妙", "细节描写克制"],
            "temperature": 0.5,
            "prompt_suffix": "请使用悬疑推理风格创作，注重逻辑和伏笔。",
        },
        "romance": {
            "id": "romance",
            "name": "言情风",
            "description": "情感细腻，人物关系复杂，氛围温馨",
            "features": ["情感描写细腻", "对话生动", "氛围营造温馨", "人物互动丰富"],
            "temperature": 0.75,
            "prompt_suffix": "请使用言情风格创作，情感细腻，氛围温馨。",
        },
        "script_professional": {
            "id": "script_professional",
            "name": "专业剧本风",
            "description": "标准剧本格式，对白精准，场景转换清晰",
            "features": ["标准格式", "对白精准", "场景描述简洁", "镜头语言专业"],
            "temperature": 0.6,
            "prompt_suffix": "请使用专业剧本风格创作，格式标准，对白精准。",
        },
        "wuxia": {
            "id": "wuxia",
            "name": "武侠风",
            "description": "江湖豪气，武打精彩，义薄云天",
            "features": ["武打场面精彩", "江湖气息浓厚", "人物义气深重", "语言古韵犹存"],
            "temperature": 0.7,
            "prompt_suffix": "请使用武侠风格创作，江湖豪气，武打精彩。",
        },
    }

    def __init__(self):
        self._custom_styles: Dict[str, Dict] = {}
        self._load_custom_styles()

    def _load_custom_styles(self):
        style_dir = os.path.join(
            settings._normalize_path(settings.UPLOAD_DIR), "styles"
        )
        if os.path.exists(style_dir):
            for fname in os.listdir(style_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(style_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            style = json.load(f)
                            if "id" in style:
                                self._custom_styles[style["id"]] = style
                    except Exception as e:
                        logger.warning(f"加载风格文件失败 {fname}: {e}")

    def get_all_styles(self) -> List[Dict]:
        all_styles = {**self.DEFAULT_STYLES, **self._custom_styles}
        return list(all_styles.values())

    def get_style_by_id(self, style_id: str) -> Optional[Dict]:
        if style_id in self.DEFAULT_STYLES:
            return self.DEFAULT_STYLES[style_id]
        if style_id in self._custom_styles:
            return self._custom_styles[style_id]
        return None

    def get_prompt_suffix(self, style_id: str) -> str:
        style = self.get_style_by_id(style_id)
        if style:
            return style.get("prompt_suffix", "")
        return ""

    def get_temperature(self, style_id: str) -> float:
        style = self.get_style_by_id(style_id)
        if style:
            return style.get("temperature", 0.7)
        return 0.7


_style_library: Optional[StyleLibrary] = None


def get_style_library() -> StyleLibrary:
    global _style_library
    if _style_library is None:
        _style_library = StyleLibrary()
    return _style_library


def get_style_by_id(style_id: str) -> Optional[Dict]:
    return get_style_library().get_style_by_id(style_id)
''')

# --- infrastructure/external/__init__.py ---
write_file('app/infrastructure/external/__init__.py', '''
"""外部集成模块"""
from app.infrastructure.external.style_library import get_style_library, StyleLibrary

__all__ = ["get_style_library", "StyleLibrary"]
''')

# ==================== 2. API端点 ====================

# --- api/v1/endpoints/quality_control.py ---
write_file('app/api/v1/endpoints/quality_control.py', '''
"""质控API端点"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logger import get_logger
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ResponseModel
from app.domain.services.quality_service import QualityControlService

router = APIRouter()
logger = get_logger("quality_control")


class QCAnalysisRequest(BaseModel):
    """质控分析请求"""
    content: str = Field(..., description="待分析内容")
    analysis_type: str = Field(
        default="chapter",
        description="分析类型: global_outline/chapter/unit_summary"
    )
    dimensions: Optional[List[str]] = Field(None, description="分析维度")
    depth: str = Field(default="standard", description="分析深度: quick/standard/deep")
    project_id: Optional[int] = Field(None, description="项目ID")


class QCFixRequest(BaseModel):
    """质控修正请求"""
    content: str = Field(..., description="原始内容")
    issues: List[Dict[str, Any]] = Field(..., description="待修正问题列表")
    project_id: Optional[int] = Field(None, description="项目ID")


class QCFeedbackRequest(BaseModel):
    """用户反馈请求"""
    issue_id: str = Field(..., description="问题ID")
    dimension: str = Field(..., description="维度")
    category: str = Field(..., description="分类")
    feedback_type: str = Field(
        ..., description="反馈类型: accepted/ignored/false_positive"
    )
    comment: str = Field(default="", description="用户备注")


@router.post("/analyze", response_model=ResponseModel)
async def analyze_quality(
    request: QCAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行质量分析"""
    qc_service = QualityControlService(db=db)

    analysis_map = {
        "global_outline": qc_service.analyze_global_outline,
        "unit_summary": qc_service.analyze_unit_summaries,
        "chapter": qc_service.analyze_chapter,
    }

    analyze_func = analysis_map.get(
        request.analysis_type, qc_service.analyze_chapter
    )

    if request.analysis_type == "global_outline":
        report = await analyze_func(
            content=request.content,
            dimensions=request.dimensions,
            depth=request.depth,
            user_id=current_user.id,
        )
    elif request.analysis_type == "unit_summary":
        report = await analyze_func(
            chapters_data=[{"content": request.content}],
            dimensions=request.dimensions,
            depth=request.depth,
            user_id=current_user.id,
        )
    else:
        report = await analyze_func(
            content=request.content,
            dimensions=request.dimensions,
            depth=request.depth,
            user_id=current_user.id,
        )

    return ResponseModel(data=report.to_dict())


@router.post("/auto-fix", response_model=ResponseModel)
async def auto_fix_quality(
    request: QCFixRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自动修正质控问题"""
    qc_service = QualityControlService(db=db)
    result = await qc_service.auto_fix(
        content=request.content,
        issues=request.issues,
        user_id=current_user.id,
    )
    return ResponseModel(data=result)


@router.post("/feedback", response_model=ResponseModel)
async def submit_feedback(
    request: QCFeedbackRequest,
    current_user: User = Depends(get_current_user),
):
    """提交质控反馈"""
    logger.info(
        f"用户 {current_user.id} 提交反馈: "
        f"issue={request.issue_id}, type={request.feedback_type}"
    )
    return ResponseModel(
        message="反馈已记录",
        data={"issue_id": request.issue_id, "feedback_type": request.feedback_type}
    )
''')

# --- api/v1/endpoints/knowledge.py ---
write_file('app/api/v1/endpoints/knowledge.py', '''
"""知识库API端点"""
import os
import uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ResponseModel
from app.infrastructure.knowledge import (
    get_vector_store, get_knowledge_retrieval_tool
)

router = APIRouter()
logger = get_logger("knowledge")
settings = get_settings()


@router.get("/list", response_model=ResponseModel)
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
):
    """获取项目知识库列表"""
    vector_store = get_vector_store()
    collections = vector_store._get_client().list_collections()
    result = []
    for col in collections:
        if col.name.startswith(f"project_"):
            result.append({
                "name": col.name,
                "document_count": vector_store.count_documents(col.name),
            })
    return ResponseModel(data=result)


@router.post("/upload", response_model=ResponseModel)
async def upload_document(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档到项目知识库"""
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise ValidationException(message=f"不支持的文件类型: {file_ext}")

    upload_dir = os.path.join(settings.get_upload_dir(), "knowledge", str(project_id))
    os.makedirs(upload_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = os.path.join(upload_dir, f"{file_id}{file_ext}")

    import shutil
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    collection_name = f"project_{project_id}"
    retrieval_tool = get_knowledge_retrieval_tool()

    try:
        content = ""
        if file_ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        elif file_ext == ".md":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = f"[上传文档: {file.filename}]"

        if content:
            chunks = _split_text(content, chunk_size=1000, overlap=200)
            metadatas = [
                {"source": file.filename, "chunk_index": i, "project_id": project_id}
                for i in range(len(chunks))
            ]
            await retrieval_tool.add_documents_batch(
                collection_name=collection_name,
                documents=chunks,
                metadatas=metadatas,
            )
    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        raise ValidationException(message=f"文档处理失败: {str(e)}")

    return ResponseModel(
        message="文档上传成功",
        data={"file_name": file.filename, "collection": collection_name}
    )


@router.post("/query", response_model=ResponseModel)
async def query_knowledge(
    project_id: int,
    query: str,
    n_results: int = 5,
    current_user: User = Depends(get_current_user),
):
    """查询项目知识库"""
    collection_name = f"project_{project_id}"
    retrieval_tool = get_knowledge_retrieval_tool()

    results = await retrieval_tool.retrieve(
        collection_name=collection_name,
        query=query,
        n_results=n_results,
    )
    return ResponseModel(data=results)


@router.delete("/{project_id}", response_model=ResponseModel)
async def delete_project_knowledge(
    project_id: int,
    current_user: User = Depends(get_current_user),
):
    """删除项目知识库"""
    collection_name = f"project_{project_id}"
    vector_store = get_vector_store()
    vector_store.delete_collection(collection_name)
    return ResponseModel(message="知识库已删除")


def _split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """文本分块"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks
''')

# --- api/v1/endpoints/style_document.py ---
write_file('app/api/v1/endpoints/style_document.py', '''
"""风格文档API端点"""
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ResponseModel
from app.infrastructure.external.style_library import get_style_library

router = APIRouter()
logger = get_logger("style_document")
settings = get_settings()


@router.get("/library", response_model=ResponseModel)
async def list_styles(
    current_user: User = Depends(get_current_user),
):
    """获取风格库列表"""
    library = get_style_library()
    styles = library.get_all_styles()
    return ResponseModel(data=styles)


@router.get("/library/{style_id}", response_model=ResponseModel)
async def get_style(
    style_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取风格详情"""
    library = get_style_library()
    style = library.get_style_by_id(style_id)
    if not style:
        raise ResourceNotFoundException(message=f"风格 '{style_id}' 不存在")
    return ResponseModel(data=style)


@router.post("/upload", response_model=ResponseModel)
async def upload_style_document(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传风格参考文档"""
    import os, shutil, uuid

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in {".txt", ".md", ".docx", ".pdf"}:
        raise ValidationException(message=f"不支持的文件类型: {file_ext}")

    upload_dir = os.path.join(settings.get_upload_dir(), "styles", str(project_id))
    os.makedirs(upload_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = os.path.join(upload_dir, f"{file_id}{file_ext}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    content = ""
    if file_ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

    style_features = ""
    if content:
        style_features = content[:2000]

    from app.infrastructure.repositories.project_repository_impl import ProjectRepositoryImpl
    repo = ProjectRepositoryImpl(db)
    project = await repo.find_by_id(project_id)
    if project:
        project.style_document_path = file_path
        project.style_document_name = file.filename
        if style_features:
            project.style_config = {"features": style_features}
        await repo.save(project)

    return ResponseModel(
        message="风格文档上传成功",
        data={"file_name": file.filename, "features_length": len(style_features)}
    )


@router.get("/project/{project_id}", response_model=ResponseModel)
async def get_project_style(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目风格配置"""
    from app.infrastructure.repositories.project_repository_impl import ProjectRepositoryImpl
    repo = ProjectRepositoryImpl(db)
    project = await repo.find_by_id(project_id)
    if not project:
        raise ResourceNotFoundException(message="项目不存在")

    return ResponseModel(data={
        "style_document_name": project.style_document_name,
        "style_config": project.style_config,
    })
''')

# ==================== 3. WebSocket ====================

# --- infrastructure/websocket_manager.py ---
write_file('app/infrastructure/websocket_manager.py', '''
"""WebSocket管理器 - 实时进度推送"""
import asyncio
import json
from typing import Dict, Any, Optional, Set
from fastapi import WebSocket
from app.core.logger import get_logger

logger = get_logger("websocket")


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self._connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket):
        """建立WebSocket连接"""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
        logger.info(f"WebSocket连接建立: user_id={user_id}")

    async def disconnect(self, user_id: int, websocket: WebSocket):
        """断开WebSocket连接"""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]
        logger.info(f"WebSocket连接断开: user_id={user_id}")

    async def send_to_user(
        self, user_id: int, event_type: str, data: Dict[str, Any]
    ):
        """向指定用户推送消息"""
        async with self._lock:
            connections = self._connections.get(user_id, set()).copy()

        message = json.dumps(
            {"type": event_type, "data": data},
            ensure_ascii=False,
        )

        disconnected = set()
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"发送WebSocket消息失败: {e}")
                disconnected.add(ws)

        if disconnected:
            async with self._lock:
                if user_id in self._connections:
                    self._connections[user_id] -= disconnected

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """广播消息"""
        async with self._lock:
            all_user_ids = list(self._connections.keys())

        for user_id in all_user_ids:
            await self.send_to_user(user_id, event_type, data)


_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
''')

# --- api/v1/endpoints/websocket.py ---
write_file('app/api/v1/endpoints/websocket.py', '''
"""WebSocket API端点"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from app.core.logger import get_logger
from app.infrastructure.websocket_manager import get_ws_manager

router = APIRouter()
logger = get_logger("websocket")


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None),
):
    """WebSocket连接端点"""
    ws_manager = get_ws_manager()

    user_id = 0
    if token:
        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        if payload:
            user_id = int(payload.get("sub", 0))

    await ws_manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"收到WebSocket消息: user_id={user_id}, data={data[:100]}")
    except WebSocketDisconnect:
        await ws_manager.disconnect(user_id, websocket)
        logger.info(f"用户 {user_id} 断开WebSocket连接")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        await ws_manager.disconnect(user_id, websocket)
''')

# ==================== 4. 更新路由注册 ====================
write_file('app/api/v1/router.py', '''
"""API路由注册"""
from fastapi import APIRouter

api_router = APIRouter()

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.chapters import router as chapters_router
from app.api.v1.endpoints.quality_control import router as qc_router
from app.api.v1.endpoints.knowledge import router as knowledge_router
from app.api.v1.endpoints.style_document import router as style_router
from app.api.v1.endpoints.websocket import router as ws_router

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(projects_router, prefix="/projects", tags=["项目管理"])
api_router.include_router(chapters_router, prefix="/chapters", tags=["章节管理"])
api_router.include_router(qc_router, prefix="/quality-control", tags=["质量管控"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["知识库"])
api_router.include_router(style_router, prefix="/style", tags=["风格文档"])
api_router.include_router(ws_router, tags=["WebSocket"])
''')

# ==================== 5. 更新main.py添加WebSocket ====================
write_file('app/main.py', '''
"""Writer Master 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Writer Master 启动中...")
    await init_db()
    logger.info("数据库初始化完成")
    yield
    await close_db()
    logger.info("Writer Master 已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "app": settings.APP_NAME}


# 注册路由
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")
''')

# ==================== 6. 更新schemas添加质控相关 ====================
write_file('app/schemas/quality_control.py', '''
"""质控相关Schema"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QCAnalysisRequest(BaseModel):
    """质控分析请求"""
    content: str = Field(..., description="待分析内容")
    analysis_type: str = Field(
        default="chapter",
        description="分析类型: global_outline/chapter/unit_summary"
    )
    dimensions: Optional[List[str]] = Field(None, description="分析维度")
    depth: str = Field(
        default="standard",
        description="分析深度: quick/standard/deep"
    )
    project_id: Optional[int] = Field(None, description="项目ID")


class QCFixRequest(BaseModel):
    """质控修正请求"""
    content: str = Field(..., description="原始内容")
    issues: List[Dict[str, Any]] = Field(..., description="待修正问题列表")
    project_id: Optional[int] = Field(None, description="项目ID")


class QCReportResponse(BaseModel):
    """质控报告响应"""
    overall_score: float = 0
    dimension_scores: Dict[str, float] = {}
    issues: List[Dict[str, Any]] = []
    grade: str = ""
    is_passed: bool = False
''')

# ==================== 7. 更新models添加KnowledgeBase ====================
write_file('app/models/knowledge_base.py', '''
"""知识库模型"""
import enum
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum, JSON, Boolean
from app.models.base import BaseModel


class KnowledgeBaseType(str, enum.Enum):
    TEMP = "temp"
    STATIC = "static"


class KnowledgeBaseStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeBaseCategory(str, enum.Enum):
    NOVEL = "novel"
    SCRIPT = "script"
    GENERAL = "general"
    USER_SPECIFIC = "user-specific"
    MANUAL = "manual"


class KnowledgeBase(BaseModel):
    """知识库表"""
    __tablename__ = "knowledge_bases"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, comment="用户ID")
    name = Column(String(100), nullable=False, comment="知识库名称")
    description = Column(Text, nullable=True, comment="描述")
    type = Column(Enum(KnowledgeBaseType), default=KnowledgeBaseType.TEMP,
                  comment="知识库类型")
    category = Column(Enum(KnowledgeBaseCategory), default=KnowledgeBaseCategory.GENERAL,
                      comment="业务分类")
    status = Column(Enum(KnowledgeBaseStatus), default=KnowledgeBaseStatus.PENDING,
                    comment="状态")
    collection_name = Column(String(100), nullable=True, comment="向量集合名称")
    file_path = Column(String(255), nullable=True, comment="文件路径")
    file_type = Column(String(20), nullable=True, comment="文件类型")
    file_size = Column(Integer, default=0, comment="文件大小")
    document_count = Column(Integer, default=0, comment="文档数")
    preprocessor_metadata = Column(JSON, nullable=True, comment="预处理元数据")
    graphrag_enabled = Column(Boolean, default=True, comment="是否启用GraphRAG")

    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, name='{self.name}')>"
''')

# Update models __init__
write_file('app/models/__init__.py', '''
"""数据库模型统一导出"""
from app.models.user import User
from app.models.project import NovelProject, ProjectType, ProjectStatus
from app.models.chapter import NovelChapter, ChapterStatus
from app.models.api_key import UserAPIKey
from app.models.writing_model_config import WritingModelConfig
from app.models.knowledge_base import (
    KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory
)

__all__ = [
    "User", "NovelProject", "ProjectType", "ProjectStatus",
    "NovelChapter", "ChapterStatus", "UserAPIKey", "WritingModelConfig",
    "KnowledgeBase", "KnowledgeBaseType", "KnowledgeBaseStatus",
    "KnowledgeBaseCategory",
]
''')

# ==================== 8. 更新domain services __init__ ====================
write_file('app/domain/services/__init__.py', '''
"""领域服务模块"""
from app.domain.services.outline_service import OutlineService
from app.domain.services.chapter_service import ChapterGenerationService
from app.domain.services.quality_service import QualityControlService

__all__ = [
    "OutlineService", "ChapterGenerationService", "QualityControlService",
]
''')

# ==================== 9. Update infrastructure __init__ ====================
write_file('app/infrastructure/__init__.py', '''
"""基础设施模块"""
''')

print("\n=== T13 Complete: Quality Control + Knowledge Base + Style Document + WebSocket ===")
