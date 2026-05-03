"""T13文件创建脚本 - 批量生成质控/知识库/风格/WebSocket模块文件"""
import os

BASE = r"F:\python_project\writer_master\backend\app"


def write_file(rel_path: str, content: str):
    """写入文件"""
    full_path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Created: {rel_path}")


# ============================================================
# 1. 扩展 constants.py - 添加质控/知识库/WebSocket常量
# ============================================================
CONSTANTS_APPEND = '''

class QualityConstants:
    """质控相关常量"""
    MIN_SCORE = 0
    MAX_SCORE = 100
    PASS_THRESHOLD = 60
    EXCELLENT_THRESHOLD = 80
    WEIGHT_CONSISTENCY = 0.4
    WEIGHT_COHERENCE = 0.35
    WEIGHT_STYLE_MATCH = 0.25
    DEFAULT_ANALYSIS_DEPTH = "standard"
    DEFAULT_AUTO_FIX_THRESHOLD = 0.8
    MAX_SUBSCRIBERS_PER_TASK = 5
    TASK_TIMEOUT_SECONDS = 3600
    SSE_HEARTBEAT_TIMEOUT = 30

    # 质控维度
    DIM_UNIT_STRUCTURE = "unit_structure"
    DIM_UNIT_CHARACTER = "unit_character"
    DIM_UNIT_CONSISTENCY = "unit_consistency"
    DIM_UNIT_TIMELINE_SPACE = "unit_timeline_space"
    DIM_UNIT_OOC = "unit_ooc"
    DEFAULT_DIMENSIONS = [
        "unit_structure", "unit_character",
        "unit_consistency", "unit_timeline_space", "unit_ooc"
    ]

    # 分析深度
    DEPTH_QUICK = "quick"
    DEPTH_STANDARD = "standard"
    DEPTH_DEEP = "deep"


class KnowledgeBaseConstants:
    """知识库相关常量"""
    STATUS_PENDING = "pending"
    STATUS_BUILDING = "building"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STALE_THRESHOLD_MINUTES = 30
    STALE_THRESHOLD_HOURS = 1
    BUILD_BATCH_DELAY_SECONDS = 1
    MIN_OUTLINE_LENGTH = 100


class StyleConstants:
    """风格文档相关常量"""
    ALLOWED_EXTENSIONS = [".txt", ".docx", ".pdf", ".md"]
    MIN_STYLE_CONTENT_LENGTH = 100
    MAX_STYLE_CONTENT_LENGTH = 100000
    STYLE_ANALYSIS_TEMPERATURE = 0.6
    STYLE_ANALYSIS_MAX_TOKENS = 8192
    MAX_BLEND_STYLES = 3
    MIN_BLEND_INTENSITY = 0.0
    MAX_BLEND_INTENSITY = 1.0
    DEFAULT_BLEND_INTENSITY = 0.7


class WebSocketConstants:
    """WebSocket相关常量"""
    CHANNEL_TASK_PROGRESS = "task_progress"
    CHANNEL_QC_PROGRESS = "qc_progress"
    CHANNEL_GENERATION = "generation"
    CHANNEL_SYSTEM = "system"
    HEARTBEAT_INTERVAL_SECONDS = 30
    MAX_MESSAGE_SIZE = 1048576  # 1MB
    RECONNECT_TIMEOUT_SECONDS = 60
'''

write_file("core/constants_ext.py", CONSTANTS_APPEND)


# ============================================================
# 2. 质控 schemas
# ============================================================
write_file("schemas/quality_control.py", '''"""质控相关数据传输对象"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.core.constants import QualityConstants


class QualityAnalysisRequest(BaseModel):
    """质量分析请求"""
    project_id: int
    chapter_ids: Optional[List[int]] = None
    dimensions: Optional[List[str]] = None
    analysis_depth: str = QualityConstants.DEFAULT_ANALYSIS_DEPTH


class ApplyFixRequest(BaseModel):
    """应用修正请求"""
    issue_id: str = Field(..., description="问题ID")
    auto_fix: Optional[Dict[str, Any]] = Field(
        None, description="自动修正方案")
    chapter_number: int = Field(..., description="单元号")
    project_id: Optional[int] = Field(None, description="项目ID")


class GenerateFixRequest(BaseModel):
    """生成修正方案请求"""
    issue_id: str = Field(..., description="问题ID")
    chapter_number: int = Field(..., description="单元号")
    category: str = Field(..., description="问题分类")
    description: str = Field(..., description="问题描述")
    project_id: int = Field(0, description="项目ID")
    chapter_content: str = Field("", description="单元内容")
    global_outline: str = Field("", description="全局大纲")


class ReAnalyzeRequest(BaseModel):
    """重新分析请求"""
    project_id: int
    chapter_number: Optional[int] = None
    dimensions: Optional[List[str]] = None
    depth: str = QualityConstants.DEFAULT_ANALYSIS_DEPTH


class CancelQCRequest(BaseModel):
    """取消质控检测请求"""
    project_id: int


class FeedbackRequest(BaseModel):
    """用户反馈请求"""
    issue_id: str
    dimension: str
    category: str
    feedback_type: str = Field(
        ..., description="反馈类型: accepted/ignored/false_positive")
    comment: str = ""


class UnitQualityControlRequest(BaseModel):
    """单单元质控检测请求"""
    project_id: int
    unit_index: int
    content: str
    dimensions: Optional[List[str]] = None
    depth: str = QualityConstants.DEFAULT_ANALYSIS_DEPTH
    auto_fix: bool = True
    auto_fix_threshold: float = QualityConstants.DEFAULT_AUTO_FIX_THRESHOLD


class GlobalOutlineQCRequest(BaseModel):
    """全局大纲质量检测请求"""
    dimensions: Optional[List[str]] = None
    depth: str = QualityConstants.DEFAULT_ANALYSIS_DEPTH
    existing_outline: Optional[str] = ""


class GlobalOutlineReviseRequest(BaseModel):
    """全局大纲修正请求"""
    quality_report: Dict[str, Any]
    issues_to_fix: List[str]


class ImportedOutlineAutoReviseRequest(BaseModel):
    """导入大纲自动质控修正请求"""
    outline_content: str
    dimensions: Optional[List[str]] = None
    depth: str = QualityConstants.DEFAULT_ANALYSIS_DEPTH


class QualityReportResponse(BaseModel):
    """质量报告响应"""
    report_id: Optional[int] = None
    project_id: int
    analysis_scope: str
    dimensions: List[str]
    overall_score: float
    dimension_scores: Dict[str, float]
    issues: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    is_cached: bool = False


class QualityFixResult(BaseModel):
    """修正方案结果"""
    original: str = Field(..., description="修正前内容")
    fixed: str = Field(..., description="修正后内容")
    description: str = Field("", description="修正说明")
    confidence: float = Field(0.0, description="置信度")
    fix_type: str = Field("unknown", description="修正类型")
    tokens_used: int = Field(0, description="消耗Token数")
''')


# ============================================================
# 3. 知识库 schemas
# ============================================================
write_file("schemas/knowledge_base.py", '''"""知识库相关数据传输对象"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BuildKnowledgeBaseRequest(BaseModel):
    """构建知识库请求"""
    project_id: int
    graphrag_enabled: bool = True


class BuildUnitGraphRequest(BaseModel):
    """构建单元图谱请求"""
    project_id: int
    unit_number: int


class BuildAllUnitGraphsRequest(BaseModel):
    """批量构建单元图谱请求"""
    project_id: int
    unit_numbers: Optional[str] = Field(
        None, description="逗号分隔的单元号，不传则构建所有")


class UpdateKBConfigRequest(BaseModel):
    """更新知识库配置请求"""
    project_id: int
    graphrag_enabled: Optional[bool] = None


class CheckConsistencyRequest(BaseModel):
    """检查内容一致性请求"""
    project_id: int
    content: str
    unit_number: Optional[int] = None


class KnowledgeBaseStatusResponse(BaseModel):
    """知识库状态响应"""
    status: str
    progress: Optional[Dict[str, Any]] = None
    graphrag_enabled: bool = True
    collection_name: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    is_stale: bool = False
''')


# ============================================================
# 4. 风格文档 schemas
# ============================================================
write_file("schemas/style.py", '''"""风格文档相关数据传输对象"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.core.constants import StyleConstants


class StyleDocumentUpdate(BaseModel):
    """风格文档设置更新"""
    ai_elimination_enabled: Optional[bool] = None
    ai_elimination_threshold: Optional[int] = None


class StyleProfile(BaseModel):
    """风格画像"""
    name: str = ""
    description: str = ""
    language_features: Dict[str, Any] = Field(default_factory=dict)
    narrative_features: Dict[str, Any] = Field(default_factory=dict)
    dialogue_features: Dict[str, Any] = Field(default_factory=dict)
    rhetorical_features: Dict[str, Any] = Field(default_factory=dict)


class StyleDocumentResponse(BaseModel):
    """风格文档响应"""
    project_id: int
    style_document_uploaded: bool = False
    style_document_name: Optional[str] = None
    style_profile: Optional[Dict[str, Any]] = None
    style_guide_for_writing: Optional[str] = None
    key_imitation_points: Optional[List[str]] = None
    example_transformations: Optional[List[Dict]] = None
    avoid_patterns: Optional[List[str]] = None
    ai_elimination_enabled: bool = True
    ai_elimination_threshold: int = 50


class BlendStylesRequest(BaseModel):
    """融合文风请求"""
    style_ids: List[str] = Field(
        ..., description="文风ID列表")
    intensity: float = Field(
        StyleConstants.DEFAULT_BLEND_INTENSITY,
        description="风格强度")


class RealTimeStyleGuide(BaseModel):
    """实时风格指导"""
    style_instructions: Dict[str, Any] = Field(default_factory=dict)
    key_reminders: List[str] = Field(default_factory=list)
    style_examples: Dict[str, str] = Field(default_factory=dict)
''')


# ============================================================
# 5. WebSocket schemas
# ============================================================
write_file("schemas/websocket.py", '''"""WebSocket相关数据传输对象"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.constants import WebSocketConstants


class WSMessage(BaseModel):
    """WebSocket消息模型"""
    type: str = Field(..., description="消息类型")
    channel: str = Field(..., description="频道")
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat())
    project_id: Optional[int] = None


class WSProgressUpdate(BaseModel):
    """进度更新消息"""
    progress: float = Field(0.0, description="进度百分比")
    current_step: str = Field("", description="当前步骤")
    message: str = Field("", description="消息")
    total: int = Field(0, description="总数")
    completed: int = Field(0, description="已完成数")


class WSQCProgress(BaseModel):
    """质控进度消息"""
    dimension: str = Field("", description="当前维度")
    status: str = Field("", description="状态")
    progress: float = Field(0.0, description="进度")
    message: str = Field("", description="消息")
''')


print("\n=== Phase 1: Schemas created ===")


# ============================================================
# 6. 质控领域服务
# ============================================================
write_file("domain/services/__init__.py", '''"""领域服务"""
from app.domain.services.quality_service import QualityControlService
from app.domain.services.knowledge_service import KnowledgeBaseService

__all__ = ["QualityControlService", "KnowledgeBaseService"]
''')


write_file("domain/services/quality_service.py", '''"""质控领域服务 - 核心业务逻辑

提供三维质控的核心评估、分析和修正逻辑
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.core.constants import QualityConstants
from app.core.logger import get_logger
from app.domain.models.value_objects.quality_score import QualityScore

logger = get_logger("quality_service")


class QualityControlService:
    """质控领域服务

    职责：
    1. 执行多维度质量分析
    2. 生成质量报告
    3. 管理修正建议
    4. 记录用户反馈
    """

    def __init__(self, db=None):
        self._db = db

    async def analyze_quality(
        self,
        user_id: int,
        project_id: int,
        chapters_data: List[Dict[str, Any]],
        dimensions: Optional[List[str]] = None,
        analysis_depth: str = QualityConstants.DEFAULT_ANALYSIS_DEPTH,
        global_outline: str = "",
        character_profiles: Optional[List] = None,
        worldview_settings: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """执行质量分析

        Args:
            user_id: 用户ID
            project_id: 项目ID
            chapters_data: 章节数据列表
            dimensions: 分析维度
            analysis_depth: 分析深度
            global_outline: 全局大纲
            character_profiles: 人物设定
            worldview_settings: 世界观设定

        Returns:
            质量分析报告
        """
        dimensions = dimensions or QualityConstants.DEFAULT_DIMENSIONS

        logger.info(
            f"[质控分析] 开始: project={project_id}, "
            f"dimensions={dimensions}, depth={analysis_depth}"
        )

        dimension_scores = {}
        all_issues = []

        for dimension in dimensions:
            score, issues = await self._analyze_dimension(
                dimension=dimension,
                chapters_data=chapters_data,
                global_outline=global_outline,
                character_profiles=character_profiles or [],
                worldview_settings=worldview_settings or {},
                depth=analysis_depth,
                user_id=user_id,
                project_id=project_id
            )
            dimension_scores[dimension] = score
            all_issues.extend(issues)

        # 计算综合得分
        overall_score = self._calculate_overall_score(dimension_scores)

        report = {
            "project_id": project_id,
            "analysis_scope": "full" if len(chapters_data) > 1 else "single",
            "dimensions": dimensions,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "issues": all_issues,
            "statistics": {
                "total_chapters": len(chapters_data),
                "total_issues": len(all_issues),
                "analysis_depth": analysis_depth,
                "analyzed_at": datetime.now().isoformat()
            }
        }

        logger.info(
            f"[质控分析] 完成: project={project_id}, "
            f"score={overall_score:.1f}, issues={len(all_issues)}"
        )

        return report

    async def _analyze_dimension(
        self,
        dimension: str,
        chapters_data: List[Dict],
        global_outline: str,
        character_profiles: List,
        worldview_settings: Dict,
        depth: str,
        user_id: int,
        project_id: int
    ) -> tuple:
        """分析单个维度

        Returns:
            (score, issues) 元组
        """
        try:
            from app.infrastructure.ai.llm_manager import get_llm_manager
            from app.infrastructure.ai.prompt_templates.quality_control_prompts import (
                get_dimension_prompt
            )

            llm_manager = get_llm_manager()
            provider = await llm_manager.get_provider_from_db(
                self._db, user_id)

            prompt = get_dimension_prompt(
                dimension=dimension,
                chapters_data=chapters_data,
                global_outline=global_outline,
                character_profiles=character_profiles,
                worldview_settings=worldview_settings,
                depth=depth
            )

            response = await provider.generate(prompt)

            score, issues = self._parse_quality_response(
                response.content, dimension)

            return score, issues

        except Exception as e:
            logger.warning(
                f"[质控分析] 维度 {dimension} LLM分析失败: {e}, "
                f"使用规则引擎兜底"
            )
            return self._rule_based_analyze(
                dimension, chapters_data, global_outline
            )

    def _rule_based_analyze(
        self,
        dimension: str,
        chapters_data: List[Dict],
        global_outline: str
    ) -> tuple:
        """规则引擎兜底分析"""
        score = QualityConstants.PASS_THRESHOLD
        issues = []

        if dimension == QualityConstants.DIM_UNIT_STRUCTURE:
            for ch in chapters_data:
                content = ch.get("content", "")
                if len(content) < 500:
                    score -= 5
                    issues.append({
                        "id": f"rule_{dimension}_{ch.get('chapter_number', 0)}",
                        "dimension": dimension,
                        "category": "content_too_short",
                        "severity": "warning",
                        "description": f"第{ch.get('chapter_number', 0)}单元内容过短",
                        "location": {"chapter_number": ch.get("chapter_number", 0)}
                    })

        elif dimension == QualityConstants.DIM_UNIT_CHARACTER:
            if global_outline:
                char_names = self._extract_character_names(global_outline)
                for ch in chapters_data:
                    content = ch.get("content", "")
                    for name in char_names[:5]:
                        if name in content:
                            break
                    else:
                        if char_names:
                            score -= 3

        elif dimension == QualityConstants.DIM_UNIT_CONSISTENCY:
            for ch in chapters_data:
                content = ch.get("content", "")
                summary = ch.get("summary", "") or ch.get("unit_summary", "")
                if summary and content and len(content) > 500:
                    pass

        score = max(QualityConstants.MIN_SCORE, min(QualityConstants.MAX_SCORE, score))
        return score, issues

    def _extract_character_names(self, text: str) -> List[str]:
        """从文本中提取角色名称（简单规则）"""
        import re
        names = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        return list(set(names))[:20]

    def _parse_quality_response(
        self, response_text: str, dimension: str
    ) -> tuple:
        """解析LLM质控响应"""
        import json
        try:
            result = json.loads(response_text)
            score = result.get("score", QualityConstants.PASS_THRESHOLD)
            issues = result.get("issues", [])
            for issue in issues:
                issue["dimension"] = dimension
                if "id" not in issue:
                    issue["id"] = f"llm_{dimension}_{len(issues)}"
            return score, issues
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"[质控解析] LLM响应非JSON格式")
            return QualityConstants.PASS_THRESHOLD, []

    def _calculate_overall_score(
        self, dimension_scores: Dict[str, float]
    ) -> float:
        """计算综合得分"""
        if not dimension_scores:
            return 0.0

        weights = {
            QualityConstants.DIM_UNIT_STRUCTURE: 0.2,
            QualityConstants.DIM_UNIT_CHARACTER: 0.25,
            QualityConstants.DIM_UNIT_CONSISTENCY: 0.25,
            QualityConstants.DIM_UNIT_TIMELINE_SPACE: 0.15,
            QualityConstants.DIM_UNIT_OOC: 0.15,
        }

        total_weight = 0.0
        weighted_sum = 0.0
        for dim, score in dimension_scores.items():
            weight = weights.get(dim, 0.2)
            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def get_quality_grade(self, score: float) -> str:
        """获取质量等级"""
        quality = QualityScore(
            consistency=int(score),
            coherence=int(score),
            style_match=int(score)
        )
        return quality.grade
''')


# ============================================================
# 7. 知识库领域服务
# ============================================================
write_file("domain/services/knowledge_service.py", '''"""知识库领域服务 - 核心业务逻辑

提供知识库构建、查询和一致性检查的核心业务逻辑
"""
from typing import Optional, List, Dict, Any

from app.core.constants import KnowledgeBaseConstants
from app.core.logger import get_logger

logger = get_logger("knowledge_service")


class KnowledgeBaseService:
    """知识库领域服务

    职责：
    1. 管理知识库构建流程
    2. 提供知识图谱查询
    3. 一致性检查逻辑
    4. 幽灵状态检测
    """

    def is_stale_build(self, kb_status: str, build_progress: Dict,
                       updated_at=None) -> bool:
        """检测知识库构建幽灵状态

        Args:
            kb_status: 当前知识库状态
            build_progress: 构建进度信息
            updated_at: 最后更新时间

        Returns:
            是否为幽灵状态
        """
        from datetime import datetime, timedelta

        if kb_status != KnowledgeBaseConstants.STATUS_BUILDING:
            return False

        progress_info = build_progress or {}
        updated_at_str = progress_info.get(
            "updated_at") or progress_info.get("started_at")

        if updated_at_str:
            try:
                last_update = datetime.fromisoformat(updated_at_str)
                threshold = timedelta(
                    minutes=KnowledgeBaseConstants.STALE_THRESHOLD_MINUTES)
                if datetime.now() - last_update > threshold:
                    return True
            except (ValueError, TypeError):
                pass

        if updated_at:
            threshold = timedelta(
                hours=KnowledgeBaseConstants.STALE_THRESHOLD_HOURS)
            if datetime.now() - updated_at > threshold:
                return True

        return False

    def check_content_consistency(
        self,
        content: str,
        consistency_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检查内容一致性

        Args:
            content: 待检查内容
            consistency_report: 知识图谱一致性报告

        Returns:
            一致性检查结果
        """
        conflicts = []
        suggestions = []

        # 检查人物状态冲突
        for char_name, state in consistency_report.get(
                "character_states", {}).items():
            if char_name in content:
                latest_location = state.get("latest_location")
                if latest_location and latest_location not in content:
                    conflicts.append({
                        "type": "character_location",
                        "character": char_name,
                        "expected": latest_location,
                        "description": (
                            f"角色'{char_name}'当前位置应为"
                            f"'{latest_location}'，但内容中未体现"
                        )
                    })

        # 检查设施状态冲突
        for facility_name, state in consistency_report.get(
                "facility_states", {}).items():
            if facility_name in content:
                facility_status = state.get("status")
                if facility_status in ["关闭", "暂停营业", "损坏"]:
                    conflicts.append({
                        "type": "facility_status",
                        "facility": facility_name,
                        "status": facility_status,
                        "description": (
                            f"设施'{facility_name}'当前状态为"
                            f"'{facility_status}'，请注意一致性"
                        )
                    })

        # 添加待回收伏笔提醒
        for foreshadow in consistency_report.get(
                "pending_foreshadows", []):
            suggestions.append({
                "type": "foreshadow_reminder",
                "name": foreshadow.get("name"),
                "importance": foreshadow.get("importance"),
                "planted_chapter": foreshadow.get("planted_chapter"),
                "description": (
                    f"待回收伏笔: {foreshadow.get('name')} "
                    f"(第{foreshadow.get('planted_chapter', '?')}章)"
                )
            })

        is_consistent = len(conflicts) == 0

        return {
            "is_consistent": is_consistent,
            "conflicts": conflicts,
            "suggestions": suggestions
        }

    def get_unit_outline_content(
        self, project, unit_number: int
    ) -> Optional[str]:
        """获取单元大纲内容

        根据项目类型获取对应的大纲内容
        """
        content_type = project.content_type or "novel"

        outline_map = {
            "novel": "chapter_outlines",
            "series_script": "episode_outlines",
            "movie_script": "scene_outlines",
        }

        outlines_attr = outline_map.get(content_type, "chapter_outlines")
        outlines = getattr(project, outlines_attr, None) or {}

        unit_outline = outlines.get(str(unit_number), {})

        content_fields = [
            "detailed_outline", "chapter_summary",
            "episode_summary", "scene_summary"
        ]
        for field in content_fields:
            content = unit_outline.get(field)
            if content:
                return content

        return None
''')


print("\n=== Phase 2: Domain services created ===")


# ============================================================
# 8. 质控提示词模板
# ============================================================
write_file("infrastructure/ai/prompt_templates/quality_control_prompts.py", '''"""质控提示词模板"""
from typing import List, Dict, Any, Optional

from app.core.constants import QualityConstants


def get_dimension_prompt(
    dimension: str,
    chapters_data: List[Dict[str, Any]],
    global_outline: str = "",
    character_profiles: Optional[List] = None,
    worldview_settings: Optional[Dict] = None,
    depth: str = QualityConstants.DEPTH_STANDARD
) -> str:
    """获取维度分析提示词

    Args:
        dimension: 分析维度
        chapters_data: 章节数据
        global_outline: 全局大纲
        character_profiles: 人物设定
        worldview_settings: 世界观设定
        depth: 分析深度

    Returns:
        完整的分析提示词
    """
    dimension_prompts = {
        QualityConstants.DIM_UNIT_STRUCTURE: _structure_prompt,
        QualityConstants.DIM_UNIT_CHARACTER: _character_prompt,
        QualityConstants.DIM_UNIT_CONSISTENCY: _consistency_prompt,
        QualityConstants.DIM_UNIT_TIMELINE_SPACE: _timeline_prompt,
        QualityConstants.DIM_UNIT_OOC: _ooc_prompt,
    }

    prompt_fn = dimension_prompts.get(dimension, _structure_prompt)
    return prompt_fn(
        chapters_data=chapters_data,
        global_outline=global_outline,
        character_profiles=character_profiles or [],
        worldview_settings=worldview_settings or {},
        depth=depth
    )


def _structure_prompt(**kwargs) -> str:
    """结构分析提示词"""
    chapters = kwargs.get("chapters_data", [])
    depth = kwargs.get("depth", QualityConstants.DEPTH_STANDARD)

    chapters_text = ""
    for ch in chapters:
        content = ch.get("content", "")
        preview = content[:2000] if len(content) > 2000 else content
        chapters_text += f"\\n--- 第{ch.get('chapter_number', 0)}单元 ---\\n{preview}"

    return f"""请分析以下内容的结构质量，重点关注情节节奏、伏笔回收、叙事结构。

分析深度: {depth}

待分析内容:
{chapters_text}

请以JSON格式返回分析结果:
{{
    "score": <0-100的评分>,
    "issues": [
        {{
            "id": "issue_1",
            "category": "structure_category",
            "severity": "warning/error",
            "description": "问题描述",
            "location": {{"chapter_number": 1}},
            "suggestion": "修正建议"
        }}
    ]
}}"""


def _character_prompt(**kwargs) -> str:
    """人物分析提示词"""
    chapters = kwargs.get("chapters_data", [])
    profiles = kwargs.get("character_profiles", [])
    depth = kwargs.get("depth", QualityConstants.DEPTH_STANDARD)

    chapters_text = ""
    for ch in chapters:
        content = ch.get("content", "")
        preview = content[:2000] if len(content) > 2000 else content
        chapters_text += f"\\n--- 第{ch.get('chapter_number', 0)}单元 ---\\n{preview}"

    profiles_text = ""
    if profiles:
        for p in profiles[:10]:
            profiles_text += f"\\n- {p}"

    return f"""请分析以下内容的人物塑造质量，重点关注角色一致性、台词指纹、行为合理性。

人物设定:
{profiles_text}

分析深度: {depth}

待分析内容:
{chapters_text}

请以JSON格式返回分析结果:
{{
    "score": <0-100的评分>,
    "issues": [
        {{
            "id": "issue_1",
            "category": "character_category",
            "severity": "warning/error",
            "description": "问题描述",
            "location": {{"chapter_number": 1}},
            "suggestion": "修正建议"
        }}
    ]
}}"""


def _consistency_prompt(**kwargs) -> str:
    """一致性分析提示词"""
    chapters = kwargs.get("chapters_data", [])
    global_outline = kwargs.get("global_outline", "")
    depth = kwargs.get("depth", QualityConstants.DEPTH_STANDARD)

    chapters_text = ""
    for ch in chapters:
        content = ch.get("content", "")
        preview = content[:2000] if len(content) > 2000 else content
        chapters_text += f"\\n--- 第{ch.get('chapter_number', 0)}单元 ---\\n{preview}"

    outline_preview = global_outline[:3000] if len(global_outline) > 3000 else global_outline

    return f"""请分析以下内容与全局大纲的一致性，重点关注情节走向、设定一致性、逻辑矛盾。

全局大纲:
{outline_preview}

分析深度: {depth}

待分析内容:
{chapters_text}

请以JSON格式返回分析结果:
{{
    "score": <0-100的评分>,
    "issues": [
        {{
            "id": "issue_1",
            "category": "consistency_category",
            "severity": "warning/error",
            "description": "问题描述",
            "location": {{"chapter_number": 1}},
            "suggestion": "修正建议"
        }}
    ]
}}"""


def _timeline_prompt(**kwargs) -> str:
    """时空一致性分析提示词"""
    chapters = kwargs.get("chapters_data", [])
    depth = kwargs.get("depth", QualityConstants.DEPTH_STANDARD)

    chapters_text = ""
    for ch in chapters:
        content = ch.get("content", "")
        preview = content[:2000] if len(content) > 2000 else content
        chapters_text += f"\\n--- 第{ch.get('chapter_number', 0)}单元 ---\\n{preview}"

    return f"""请分析以下内容的时空一致性，重点关注时间线跳跃、空间位置矛盾、场景转换合理性。

分析深度: {depth}

待分析内容:
{chapters_text}

请以JSON格式返回分析结果:
{{
    "score": <0-100的评分>,
    "issues": [
        {{
            "id": "issue_1",
            "category": "timeline_category",
            "severity": "warning/error",
            "description": "问题描述",
            "location": {{"chapter_number": 1}},
            "suggestion": "修正建议"
        }}
    ]
}}"""


def _ooc_prompt(**kwargs) -> str:
    """OOC检测分析提示词"""
    chapters = kwargs.get("chapters_data", [])
    profiles = kwargs.get("character_profiles", [])
    worldview = kwargs.get("worldview_settings", {})
    depth = kwargs.get("depth", QualityConstants.DEPTH_STANDARD)

    chapters_text = ""
    for ch in chapters:
        content = ch.get("content", "")
        preview = content[:2000] if len(content) > 2000 else content
        chapters_text += f"\\n--- 第{ch.get('chapter_number', 0)}单元 ---\\n{preview}"

    return f"""请分析以下内容是否存在OOC(角色失控)问题，重点关注角色行为偏离设定、世界观违背、角色突然性格转变。

人物设定: {profiles[:5] if profiles else '无'}
世界观: {worldview if worldview else '无'}

分析深度: {depth}

待分析内容:
{chapters_text}

请以JSON格式返回分析结果:
{{
    "score": <0-100的评分>,
    "issues": [
        {{
            "id": "issue_1",
            "category": "ooc_category",
            "severity": "warning/error",
            "description": "问题描述",
            "location": {{"chapter_number": 1}},
            "suggestion": "修正建议"
        }}
    ]
}}"""


def get_fix_prompt(
    issue: Dict[str, Any],
    chapter_content: str,
    unit_summary: str = "",
    knowledge_graph_context: str = "",
    character_profiles: Optional[List] = None,
    worldview_settings: Optional[Dict] = None,
) -> str:
    """获取修正方案提示词"""
    return f"""请针对以下质量问题生成修正方案。

问题描述:
- 类别: {issue.get('category', 'unknown')}
- 严重度: {issue.get('severity', 'warning')}
- 描述: {issue.get('description', '')}
- 建议: {issue.get('suggestion', '')}

单元概述: {unit_summary[:500] if unit_summary else '无'}

{f'知识图谱上下文: {knowledge_graph_context[:1000]}' if knowledge_graph_context else ''}

当前单元内容:
{chapter_content[:3000]}

请以JSON格式返回修正方案:
{{
    "original": "需要修正的原文片段",
    "fixed": "修正后的内容",
    "description": "修正说明",
    "confidence": <0.0-1.0的置信度>,
    "type": "replace/insert/delete"
}}"""
''')


# ============================================================
# 9. 修正生成器 (infrastructure)
# ============================================================
write_file("infrastructure/ai/fix_generator.py", '''"""修正方案生成器

调用LLM为质控问题生成修正建议
"""
from typing import Optional, Dict, Any, List

from app.core.constants import QualityConstants, TokenConstants
from app.core.logger import get_logger
from app.infrastructure.ai.prompt_templates.quality_control_prompts import (
    get_fix_prompt
)

logger = get_logger("fix_generator")


class QualityFixGenerator:
    """修正方案生成器

    职责：
    1. 为质控问题生成修正建议
    2. 调用LLM生成智能修正方案
    3. 解析和验证修正结果
    """

    async def generate_fix(
        self,
        issue: Dict[str, Any],
        chapter_content: str,
        unit_summary: str = "",
        knowledge_graph_context: str = "",
        character_profiles: Optional[List] = None,
        worldview_settings: Optional[Dict] = None,
        db=None,
        user_id: int = 0
    ) -> Dict[str, Any]:
        """为问题生成修正方案

        Args:
            issue: 质控问题
            chapter_content: 章节内容
            unit_summary: 单元概述
            knowledge_graph_context: 知识图谱上下文
            character_profiles: 人物设定
            worldview_settings: 世界观设定
            db: 数据库会话
            user_id: 用户ID

        Returns:
            修正方案字典
        """
        try:
            from app.infrastructure.ai.llm_manager import get_llm_manager
            import json

            llm_manager = get_llm_manager()
            provider = await llm_manager.get_provider_from_db(db, user_id)

            prompt = get_fix_prompt(
                issue=issue,
                chapter_content=chapter_content,
                unit_summary=unit_summary,
                knowledge_graph_context=knowledge_graph_context,
                character_profiles=character_profiles,
                worldview_settings=worldview_settings
            )

            response = await provider.generate(prompt)

            fix_result = self._parse_fix_response(response.content)

            fix_result["tokens_used"] = getattr(
                response, "tokens_used", 0)

            logger.info(
                f"[修正生成] 问题={issue.get('id')}, "
                f"confidence={fix_result.get('confidence', 0):.2f}"
            )

            return fix_result

        except Exception as e:
            logger.warning(f"[修正生成] LLM生成失败: {e}")
            return {
                "original": "",
                "fixed": "",
                "description": f"自动修正失败: {str(e)}",
                "confidence": 0.0,
                "type": "failed",
                "tokens_used": 0
            }

    def _parse_fix_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM修正响应"""
        import json

        try:
            result = json.loads(response_text)
            return {
                "original": result.get("original", ""),
                "fixed": result.get("fixed", ""),
                "description": result.get("description", ""),
                "confidence": float(result.get("confidence", 0.0)),
                "type": result.get("type", "replace"),
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("[修正解析] LLM响应非JSON格式")
            return {
                "original": "",
                "fixed": "",
                "description": "修正方案解析失败",
                "confidence": 0.0,
                "type": "parse_failed",
            }
''')


# ============================================================
# 10. SSE进度订阅管理器 (infrastructure)
# ============================================================
write_file("infrastructure/sse_subscriber.py", '''"""SSE进度订阅管理器

提供质控进度的SSE实时推送功能
"""
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.constants import QualityConstants
from app.core.logger import get_logger

logger = get_logger("sse_subscriber")


class QCProgressSubscriber:
    """质控进度SSE订阅管理器

    功能：
    1. 管理SSE订阅队列
    2. 发布进度事件
    3. 自动清理过期订阅
    4. 限制每任务订阅数
    """

    def __init__(self):
        self._subscribers: Dict[str, dict] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """订阅任务进度

        Args:
            task_id: 任务ID

        Returns:
            asyncio.Queue 事件队列

        Raises:
            ValueError: 订阅数已达上限
        """
        self._cleanup_expired_tasks()

        if task_id not in self._subscribers:
            self._subscribers[task_id] = {
                "queues": [],
                "created_at": datetime.now()
            }

        max_subs = QualityConstants.MAX_SUBSCRIBERS_PER_TASK
        if len(self._subscribers[task_id]["queues"]) >= max_subs:
            raise ValueError(f"任务 {task_id} 订阅数已达上限")

        queue = asyncio.Queue()
        self._subscribers[task_id]["queues"].append(queue)
        logger.info(
            f"[SSE订阅] task_id={task_id}, "
            f"当前订阅数: {len(self._subscribers[task_id]['queues'])}")
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        """取消订阅"""
        if task_id in self._subscribers:
            if queue in self._subscribers[task_id]["queues"]:
                self._subscribers[task_id]["queues"].remove(queue)
            if not self._subscribers[task_id]["queues"]:
                del self._subscribers[task_id]
                logger.info(f"[SSE取消订阅] 任务 {task_id} 已清理")

    async def publish(self, task_id: str, event: Dict):
        """发布进度事件"""
        self._cleanup_expired_tasks()

        if task_id in self._subscribers:
            for queue in self._subscribers[task_id]["queues"]:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.warning(f"[SSE发布] 队列推送失败: {e}")

    def _cleanup_expired_tasks(self):
        """清理过期任务"""
        now = datetime.now()
        timeout = QualityConstants.TASK_TIMEOUT_SECONDS
        expired_tasks = []

        for task_id, data in list(self._subscribers.items()):
            created_at = data.get("created_at", now)
            if (now - created_at).total_seconds() > timeout:
                expired_tasks.append(task_id)

        for task_id in expired_tasks:
            del self._subscribers[task_id]
            logger.info(f"[SSE清理] 过期任务已清理: {task_id}")

    def get_task_count(self) -> int:
        """获取当前任务数"""
        return len(self._subscribers)

    def get_total_subscribers(self) -> int:
        """获取总订阅者数"""
        return sum(
            len(data["queues"]) for data in self._subscribers.values()
        )


# 全局单例
_qc_subscriber: Optional[QCProgressSubscriber] = None


def get_qc_subscriber() -> QCProgressSubscriber:
    """获取质控SSE订阅器单例"""
    global _qc_subscriber
    if _qc_subscriber is None:
        _qc_subscriber = QCProgressSubscriber()
    return _qc_subscriber


async def event_generator(task_id: str, queue: asyncio.Queue):
    """SSE事件生成器

    格式:
    event: progress
    data: {"dimension": "global_structure", "status": "started"}
    """
    try:
        yield (
            f"event: connected\\ndata: "
            f"{json.dumps({'task_id': task_id, 'message': 'SSE连接成功'})}\\n\\n"
        )

        while True:
            try:
                timeout = QualityConstants.SSE_HEARTBEAT_TIMEOUT
                event = await asyncio.wait_for(queue.get(), timeout=timeout)

                if event.get("type") in ("completed", "error"):
                    event_type = event.get("type", "progress")
                    yield (
                        f"event: {event_type}\\ndata: "
                        f"{json.dumps(event)}\\n\\n"
                    )
                    break

                yield (
                    f"event: progress\\ndata: "
                    f"{json.dumps(event)}\\n\\n"
                )

            except asyncio.TimeoutError:
                yield f": heartbeat\\n\\n"

    except Exception as e:
        logger.error(f"[SSE推送] 事件生成器异常: {e}")
        yield (
            f"event: error\\ndata: "
            f"{json.dumps({'error': str(e)})}\\n\\n"
        )
    finally:
        subscriber = get_qc_subscriber()
        subscriber.unsubscribe(task_id, queue)
        logger.info(f"[SSE推送] 连接关闭: task_id={task_id}")


async def publish_qc_progress(
    task_id: str,
    event_type: str,
    dimension: str = None,
    status: str = None,
    progress: float = None,
    message: str = None,
    data: Dict = None
):
    """发布质控进度事件

    Args:
        task_id: 任务ID
        event_type: 事件类型(started/progress/completed/error)
        dimension: 维度名称
        status: 状态(running/success/failed)
        progress: 进度(0-100)
        message: 消息
        data: 附加数据
    """
    event = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id
    }

    if dimension:
        event["dimension"] = dimension
    if status:
        event["status"] = status
    if progress is not None:
        event["progress"] = progress
    if message:
        event["message"] = message
    if data:
        event["data"] = data

    subscriber = get_qc_subscriber()
    await subscriber.publish(task_id, event)
''')


# ============================================================
# 11. WebSocket管理器 (infrastructure)
# ============================================================
write_file("infrastructure/websocket_manager.py", '''"""WebSocket管理器

提供实时进度推送的WebSocket连接管理
"""
import asyncio
import json
from typing import Dict, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket

from app.core.constants import WebSocketConstants
from app.core.logger import get_logger

logger = get_logger("websocket_manager")


class ConnectionManager:
    """WebSocket连接管理器

    功能：
    1. 管理WebSocket连接的生命周期
    2. 按频道分组推送消息
    3. 心跳保活机制
    4. 连接数限制
    """

    def __init__(self):
        # channel -> set of websocket connections
        self._channels: Dict[str, Set[WebSocket]] = {}
        self._connection_meta: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        channel: str,
        project_id: Optional[int] = None
    ):
        """建立WebSocket连接

        Args:
            websocket: WebSocket连接
            channel: 频道名称
            project_id: 项目ID(可选)
        """
        await websocket.accept()

        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(websocket)

        self._connection_meta[websocket] = {
            "channel": channel,
            "project_id": project_id,
            "connected_at": datetime.now().isoformat()
        }

        logger.info(
            f"[WS] 连接建立: channel={channel}, "
            f"project_id={project_id}"
        )

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        meta = self._connection_meta.pop(websocket, {})
        channel = meta.get("channel")

        if channel and channel in self._channels:
            self._channels[channel].discard(websocket)
            if not self._channels[channel]:
                del self._channels[channel]

        logger.info(f"[WS] 连接断开: channel={channel}")

    async def send_message(
        self,
        websocket: WebSocket,
        message: Dict[str, Any]
    ):
        """发送消息到单个连接"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"[WS] 发送消息失败: {e}")
            self.disconnect(websocket)

    async def broadcast_to_channel(
        self,
        channel: str,
        message: Dict[str, Any],
        project_id: Optional[int] = None
    ):
        """向频道广播消息

        Args:
            channel: 频道名称
            message: 消息内容
            project_id: 项目ID(可选，用于过滤)
        """
        connections = self._channels.get(channel, set())
        disconnected = []

        for ws in connections:
            # 如果指定了project_id，只推送给该项目的连接
            if project_id is not None:
                meta = self._connection_meta.get(ws, {})
                if meta.get("project_id") != project_id:
                    continue

            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def send_progress_update(
        self,
        channel: str,
        project_id: int,
        progress: float,
        current_step: str = "",
        message: str = "",
        total: int = 0,
        completed: int = 0
    ):
        """发送进度更新消息"""
        msg = {
            "type": "progress_update",
            "channel": channel,
            "data": {
                "progress": progress,
                "current_step": current_step,
                "message": message,
                "total": total,
                "completed": completed,
            },
            "project_id": project_id,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_channel(channel, msg, project_id)

    async def send_qc_progress(
        self,
        project_id: int,
        dimension: str = "",
        status: str = "",
        progress: float = 0.0,
        message: str = ""
    ):
        """发送质控进度消息"""
        msg = {
            "type": "qc_progress",
            "channel": WebSocketConstants.CHANNEL_QC_PROGRESS,
            "data": {
                "dimension": dimension,
                "status": status,
                "progress": progress,
                "message": message
            },
            "project_id": project_id,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_channel(
            WebSocketConstants.CHANNEL_QC_PROGRESS, msg, project_id)

    def get_channel_count(self, channel: str) -> int:
        """获取频道连接数"""
        return len(self._channels.get(channel, set()))

    def get_total_connections(self) -> int:
        """获取总连接数"""
        return sum(
            len(conns) for conns in self._channels.values()
        )


# 全局单例
_ws_manager: Optional[ConnectionManager] = None


def get_ws_manager() -> ConnectionManager:
    """获取WebSocket管理器单例"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = ConnectionManager()
    return _ws_manager
''')


# ============================================================
# 12. 知识库基础设施 - 向量存储
# ============================================================
write_file("infrastructure/knowledge/__init__.py", '''"""知识库基础设施"""
''')


write_file("infrastructure/knowledge/vector_store.py", '''"""项目向量存储

基于ChromaDB的项目专属向量存储实现
"""
from typing import Optional, List, Dict, Any
from app.core.logger import get_logger
from app.core.config import get_settings

logger = get_logger("vector_store")
settings = get_settings()


class ProjectVectorStore:
    """项目向量存储

    职责：
    1. 管理项目专属ChromaDB集合
    2. 文档分段与向量化
    3. 语义检索
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        """获取ChromaDB客户端（延迟初始化）"""
        if self._client is None:
            try:
                import chromadb
                persist_dir = settings.get_chroma_persist_dir()
                self._client = chromadb.PersistentClient(path=persist_dir)
            except ImportError:
                logger.warning("chromadb未安装，向量存储不可用")
                return None
        return self._client

    def get_collection_name(self, project_id: int) -> str:
        """获取项目集合名称"""
        return f"project_{project_id}_kb"

    async def add_chapter(
        self,
        project_id: int,
        chapter_number: int,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """添加章节内容到向量库

        Args:
            project_id: 项目ID
            chapter_number: 章节号
            content: 章节内容
            metadata: 元数据

        Returns:
            是否成功
        """
        client = self._get_client()
        if not client:
            return False

        try:
            collection_name = self.get_collection_name(project_id)
            collection = client.get_or_create_collection(
                name=collection_name)

            # 分段
            chunks = self._split_content(content)
            ids = [
                f"ch{chapter_number}_chunk{i}"
                for i in range(len(chunks))
            ]
            metas = [
                {
                    "chapter_number": chapter_number,
                    "chunk_index": i,
                    **(metadata or {})
                }
                for i in range(len(chunks))
            ]

            collection.upsert(
                ids=ids,
                documents=chunks,
                metadatas=metas
            )

            logger.info(
                f"[向量库] 添加章节: project={project_id}, "
                f"chapter={chapter_number}, chunks={len(chunks)}"
            )
            return True

        except Exception as e:
            logger.error(f"[向量库] 添加章节失败: {e}")
            return False

    async def search(
        self,
        project_id: int,
        query: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """语义检索

        Args:
            project_id: 项目ID
            query: 查询文本
            n_results: 返回结果数

        Returns:
            检索结果列表
        """
        client = self._get_client()
        if not client:
            return []

        try:
            collection_name = self.get_collection_name(project_id)
            try:
                collection = client.get_collection(name=collection_name)
            except Exception:
                return []

            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )

            search_results = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                search_results.append({
                    "content": doc,
                    "metadata": results.get("metadatas", [[]])[0][i],
                    "distance": results.get("distances", [[]])[0][i]
                    if results.get("distances") else None
                })

            return search_results

        except Exception as e:
            logger.error(f"[向量库] 检索失败: {e}")
            return []

    async def delete_collection(self, project_id: int) -> bool:
        """删除项目集合"""
        client = self._get_client()
        if not client:
            return False

        try:
            collection_name = self.get_collection_name(project_id)
            client.delete_collection(name=collection_name)
            logger.info(f"[向量库] 删除集合: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"[向量库] 删除集合失败: {e}")
            return False

    def _split_content(
        self,
        content: str,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[str]:
        """内容分段"""
        if not content:
            return []

        chunks = []
        start = 0
        while start < len(content):
            end = start + chunk_size
            chunks.append(content[start:end])
            start = end - overlap

        return [c for c in chunks if len(c.strip()) > 50]

    def get_stats(self, project_id: int) -> Dict[str, Any]:
        """获取集合统计信息"""
        client = self._get_client()
        if not client:
            return {"status": "unavailable"}

        try:
            collection_name = self.get_collection_name(project_id)
            collection = client.get_collection(name=collection_name)
            count = collection.count()
            return {
                "status": "ready",
                "document_count": count,
                "collection_name": collection_name
            }
        except Exception:
            return {"status": "not_found", "document_count": 0}
''')


# ============================================================
# 13. 知识图谱 (GraphRAG)
# ============================================================
write_file("infrastructure/knowledge/graph_rag.py", '''"""知识图谱存储

基于NetworkX的知识图谱实现，用于GraphRAG
"""
import os
import json
from typing import Optional, List, Dict, Any

from app.core.logger import get_logger
from app.core.config import get_settings

logger = get_logger("graph_rag")
settings = get_settings()


class KnowledgeGraph:
    """知识图谱

    职责：
    1. 构建和存储知识图谱
    2. 实体和关系管理
    3. 图谱查询和一致性检查
    """

    def __init__(self, persist_path: Optional[str] = None):
        self._persist_path = persist_path
        self._graph = None

    @property
    def graph(self):
        """获取图对象"""
        return self._graph

    def load(self):
        """从文件加载图谱"""
        if not self._persist_path or not os.path.exists(self._persist_path):
            logger.warning(f"[图谱] 文件不存在: {self._persist_path}")
            self._init_empty_graph()
            return

        try:
            import networkx as nx
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._graph = nx.node_link_graph(data, directed=True)
            logger.info(
                f"[图谱] 加载成功: {self._graph.number_of_nodes()}节点, "
                f"{self._graph.number_of_edges()}边"
            )
        except ImportError:
            logger.warning("networkx未安装，使用简单字典存储")
            self._init_empty_graph()
        except Exception as e:
            logger.error(f"[图谱] 加载失败: {e}")
            self._init_empty_graph()

    def save(self):
        """保存图谱到文件"""
        if not self._persist_path or self._graph is None:
            return

        try:
            import networkx as nx
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            data = nx.node_link_data(self._graph)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[图谱] 保存成功: {self._persist_path}")
        except Exception as e:
            logger.error(f"[图谱] 保存失败: {e}")

    def _init_empty_graph(self):
        """初始化空图谱"""
        try:
            import networkx as nx
            self._graph = nx.DiGraph()
        except ImportError:
            self._graph = {"nodes": {}, "edges": []}

    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        name: str,
        attributes: Optional[Dict] = None
    ):
        """添加实体节点"""
        if self._graph is None:
            self._init_empty_graph()

        try:
            import networkx as nx
            if isinstance(self._graph, nx.DiGraph):
                self._graph.add_node(
                    entity_id,
                    type=entity_type,
                    text=name,
                    attributes=attributes or {}
                )
        except ImportError:
            self._graph["nodes"][entity_id] = {
                "type": entity_type,
                "text": name,
                "attributes": attributes or {}
            }

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        attributes: Optional[Dict] = None
    ):
        """添加关系边"""
        if self._graph is None:
            self._init_empty_graph()

        try:
            import networkx as nx
            if isinstance(self._graph, nx.DiGraph):
                self._graph.add_edge(
                    source_id, target_id,
                    type=relation_type,
                    attributes=attributes or {}
                )
        except ImportError:
            self._graph["edges"].append({
                "source": source_id,
                "target": target_id,
                "type": relation_type,
                "attributes": attributes or {}
            })

    def get_consistency_report(
        self, unit_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取一致性报告"""
        report = {
            "character_states": {},
            "facility_states": {},
            "unfinished_events": [],
            "pending_foreshadows": [],
            "consistency_warnings": []
        }

        if self._graph is None:
            return report

        try:
            import networkx as nx
            if isinstance(self._graph, nx.DiGraph):
                for node_id, data in self._graph.nodes(data=True):
                    if data.get("type") == "人物状态":
                        name = data.get("text", "")
                        attrs = data.get("attributes", {})
                        report["character_states"][name] = attrs
        except (ImportError, AttributeError):
            pass

        return report

    def get_entity_count(self) -> int:
        """获取实体数量"""
        if self._graph is None:
            return 0
        try:
            import networkx as nx
            if isinstance(self._graph, nx.DiGraph):
                return self._graph.number_of_nodes()
        except ImportError:
            return len(self._graph.get("nodes", {}))
        return 0

    def get_relation_count(self) -> int:
        """获取关系数量"""
        if self._graph is None:
            return 0
        try:
            import networkx as nx
            if isinstance(self._graph, nx.DiGraph):
                return self._graph.number_of_edges()
        except ImportError:
            return len(self._graph.get("edges", []))
        return 0
''')


print("\n=== Phase 3: Infrastructure created ===")


# ============================================================
# 14. 质控API端点
# ============================================================
write_file("api/v1/endpoints/quality_control.py", '''"""质量管控 API 端点

提供质量分析、修正、SSE实时推送等功能
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.models.project import NovelProject
from app.models.chapter import NovelChapter
from app.schemas.common import ResponseModel
from app.schemas.quality_control import (
    ApplyFixRequest, GenerateFixRequest, ReAnalyzeRequest,
    CancelQCRequest, FeedbackRequest, UnitQualityControlRequest,
    GlobalOutlineQCRequest, GlobalOutlineReviseRequest,
    ImportedOutlineAutoReviseRequest, QualityReportResponse
)
from app.core.constants import QualityConstants
from app.core.exceptions import (
    ResourceNotFoundException, ValidationException
)
from app.core.logger import get_logger

logger = get_logger("quality_control_api")
router = APIRouter()


# ==================== 辅助函数 ====================

async def _generate_fixes_for_issues(
    issues: list,
    chapters_data: list,
    project: Any,
    db: Any,
    user_id: int
) -> list:
    """为问题列表生成修正建议"""
    from app.infrastructure.ai.fix_generator import QualityFixGenerator

    fix_generator = QualityFixGenerator()
    issues_with_fixes = []

    for issue in issues:
        chapter_number = issue.get('location', {}).get('chapter_number', 0)
        if not chapter_number:
            issues_with_fixes.append(issue)
            continue

        chapter_content = ""
        chapter_summary = ""
        for ch in chapters_data:
            if ch.get('chapter_number') == chapter_number:
                chapter_content = ch.get('content', '')
                chapter_summary = ch.get('summary', '') or ch.get(
                    'unit_summary', '')
                break

        if not chapter_content:
            issues_with_fixes.append(issue)
            continue

        try:
            fix_result = await fix_generator.generate_fix(
                issue=issue,
                chapter_content=chapter_content,
                unit_summary=chapter_summary,
                character_profiles=getattr(
                    project, 'character_profiles', []) or [],
                worldview_settings=getattr(
                    project, 'worldview_settings', {}) or {},
                db=db,
                user_id=user_id
            )
            issue['auto_fix'] = fix_result
            issues_with_fixes.append(issue)
        except Exception as e:
            logger.warning(f"[修正建议] 生成失败: {e}")
            issues_with_fixes.append(issue)

    return issues_with_fixes


# ==================== 质量分析 ====================

@router.post("/projects/{project_id}/quality-control/analyze")
async def analyze_quality(
    project_id: int,
    request: ReAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """执行质量分析"""
    try:
        from app.domain.services.quality_service import QualityControlService

        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取章节数据
        chapters_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        if request.chapter_number:
            chapters_query = chapters_query.where(
                NovelChapter.chapter_number == request.chapter_number
            )
        chapters_query = chapters_query.order_by(NovelChapter.chapter_number)
        chapters_result = await db.execute(chapters_query)
        chapters = chapters_result.scalars().all()

        chapters_data = []
        for chapter in chapters:
            content = chapter.final_content or chapter.draft_content or ""
            chapters_data.append({
                "id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "content": content,
                "summary": content[:500] if content else ""
            })

        if not chapters_data:
            return ResponseModel(
                success=False, message="未找到章节数据"
            )

        qc_service = QualityControlService(db=db)
        report = await qc_service.analyze_quality(
            user_id=current_user.id,
            project_id=project_id,
            chapters_data=chapters_data,
            dimensions=request.dimensions,
            analysis_depth=request.depth,
            global_outline=getattr(
                project, 'global_outline_content', '') or "",
        )

        # 为问题生成修正建议
        issues_with_fixes = await _generate_fixes_for_issues(
            issues=report.get('issues', []),
            chapters_data=chapters_data,
            project=project,
            db=db,
            user_id=current_user.id
        )
        report['issues'] = issues_with_fixes

        return ResponseModel(success=True, data=report)

    except ResourceNotFoundException:
        raise
    except Exception as e:
        logger.error(f"质量分析失败: {e}", exc_info=True)
        return ResponseModel(success=False, message=f"分析失败: {str(e)}")


# ==================== 修正方案 ====================

@router.post("/quality-control/apply-fix")
async def apply_quality_fix(
    request: ApplyFixRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """应用质量修正方案"""
    try:
        query = select(NovelChapter).where(
            NovelChapter.chapter_number == request.chapter_number,
            NovelChapter.project_id == request.project_id
        )
        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            return ResponseModel(
                success=False, message=f"未找到第{request.chapter_number}单元"
            )

        old_content = chapter.final_content or chapter.draft_content or ""
        auto_fix = request.auto_fix

        if not auto_fix or not auto_fix.get("fixed"):
            from app.infrastructure.ai.fix_generator import QualityFixGenerator

            project_query = select(NovelProject).where(
                NovelProject.id == request.project_id)
            project_result = await db.execute(project_query)
            project = project_result.scalar_one_or_none()

            if not project:
                return ResponseModel(
                    success=False, message="项目不存在"
                )

            fix_generator = QualityFixGenerator()
            auto_fix = await fix_generator.generate_fix(
                issue={"id": request.issue_id,
                       "location": {"chapter_number": request.chapter_number}},
                chapter_content=old_content,
                db=db, user_id=current_user.id
            )

        new_content = auto_fix.get("fixed", old_content)

        if chapter.final_content:
            chapter.final_content = new_content
        else:
            chapter.draft_content = new_content

        await db.commit()

        return ResponseModel(
            success=True,
            message="修正已成功应用",
            data={
                "chapter_number": request.chapter_number,
                "old_content_length": len(old_content),
                "new_content_length": len(new_content),
                "confidence": auto_fix.get("confidence", 0)
            }
        )

    except Exception as e:
        logger.error(f"应用修正失败: {e}", exc_info=True)
        await db.rollback()
        return ResponseModel(success=False, message=f"应用修正失败: {str(e)}")


@router.post("/quality-control/generate-fix")
async def generate_quality_fix(
    request: GenerateFixRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成智能修正方案"""
    try:
        from app.infrastructure.ai.fix_generator import QualityFixGenerator

        chapter_content = ""
        if request.project_id > 0:
            query = select(NovelChapter).where(
                NovelChapter.chapter_number == request.chapter_number,
                NovelChapter.project_id == request.project_id
            )
            result = await db.execute(query)
            chapter = result.scalar_one_or_none()
            if chapter:
                chapter_content = (
                    chapter.final_content or chapter.draft_content or ""
                )

        if not chapter_content:
            chapter_content = request.chapter_content or request.description

        fix_generator = QualityFixGenerator()
        fix_result = await fix_generator.generate_fix(
            issue={
                "id": request.issue_id,
                "category": request.category,
                "description": request.description,
                "location": {"chapter_number": request.chapter_number}
            },
            chapter_content=chapter_content,
            db=db, user_id=current_user.id
        )

        return ResponseModel(success=True, data=fix_result)

    except Exception as e:
        logger.error(f"生成修正方案失败: {e}", exc_info=True)
        return ResponseModel(
            success=False, message=f"生成修正方案失败: {str(e)}"
        )


# ==================== 全局大纲质控 ====================

@router.post("/quality-control/global-outline/{project_id}")
async def analyze_global_outline_quality(
    project_id: int,
    request: GlobalOutlineQCRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """对全局大纲执行质量检测"""
    try:
        from app.domain.services.quality_service import QualityControlService
        from app.infrastructure.sse_subscriber import publish_qc_progress

        task_id = f"qc_{current_user.id}_{uuid.uuid4().hex[:8]}"

        global_outline_content = None
        project = None

        if project_id == 0:
            global_outline_content = request.existing_outline or ''
        else:
            query = select(NovelProject).where(
                NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                return ResponseModel(
                    success=False, message="项目不存在"
                )
            global_outline_content = getattr(
                project, 'global_outline_content', None) or ''

        if not global_outline_content:
            return ResponseModel(
                success=False, message="全局大纲内容为空"
            )

        chapters_data = [{
            "chapter_number": 0,
            "content": global_outline_content,
            "summary": global_outline_content[:500]
        }]

        qc_service = QualityControlService(db=db)
        quality_report = await qc_service.analyze_quality(
            user_id=current_user.id,
            project_id=project_id,
            chapters_data=chapters_data,
            dimensions=request.dimensions,
            analysis_depth=request.depth,
            global_outline=global_outline_content
        )

        if project is not None:
            project.global_outline_quality_report = quality_report
            await db.commit()

        return ResponseModel(
            success=True, data=quality_report, task_id=task_id
        )

    except Exception as e:
        logger.error(f"全局大纲质控失败: {e}", exc_info=True)
        return ResponseModel(
            success=False, message=f"质量检测失败: {str(e)}"
        )


# ==================== 单元质控 ====================

@router.post("/quality-control/unit/{project_id}/{unit_index}")
async def analyze_single_unit_quality(
    project_id: int,
    unit_index: int,
    request: Optional[UnitQualityControlRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """单单元质控检测"""
    try:
        from app.domain.services.quality_service import QualityControlService

        content = request.content if request else ""

        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == unit_index
        )
        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not content and chapter:
            content = chapter.final_content or chapter.draft_content or ""

        if not content:
            return ResponseModel(
                success=False, message=f"单元 {unit_index} 内容为空"
            )

        project_query = select(NovelProject).where(
            NovelProject.id == project_id
        )
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project:
            return ResponseModel(
                success=False, message="项目不存在"
            )

        chapters_data = [{
            "chapter_number": unit_index,
            "content": content,
            "summary": content[:500],
            "unit_summary": getattr(chapter, 'unit_summary', '') or ""
        }]

        qc_service = QualityControlService(db=db)
        dimensions = (
            request.dimensions if request and request.dimensions
            else QualityConstants.DEFAULT_DIMENSIONS
        )
        depth = request.depth if request else QualityConstants.DEFAULT_ANALYSIS_DEPTH

        qc_report = await qc_service.analyze_quality(
            user_id=current_user.id,
            project_id=project_id,
            chapters_data=chapters_data,
            dimensions=dimensions,
            analysis_depth=depth,
            global_outline=getattr(
                project, 'global_outline_content', '') or ""
        )

        issues = qc_report.get("issues", [])
        score = qc_report.get("overall_score", 0)

        # 自动修正
        auto_fix_applied = []
        if request and request.auto_fix and issues:
            issues_with_fixes = await _generate_fixes_for_issues(
                issues=issues, chapters_data=chapters_data,
                project=project, db=db, user_id=current_user.id
            )

            threshold = request.auto_fix_threshold
            for issue in issues_with_fixes:
                auto_fix = issue.get('auto_fix')
                if auto_fix and auto_fix.get('confidence', 0) >= threshold:
                    auto_fix_applied.append({
                        "issue_id": issue.get('id'),
                        "category": issue.get('category'),
                        "confidence": auto_fix.get('confidence'),
                    })

        return ResponseModel(
            success=True,
            data={
                "unit_index": unit_index,
                "score": score,
                "issues_count": len(issues),
                "fixed_count": len(auto_fix_applied),
                "issues": issues,
                "fixes_applied": auto_fix_applied,
                "report": qc_report
            }
        )

    except Exception as e:
        logger.error(f"单元质控失败: {e}", exc_info=True)
        return ResponseModel(
            success=False, message=f"质控检测失败: {str(e)}"
        )


# ==================== SSE实时推送 ====================

@router.get("/quality-control/global-outline/{task_id}/events")
async def subscribe_qc_progress(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """SSE端点: 订阅质控进度"""
    from app.infrastructure.sse_subscriber import (
        get_qc_subscriber, event_generator
    )

    subscriber = get_qc_subscriber()
    queue = subscriber.subscribe(task_id)

    return StreamingResponse(
        event_generator(task_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ==================== 取消/反馈 ====================

@router.post("/quality-control/cancel")
async def cancel_quality_control(
    request: CancelQCRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消质控检测"""
    from app.infrastructure.sse_subscriber import get_qc_subscriber

    subscriber = get_qc_subscriber()
    task_id_prefix = f"qc_{current_user.id}_"

    cancel_event = {
        "type": "cancelled",
        "timestamp": datetime.now().isoformat(),
        "project_id": request.project_id
    }

    for task_id in list(subscriber._subscribers.keys()):
        if task_id.startswith(task_id_prefix):
            await subscriber.publish(task_id, cancel_event)

    return ResponseModel(success=True, message="质控检测已取消")


@router.post("/quality-control/feedback")
async def submit_quality_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交质量检测反馈"""
    logger.info(
        f"用户 {current_user.id} 提交反馈: "
        f"issue={request.issue_id}, type={request.feedback_type}"
    )

    return ResponseModel(
        success=True,
        message="反馈已记录",
        data={
            "feedback_type": request.feedback_type,
            "issue_id": request.issue_id
        }
    )
''')


print("\n=== Phase 4: Quality control API created ===")


# ============================================================
# 15. 知识库API端点
# ============================================================
write_file("api/v1/endpoints/knowledge_base.py", '''"""知识库管理 API 端点

提供项目专属知识库构建、图谱查询、一致性检查等功能
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.models.project import NovelProject
from app.schemas.common import ResponseModel
from app.core.constants import KnowledgeBaseConstants
from app.core.exceptions import (
    ResourceNotFoundException, ValidationException, AppException,
    ErrorCode
)
from app.core.logger import get_logger

logger = get_logger("knowledge_base_api")
router = APIRouter()


@router.post("/projects/{project_id}/build-knowledge-base")
async def build_project_knowledge_base(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """构建项目专属知识库"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if not project.outline_content:
            raise ValidationException("项目没有大纲内容，无法构建知识库")

        if project.kb_status == KnowledgeBaseConstants.STATUS_BUILDING:
            raise ValidationException("知识库正在构建中，请稍后再试")

        project.kb_status = KnowledgeBaseConstants.STATUS_BUILDING
        project.kb_build_progress = {
            "stage": "initializing",
            "progress": 0,
            "message": "正在初始化知识库...",
            "started_at": datetime.now().isoformat()
        }
        await db.commit()

        background_tasks.add_task(
            _build_knowledge_base_task,
            project_id=project_id,
            outline_content=project.outline_content,
            graphrag_enabled=project.kb_graphrag_enabled
            if project.kb_graphrag_enabled is not None else True
        )

        return ResponseModel(
            success=True,
            message="知识库构建任务已启动",
            data={"project_id": project_id, "status": "building"}
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"启动知识库构建失败: {e}")
        return ResponseModel(
            success=False, message=f"启动失败: {str(e)}"
        )


async def _build_knowledge_base_task(
    project_id: int,
    outline_content: str,
    graphrag_enabled: bool
):
    """后台执行知识库构建"""
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
        try:
            query = select(NovelProject).where(
                NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                return

            project.kb_build_progress = {
                "stage": "extracting_entities",
                "progress": 30,
                "message": "正在提取实体和关系...",
            }
            await db.commit()

            # 向量存储构建
            from app.infrastructure.knowledge.vector_store import (
                ProjectVectorStore
            )
            vector_store = ProjectVectorStore()
            await vector_store.add_chapter(
                project_id=project_id,
                chapter_number=0,
                content=outline_content
            )

            # GraphRAG构建
            entity_count = 0
            relation_count = 0
            graph_path = None

            if graphrag_enabled:
                from app.infrastructure.knowledge.graph_rag import (
                    KnowledgeGraph
                )
                from app.core.config import get_settings
                settings = get_settings()
                graph_dir = settings.get_knowledge_graph_dir()
                os.makedirs(graph_dir, exist_ok=True)
                graph_path = os.path.join(
                    graph_dir, f"project_{project_id}_global.json")

                kg = KnowledgeGraph(persist_path=graph_path)
                kg.load()
                entity_count = kg.get_entity_count()
                relation_count = kg.get_relation_count()
                kg.save()

            collection_name = vector_store.get_collection_name(project_id)

            project.kb_status = KnowledgeBaseConstants.STATUS_READY
            project.project_kb_collection = collection_name
            project.kb_build_progress = {
                "stage": "completed",
                "progress": 100,
                "message": "知识库构建完成",
                "entity_count": entity_count,
                "relation_count": relation_count,
                "completed_at": datetime.now().isoformat()
            }
            await db.commit()

        except Exception as e:
            logger.error(f"知识库构建失败: {e}")
            try:
                query = select(NovelProject).where(
                    NovelProject.id == project_id)
                result = await db.execute(query)
                project = result.scalar_one_or_none()
                if project:
                    project.kb_status = KnowledgeBaseConstants.STATUS_FAILED
                    project.kb_build_progress = {
                        "stage": "failed",
                        "message": f"构建失败: {str(e)}"
                    }
                    await db.commit()
            except Exception as inner_e:
                logger.warning(f"更新知识库状态失败: {inner_e}")


@router.get("/projects/{project_id}/knowledge-base-status")
async def get_knowledge_base_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取项目知识库构建状态"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        from app.infrastructure.knowledge.vector_store import (
            ProjectVectorStore
        )
        from app.domain.services.knowledge_service import KnowledgeBaseService

        vector_store = ProjectVectorStore()
        stats = vector_store.get_stats(project_id)

        kb_service = KnowledgeBaseService()
        is_stale = kb_service.is_stale_build(
            project.kb_status or "pending",
            project.kb_build_progress or {},
            project.updated_at
        )

        return ResponseModel(
            success=True,
            data={
                "status": project.kb_status or "pending",
                "progress": project.kb_build_progress,
                "graphrag_enabled": project.kb_graphrag_enabled
                if project.kb_graphrag_enabled is not None else True,
                "collection_name": project.project_kb_collection,
                "stats": stats,
                "is_stale": is_stale
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取知识库状态失败: {e}")
        return ResponseModel(
            success=False, message=f"获取失败: {str(e)}"
        )


@router.get("/projects/{project_id}/knowledge-graph")
async def get_project_knowledge_graph(
    project_id: int,
    unit_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取项目知识图谱数据"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        from app.infrastructure.knowledge.graph_rag import KnowledgeGraph
        from app.core.config import get_settings

        settings = get_settings()
        graph_dir = settings.get_knowledge_graph_dir()
        graph_path = os.path.join(
            graph_dir, f"project_{project_id}_unit_{unit_number or 'global'}.json"
        )

        if not os.path.exists(graph_path):
            graph_path = os.path.join(
                graph_dir, f"project_{project_id}_global.json"
            )

        if not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={"nodes": [], "edges": [], "stats": {}}
            )

        kg = KnowledgeGraph(persist_path=graph_path)
        kg.load()

        return ResponseModel(
            success=True,
            data={
                "nodes": [],
                "edges": [],
                "stats": {
                    "node_count": kg.get_entity_count(),
                    "edge_count": kg.get_relation_count()
                }
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱失败: {e}")
        return ResponseModel(
            success=False, message=f"获取失败: {str(e)}"
        )


@router.delete("/projects/{project_id}/knowledge-base")
async def delete_project_knowledge_base(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除项目知识库"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        from app.infrastructure.knowledge.vector_store import (
            ProjectVectorStore
        )

        vector_store = ProjectVectorStore()
        await vector_store.delete_collection(project_id)

        project.kb_status = KnowledgeBaseConstants.STATUS_PENDING
        project.project_kb_collection = None
        project.kb_build_progress = None
        await db.commit()

        return ResponseModel(success=True, message="知识库已删除")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除知识库失败: {e}")
        return ResponseModel(
            success=False, message=f"删除失败: {str(e)}"
        )


@router.post("/projects/{project_id}/check-content-consistency")
async def check_content_consistency(
    project_id: int,
    content: str,
    unit_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """检查内容一致性"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if project.kb_status != KnowledgeBaseConstants.STATUS_READY:
            return ResponseModel(
                success=True,
                data={
                    "is_consistent": True,
                    "conflicts": [],
                    "suggestions": [],
                    "message": "知识库尚未构建，跳过一致性检查"
                }
            )

        # 获取一致性报告
        from app.infrastructure.knowledge.graph_rag import KnowledgeGraph
        from app.core.config import get_settings

        settings = get_settings()
        graph_dir = settings.get_knowledge_graph_dir()
        graph_path = os.path.join(
            graph_dir,
            f"project_{project_id}_unit_{unit_number or 'global'}.json"
        )

        if not os.path.exists(graph_path):
            graph_path = os.path.join(
                graph_dir, f"project_{project_id}_global.json"
            )

        consistency_report = {}
        if os.path.exists(graph_path):
            kg = KnowledgeGraph(persist_path=graph_path)
            kg.load()
            consistency_report = kg.get_consistency_report(unit_number)

        from app.domain.services.knowledge_service import KnowledgeBaseService
        kb_service = KnowledgeBaseService()
        result = kb_service.check_content_consistency(
            content=content,
            consistency_report=consistency_report
        )

        return ResponseModel(success=True, data=result)

    except AppException:
        raise
    except Exception as e:
        logger.error(f"一致性检查失败: {e}")
        return ResponseModel(
            success=False, message=f"检查失败: {str(e)}"
        )
''')


print("\n=== Phase 5: Knowledge base API created ===")


# ============================================================
# 16. 风格文档API端点
# ============================================================
write_file("api/v1/endpoints/style.py", '''"""风格文档管理 API 端点

提供风格文档上传、分析、获取、删除等功能
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.models.project import NovelProject
from app.schemas.common import ResponseModel
from app.schemas.style import StyleDocumentUpdate
from app.core.constants import StyleConstants
from app.core.exceptions import (
    ResourceNotFoundException, ValidationException,
    AppException, ErrorCode
)
from app.core.logger import get_logger

logger = get_logger("style_api")
router = APIRouter()


@router.post("/projects/{project_id}/style-document")
async def upload_style_document(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传风格文档"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if not file.filename:
            raise ValidationException("文件名不能为空")

        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in StyleConstants.ALLOWED_EXTENSIONS:
            raise ValidationException(
                f"不支持的文件格式，仅支持: "
                f"{', '.join(StyleConstants.ALLOWED_EXTENSIONS)}"
            )

        content = await file.read()

        if file_ext in ('.txt', '.md'):
            style_content = content.decode('utf-8', errors='ignore')
        elif file_ext == '.docx':
            try:
                import docx
                import tempfile
                with tempfile.NamedTemporaryFile(
                    suffix='.docx', delete=False
                ) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                doc = docx.Document(tmp_path)
                style_content = '\\n'.join(
                    [para.text for para in doc.paragraphs])
                os.unlink(tmp_path)
            except ImportError:
                raise ValidationException(
                    "服务器未安装python-docx库，无法解析docx文件"
                )
        elif file_ext == '.pdf':
            try:
                import fitz
                import tempfile
                with tempfile.NamedTemporaryFile(
                    suffix='.pdf', delete=False
                ) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                doc = fitz.open(tmp_path)
                style_content = ''
                for page in doc:
                    style_content += page.get_text()
                doc.close()
                os.unlink(tmp_path)
            except ImportError:
                raise ValidationException(
                    "服务器未安装pymupdf库，无法解析pdf文件"
                )
        else:
            style_content = content.decode('utf-8', errors='ignore')

        if len(style_content.strip()) < StyleConstants.MIN_STYLE_CONTENT_LENGTH:
            raise ValidationException("风格文档内容过短")

        if len(style_content) > StyleConstants.MAX_STYLE_CONTENT_LENGTH:
            style_content = style_content[:StyleConstants.MAX_STYLE_CONTENT_LENGTH]

        project.style_document_name = file.filename
        project.style_analysis_status = "pending"
        await db.commit()

        logger.info(
            f"风格文档上传成功: project_id={project_id}, "
            f"file={file.filename}"
        )

        return ResponseModel(
            success=True,
            data={
                "project_id": project_id,
                "style_document_name": file.filename,
                "style_document_uploaded": True,
                "style_analysis_status": "pending",
                "message": "风格文档上传成功"
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"上传风格文档失败: {e}")
        return ResponseModel(
            success=False, message=f"上传失败: {str(e)}"
        )


@router.get("/projects/{project_id}/style-document")
async def get_style_document(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取风格文档信息"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        style_config = project.style_config or {}

        return ResponseModel(
            success=True,
            data={
                "project_id": project_id,
                "style_document_uploaded": bool(project.style_document_path),
                "style_document_name": project.style_document_name,
                "style_profile": style_config.get("style_profile"),
                "style_guide_for_writing": style_config.get(
                    "style_guide_for_writing"),
                "key_imitation_points": style_config.get(
                    "key_imitation_points"),
                "avoid_patterns": style_config.get("avoid_patterns"),
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取风格文档失败: {e}")
        return ResponseModel(
            success=False, message=f"获取失败: {str(e)}"
        )


@router.delete("/projects/{project_id}/style-document")
async def delete_style_document(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除风格文档"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        project.style_document_path = None
        project.style_document_name = None
        project.style_config = None
        await db.commit()

        return ResponseModel(success=True, message="风格文档已删除")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除风格文档失败: {e}")
        return ResponseModel(
            success=False, message=f"删除失败: {str(e)}"
        )


@router.put("/projects/{project_id}/style-document")
async def update_style_document_settings(
    project_id: int,
    request: StyleDocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新风格文档设置"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if request.ai_elimination_enabled is not None:
            project.ai_elimination_enabled = request.ai_elimination_enabled
        if request.ai_elimination_threshold is not None:
            project.ai_elimination_threshold = request.ai_elimination_threshold

        await db.commit()

        return ResponseModel(
            success=True,
            data={
                "project_id": project_id,
                "ai_elimination_enabled": project.ai_elimination_enabled,
                "ai_elimination_threshold": project.ai_elimination_threshold
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新风格文档设置失败: {e}")
        return ResponseModel(
            success=False, message=f"更新失败: {str(e)}"
        )


@router.get("/style-library")
async def get_style_library(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """获取文风知识库"""
    return ResponseModel(
        success=True,
        data={
            "categories": ["traditional", "personal", "web_novel"],
            "styles": [],
            "total": 0
        }
    )


@router.post("/style-library/blend")
async def blend_styles(
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """融合多个文风"""
    style_ids = request.get("style_ids", [])
    intensity = float(request.get(
        "intensity", StyleConstants.DEFAULT_BLEND_INTENSITY))

    if not style_ids:
        raise ValidationException("style_ids 不能为空")
    if len(style_ids) > StyleConstants.MAX_BLEND_STYLES:
        raise ValidationException(
            f"最多支持{StyleConstants.MAX_BLEND_STYLES}种文风融合")
    if not (StyleConstants.MIN_BLEND_INTENSITY <= intensity
            <= StyleConstants.MAX_BLEND_INTENSITY):
        raise ValidationException("intensity 必须在 0.0 到 1.0 之间")

    return ResponseModel(
        success=True,
        data={"style_guide": {}, "formatted_prompt": ""}
    )
''')


# ============================================================
# 17. WebSocket API端点
# ============================================================
write_file("api/v1/endpoints/websocket.py", '''"""WebSocket API 端点

提供实时进度推送的WebSocket连接
"""
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from app.core.constants import WebSocketConstants
from app.core.logger import get_logger

logger = get_logger("websocket_api")
router = APIRouter()


@router.websocket("/ws/{channel}")
async def websocket_endpoint(
    websocket: WebSocket,
    channel: str,
    project_id: Optional[int] = None
):
    """WebSocket连接端点

    频道:
    - task_progress: 任务进度推送
    - qc_progress: 质控进度推送
    - generation: 生成进度推送
    - system: 系统通知
    """
    from app.infrastructure.websocket_manager import get_ws_manager

    manager = get_ws_manager()

    await manager.connect(websocket, channel, project_id)

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(
                f"[WS] 收到消息: channel={channel}, data={data[:100]}"
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"[WS] 客户端断开: channel={channel}")
    except Exception as e:
        logger.warning(f"[WS] 连接异常: {e}")
        manager.disconnect(websocket)
''')


print("\n=== Phase 6: Style and WebSocket API created ===")
print("\n=== All T13 files created! ===")
