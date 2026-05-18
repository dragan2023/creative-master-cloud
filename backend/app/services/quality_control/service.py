# -*- coding: utf-8 -*-
"""
AI辅助长篇写作质量管控服务模块 - 服务层

基于六维度质量管控体系:
1. 宏观结构层 - 情节节奏、伏笔回收、卷末情绪
2. 人物塑造层 - 角色一致性、台词指纹、配角活跃度
3. 场景与感官层 - 五感平衡、时空跳跃、动作逻辑
4. 文笔与修辞层 - 高频词疲劳、陈词滥调、被动语态
5. 阅读体验层 - 章末悬念、金句密度、段落舒适度
6. 技术性排雷层 - 视角越界、时代穿帮、合规检查
"""
import asyncio
import hashlib
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logger import get_logger
from app.models import QualityReport as QualityReportModel, AnalysisScope, AnalysisStatus, NovelProject, NovelChapter  # noqa: N812
from app.agents.llm_manager import get_llm_manager

logger = get_logger("quality_control")


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
    """质量报告"""
    project_id: int
    analysis_scope: str
    chapters_analyzed: List[int]
    dimensions: List[str]
    overall_score: float
    dimension_scores: Dict[str, float]
    issues: List[QualityIssue]
    statistics: Dict = field(default_factory=dict)
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "project_id": self.project_id,
            "analysis_scope": self.analysis_scope,
            "chapters_analyzed": self.chapters_analyzed,
            "dimensions": self.dimensions,
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "issues": [issue.to_dict() for issue in self.issues],
            "statistics": self.statistics,
            "generated_at": self.generated_at
        }


class QualityControlService:
    """
    质量管控服务

    协调六维度分析器,执行质量分析任务
    支持分层分析、智能缓存、批量处理等优化策略
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_manager = get_llm_manager()

        # 分析器实例(延迟初始化)
        self._rule_engine = None
        self._llm_engine = None
        self._analyzers = {}

    def _get_rule_engine(self):
        """获取规则引擎(懒加载)"""
        if self._rule_engine is None:
            from app.services.quality_control.engines.rule_based_engine import RuleBasedEngine
            self._rule_engine = RuleBasedEngine()
        return self._rule_engine

    def _get_llm_engine(self):
        """获取LLM引擎(懒加载)"""
        if self._llm_engine is None:
            from app.services.quality_control.engines.llm_engine import LLMAnalysisEngine
            self._llm_engine = LLMAnalysisEngine(self.llm_manager)
        return self._llm_engine

    def _get_analyzer(self, dimension: str):
        """获取指定维度的分析器(懒加载)"""
        if dimension not in self._analyzers:
            analyzer_map = {
                "structure": "app.services.quality_control.analyzers.structure_analyzer:StructureAnalyzer",
                "character": "app.services.quality_control.analyzers.character_analyzer:CharacterAnalyzer",
                "scene": "app.services.quality_control.analyzers.scene_analyzer:SceneAnalyzer",
                "prose": "app.services.quality_control.analyzers.prose_analyzer:ProseAnalyzer",
                "experience": "app.services.quality_control.analyzers.experience_analyzer:ExperienceAnalyzer",
                "technical": "app.services.quality_control.analyzers.technical_analyzer:TechnicalAnalyzer",
                # 剧集/电影专项维度（映射到现有分析器）
                "script_format": "app.services.quality_control.analyzers.technical_analyzer:TechnicalAnalyzer",
                "visual_quality": "app.services.quality_control.analyzers.scene_analyzer:SceneAnalyzer",
                "unit_structure": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitStructureAnalyzer",
                "unit_character": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitCharacterAnalyzer",
                "unit_consistency": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitConsistencyAnalyzer",
                "unit_timeline_space": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitTimelineSpaceAnalyzer",
                "unit_ooc": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitOOCAnalyzer",
                "character_state": "app.services.quality_control.analyzers.unit_quality_analyzer:CharacterStateChangeAnalyzer",
                "worldview_consistency": "app.services.quality_control.analyzers.unit_quality_analyzer:WorldviewConsistencyAnalyzer",
                "timeline_consistency": "app.services.quality_control.analyzers.unit_quality_analyzer:TimelineConsistencyAnalyzer",
                "global_structure": "app.services.quality_control.analyzers.global_quality_analyzer:GlobalStructureAnalyzer",
                "global_character_worldview": "app.services.quality_control.analyzers.global_quality_analyzer:GlobalCharacterWorldviewAnalyzer",
                "global_plot_consistency": "app.services.quality_control.analyzers.global_quality_analyzer:GlobalPlotConsistencyAnalyzer",
                "global_storyline_integrity": "app.services.quality_control.analyzers.global_quality_analyzer:GlobalStorylineIntegrityAnalyzer",
            }

            if dimension not in analyzer_map:
                raise ValueError(f"不支持的分析维度: {dimension}")

            module_path, class_name = analyzer_map[dimension].split(":")
            import importlib
            module = importlib.import_module(module_path)
            analyzer_class = getattr(module, class_name)
            self._analyzers[dimension] = analyzer_class()

        return self._analyzers[dimension]

    def _compute_content_hash(self, chapters_data: List[Dict]) -> str:
        """计算章节内容哈希(用于缓存)"""
        content_str = json.dumps([
            {"id": ch["id"], "content": ch.get("content", "")[:1000]}
            for ch in chapters_data
        ], ensure_ascii=False)
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

    async def _check_cache(self, project_id: int, content_hash: str, dimensions: List[str]) -> Optional[Dict]:
        """检查缓存"""
        try:
            cache_key = f"quality:{project_id}:{content_hash}:{','.join(sorted(dimensions))}"
            query = select(QualityReportModel).where(
                QualityReportModel.project_id == project_id,
                QualityReportModel.content_hash == content_hash,
                QualityReportModel.dimensions == json.dumps(sorted(dimensions), ensure_ascii=False),
                QualityReportModel.status == AnalysisStatus.COMPLETED
            ).order_by(QualityReportModel.created_at.desc()).limit(1)

            result = await self.db.execute(query)
            cached_report = result.scalar_one_or_none()

            if cached_report:
                logger.info(f"缓存命中: report_id={cached_report.id}")
                return {"report": cached_report.report_data, "is_cached": True, "report_id": cached_report.id}
        except Exception as e:
            logger.warning(f"缓存检查失败: {e}")
        return None

    async def _save_report(self, report_data: Dict, user_id: int, project_id: int,
                           analysis_scope: str, dimensions: List[str],
                           content_hash: str, statistics: Dict) -> int:
        """保存分析报告到数据库"""
        try:
            issues = report_data.get("issues", [])
            critical_count = sum(1 for issue in issues if issue.get("severity") == "critical")
            warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
            info_count = sum(1 for issue in issues if issue.get("severity") == "info")

            db_report = QualityReportModel(
                user_id=user_id,
                project_id=project_id,
                analysis_scope=AnalysisScope(analysis_scope),
                chapters_analyzed=report_data.get("chapters_analyzed", []),
                dimensions=dimensions,
                analysis_depth=statistics.get("depth", "standard"),
                overall_score=report_data.get("overall_score"),
                dimension_scores=report_data.get("dimension_scores"),
                report_data=report_data,
                total_issues=len(issues),
                critical_issues=critical_count,
                warning_issues=warning_count,
                info_issues=info_count,
                total_tokens=statistics.get("total_tokens", 0),
                rule_engine_tokens=statistics.get("rule_engine_tokens", 0),
                llm_tokens=statistics.get("llm_tokens", 0),
                status=AnalysisStatus.COMPLETED,
                content_hash=content_hash,
                cache_key=f"quality:{project_id}:{content_hash}",
                is_cached=False,
                started_at=statistics.get("started_at"),
                completed_at=statistics.get("completed_at"),
                duration_ms=statistics.get("duration_ms", 0)
            )
            self.db.add(db_report)
            await self.db.commit()
            await self.db.refresh(db_report)
            logger.info(f"报告保存成功: report_id={db_report.id}")
            return db_report.id
        except Exception as e:
            logger.error(f"保存报告失败: {e}")
            await self.db.rollback()
            raise

    async def analyze(self, user_id: int, project_id: int,
                      chapter_ids: Optional[List[int]] = None,
                      dimensions: Optional[List[str]] = None,
                      analysis_depth: str = "standard") -> Dict:
        """执行质量分析"""
        start_time = time.time()

        if not dimensions:
            dimensions = ["structure", "character", "scene", "prose", "experience", "technical"]

        logger.info(f"开始质量分析: project={project_id}, depth={analysis_depth}, dimensions={dimensions}")

        try:
            project, chapters_data = await self._load_project_data(project_id, chapter_ids)
            if not chapters_data:
                raise ValueError("没有找到可分析的章节内容")

            if analysis_depth != "quick":
                content_hash = self._compute_content_hash(chapters_data)
                cached = await self._check_cache(project_id, content_hash, dimensions)
                if cached:
                    logger.info("使用缓存结果")
                    cached["is_cached"] = True
                    return cached["report"]

            report = await self._execute_analysis(
                chapters_data=chapters_data, project=project,
                dimensions=dimensions, depth=analysis_depth, user_id=user_id
            )

            duration_ms = int((time.time() - start_time) * 1000)
            statistics = {
                "depth": analysis_depth,
                "started_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "duration_ms": duration_ms,
                "total_tokens": report.get("statistics", {}).get("total_tokens", 0),
                "rule_engine_tokens": report.get("statistics", {}).get("rule_engine_tokens", 0),
                "llm_tokens": report.get("statistics", {}).get("llm_tokens", 0)
            }
            content_hash = self._compute_content_hash(chapters_data)
            report_id = await self._save_report(
                report_data=report, user_id=user_id, project_id=project_id,
                analysis_scope="multi_chapter" if len(chapters_data) > 1 else "single_chapter",
                dimensions=dimensions, content_hash=content_hash, statistics=statistics
            )
            report["report_id"] = report_id
            report["statistics"].update(statistics)
            logger.info(f"质量分析完成: duration={duration_ms}ms, tokens={statistics['total_tokens']}")
            return report
        except Exception as e:
            logger.error(f"质量分析失败: {e}", exc_info=True)
            raise

    async def _load_project_data(self, project_id: int, chapter_ids: Optional[List[int]] = None):
        """加载项目和章节数据"""
        query = select(NovelProject).where(NovelProject.id == project_id)
        result = await self.db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.status == "completed"
        )
        if chapter_ids:
            query = query.where(NovelChapter.id.in_(chapter_ids))
        query = query.order_by(NovelChapter.chapter_number)
        result = await self.db.execute(query)
        chapters = result.scalars().all()

        chapters_data = []
        for chapter in chapters:
            content = chapter.final_content or chapter.draft_content or ""
            if content.strip():
                chapters_data.append({
                    "id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.chapter_title,
                    "content": content,
                    "word_count": len(content),
                    "metadata": chapter.chapter_metadata or {}
                })
        return project, chapters_data

    async def _execute_analysis(self, chapters_data: List[Dict], project: Any,
                                 dimensions: List[str], depth: str, user_id: int = 0) -> Dict:
        """执行分析任务"""
        rule_engine = self._get_rule_engine()
        rule_results = await rule_engine.analyze_all(chapters_data, dimensions)

        if depth == "quick":
            return self._build_report_from_rules(rule_results, chapters_data)

        # 构建维度→LLM任务映射，仅对需要LLM的维度创建任务
        # v3.1：扩展为全八维度，增加剧集/电影专项维度
        llm_dimensions = ["structure", "character", "scene", "prose", "experience", "technical",
                          "script_format", "visual_quality"]
        llm_task_map: Dict[str, Any] = {}
        for dimension in dimensions:
            if dimension in llm_dimensions:
                analyzer = self._get_analyzer(dimension)
                llm_task_map[dimension] = analyzer.analyze(
                    chapters_data=chapters_data, project=project,
                    rule_results=rule_results.get(dimension, {}),
                    depth=depth, db=self.db, user_id=user_id
                )

        # 从规则引擎收集初始结果
        all_issues = []
        dimension_scores = {}
        for dimension, results in rule_results.items():
            if "issues" in results:
                all_issues.extend(results["issues"])
            if "score" in results:
                dimension_scores[dimension] = results["score"]

        # 并发执行所有LLM任务，通过键名对齐结果
        raw_results = []
        if llm_task_map:
            task_keys = list(llm_task_map.keys())
            task_coros = list(llm_task_map.values())
            raw_results = await asyncio.gather(*task_coros, return_exceptions=True)
            for key, result in zip(task_keys, raw_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"[LLM分析] 维度 '{key}' 失败: {type(result).__name__}: {result}"
                    )
                    continue
                if "issues" in result:
                    all_issues.extend(result["issues"])
                if "score" in result:
                    dimension_scores[key] = result["score"]

        overall_score = sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0

        return {
            "project_id": project.id,
            "analysis_scope": "multi_chapter" if len(chapters_data) > 1 else "single_chapter",
            "chapters_analyzed": [ch["id"] for ch in chapters_data],
            "dimensions": dimensions,
            "overall_score": round(overall_score, 2),
            "dimension_scores": dimension_scores,
            "issues": all_issues,
            "statistics": {
                "total_tokens": sum(r.get("tokens", 0) for r in raw_results if not isinstance(r, Exception)),
                "rule_engine_tokens": 0,
                "llm_tokens": sum(r.get("tokens", 0) for r in raw_results if not isinstance(r, Exception))
            }
        }

    async def analyze_content_with_context(
        self,
        chapters_data: List[Dict],
        project: Any,
        dimensions: List[str],
        depth: str,
        user_id: int,
        qc_context: Dict[str, str] = None
    ) -> Dict:
        """
        正文质控专用分析 — 接收综合信息上下文进行六维度深度检测

        与现有的 analyze() 方法区别：
        - analyze() 是通用入口，用于单元概述质控等场景
        - analyze_content_with_context() 是正文质控专用，整合了知识图谱、
          人物设定、前文摘要、一致性报告等综合信息上下文

        Args:
            chapters_data: 章节数据列表
            project: 项目对象
            dimensions: 分析维度（正文六维度）
            depth: 分析深度
            user_id: 用户ID
            qc_context: 综合信息上下文（由ContentQCContextAggregator生成）

        Returns:
            质控报告字典
        """
        start_time = __import__('time').time()
        logger.info(
            f"[正文质控-六维度] 开始深度分析: dimensions={dimensions}, "
            f"depth={depth}, 上下文提供={list(qc_context.keys()) if qc_context else '无'}"
        )

        # 使用相同的核心分析引擎
        # TODO(Phase2): 将 qc_context 各信息源注入 _execute_analysis 内各维度分析器的 prompt，
        #   使 LLM 能在六维度检测时参考知识图谱、人物设定、前文摘要、一致性报告等综合上下文，
        #   当前仅将 qc_context 附加到报告供前端展示，尚未影响分析过程。
        report = await self._execute_analysis(
            chapters_data=chapters_data,
            project=project,
            dimensions=dimensions,
            depth=depth,
            user_id=user_id
        )

        # 将综合信息上下文注入报告（供前端展示和后续修正参考）
        report["qc_context"] = qc_context or {}
        report["context_summary"] = self._build_context_summary(qc_context)

        duration_ms = int((__import__('time').time() - start_time) * 1000)
        report["duration_ms"] = duration_ms

        logger.info(
            f"[正文质控-六维度] 分析完成: duration={duration_ms}ms, "
            f"score={report.get('overall_score')}, issues={len(report.get('issues', []))}"
        )
        return report

    @staticmethod
    def _build_context_summary(qc_context: Dict[str, str]) -> str:
        """构建上下文摘要（用于质控报告）"""
        if not qc_context:
            return ""

        parts = []
        labels = {
            "knowledge_graph_context": "知识图谱",
            "character_context": "人物设定",
            "previous_content_summary": "前文信息",
            "consistency_context": "一致性报告",
            "timeline_spatial_context": "时间空间",
            "ooc_constraints": "OOC约束"
        }
        for key, label in labels.items():
            if qc_context.get(key):
                parts.append(f"{label}: 已加载 ({len(qc_context[key])}字符)")
        return "; ".join(parts) if parts else "无综合上下文"

    def _build_report_from_rules(self, rule_results: Dict, chapters_data: List[Dict]) -> Dict:
        """仅从规则引擎结果构建报告"""
        all_issues = []
        dimension_scores = {}
        for dimension, results in rule_results.items():
            if "issues" in results:
                all_issues.extend(results["issues"])
            if "score" in results:
                dimension_scores[dimension] = results["score"]

        overall_score = sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0
        return {
            "project_id": 0,
            "analysis_scope": "multi_chapter" if len(chapters_data) > 1 else "single_chapter",
            "chapters_analyzed": [ch["id"] for ch in chapters_data],
            "dimensions": list(rule_results.keys()),
            "overall_score": round(overall_score, 2),
            "dimension_scores": dimension_scores,
            "issues": all_issues,
            "statistics": {"total_tokens": 0, "rule_engine_tokens": 0, "llm_tokens": 0}
        }
