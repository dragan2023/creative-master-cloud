"""
AI辅助长篇写作质量管控服务模块

基于六维度质量管控体系:
1. 宏观结构层 - 情节节奏、伏笔回收、卷末情绪
2. 人物塑造层 - 角色一致性、台词指纹、配角活跃度
3. 场景与感官层 - 五感平衡、时空跳跃、动作逻辑
4. 文笔与修辞层 - 高频词疲劳、陈词滥调、被动语态
5. 阅读体验层 - 章末悬念、金句密度、段落舒适度
6. 技术性排雷层 - 视角越界、时代穿帮、合规检查

效率优化策略:
- 分层分析: 规则引擎(0 Token) → 轻量LLM → 深度LLM
- 智能缓存: 内容哈希缓存,避免重复分析
- 按需分析: 快速/标准/深度三档
- 批量处理: 减少API调用次数
- 并行执行: 六维度独立分析

@date: 2026-04-12
@version: v3.1.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
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
from app.models import QualityReport, AnalysisScope, AnalysisStatus, NovelProject, NovelChapter
from app.agents.llm_manager import get_llm_manager

logger = get_logger("quality_control")


# ==================== 数据模型 ====================

@dataclass
class QualityIssue:
    """质量问题"""
    id: str                          # 问题ID (如 V007, OOC-042)
    # 维度 (structure/character/scene/prose/experience/technical)
    dimension: str
    category: str                    # 分类 (如 伏笔回收/台词指纹/感官平衡)
    severity: str                    # 严重程度 (critical/warning/info)
    location: Dict                   # 位置信息 {chapter, paragraph, line}
    description: str                 # 问题描述
    evidence: str                    # 原文证据
    suggestion: str                  # 修改建议
    metadata: Dict = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class QualityReport:
    """质量报告"""
    project_id: int
    analysis_scope: str              # single_chapter / multi_chapter / full_book
    chapters_analyzed: List[int]
    dimensions: List[str]
    overall_score: float             # 综合评分 0-100
    dimension_scores: Dict[str, float]  # 各维度得分
    issues: List[QualityIssue]
    statistics: Dict = field(default_factory=dict)  # 统计数据
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


# ==================== 主服务类 ====================

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
                # 原有六维度(正文质控)
                "structure": "app.services.quality_control.analyzers.structure_analyzer:StructureAnalyzer",
                "character": "app.services.quality_control.analyzers.character_analyzer:CharacterAnalyzer",
                "scene": "app.services.quality_control.analyzers.scene_analyzer:SceneAnalyzer",
                "prose": "app.services.quality_control.analyzers.prose_analyzer:ProseAnalyzer",
                "experience": "app.services.quality_control.analyzers.experience_analyzer:ExperienceAnalyzer",
                "technical": "app.services.quality_control.analyzers.technical_analyzer:TechnicalAnalyzer",

                # 单元概述五维度
                "unit_structure": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitStructureAnalyzer",
                "unit_character": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitCharacterAnalyzer",
                "unit_consistency": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitConsistencyAnalyzer",
                "unit_timeline_space": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitTimelineSpaceAnalyzer",
                "unit_ooc": "app.services.quality_control.analyzers.unit_quality_analyzer:UnitOOCAnalyzer",

                # 新增：三个深度检测维度
                "character_state": "app.services.quality_control.analyzers.unit_quality_analyzer:CharacterStateChangeAnalyzer",
                "worldview_consistency": "app.services.quality_control.analyzers.unit_quality_analyzer:WorldviewConsistencyAnalyzer",
                "timeline_consistency": "app.services.quality_control.analyzers.unit_quality_analyzer:TimelineConsistencyAnalyzer",

                # 新增:全局大纲四维度
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
            {"id": ch["id"], "content": ch.get(
                "content", "")[:1000]}  # 仅取前1000字
            for ch in chapters_data
        ], ensure_ascii=False)
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

    async def _check_cache(self, project_id: int, content_hash: str, dimensions: List[str]) -> Optional[Dict]:
        """检查缓存"""
        try:
            cache_key = f"quality:{project_id}:{content_hash}:{','.join(sorted(dimensions))}"

            # 查询数据库中的缓存报告
            query = select(QualityReport).where(
                QualityReport.project_id == project_id,
                QualityReport.content_hash == content_hash,
                QualityReport.dimensions == json.dumps(
                    dimensions, ensure_ascii=False),
                QualityReport.status == AnalysisStatus.COMPLETED
            ).order_by(QualityReport.created_at.desc()).limit(1)

            result = await self.db.execute(query)
            cached_report = result.scalar_one_or_none()

            if cached_report:
                logger.info(f"缓存命中: report_id={cached_report.id}")
                return {
                    "report": cached_report.report_data,
                    "is_cached": True,
                    "report_id": cached_report.id
                }
        except Exception as e:
            logger.warning(f"缓存检查失败: {e}")

        return None

    async def _save_report(self, report_data: Dict, user_id: int, project_id: int,
                           analysis_scope: str, dimensions: List[str],
                           content_hash: str, statistics: Dict) -> int:
        """保存分析报告到数据库"""
        try:
            # 统计问题数量
            issues = report_data.get("issues", [])
            critical_count = sum(
                1 for issue in issues if issue.get("severity") == "critical")
            warning_count = sum(
                1 for issue in issues if issue.get("severity") == "warning")
            info_count = sum(
                1 for issue in issues if issue.get("severity") == "info")

            db_report = QualityReport(
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

    async def analyze(
        self,
        user_id: int,
        project_id: int,
        chapter_ids: Optional[List[int]] = None,
        dimensions: Optional[List[str]] = None,
        analysis_depth: str = "standard"
    ) -> Dict:
        """
        执行质量分析

        Args:
            user_id: 用户ID
            project_id: 项目ID
            chapter_ids: 章节ID列表(None表示全部)
            dimensions: 分析维度列表(None表示全部)
            analysis_depth: 分析深度(quick/standard/deep)

        Returns:
            分析报告字典
        """
        start_time = time.time()

        # 默认维度
        if not dimensions:
            dimensions = ["structure", "character",
                          "scene", "prose", "experience", "technical"]

        logger.info(
            f"开始质量分析: project={project_id}, depth={analysis_depth}, dimensions={dimensions}")

        try:
            # 1. 获取项目和章节数据
            project, chapters_data = await self._load_project_data(project_id, chapter_ids)

            if not chapters_data:
                raise ValueError("没有找到可分析的章节内容")

            # 2. 检查缓存(仅standard和deep模式)
            if analysis_depth != "quick":
                content_hash = self._compute_content_hash(chapters_data)
                cached = await self._check_cache(project_id, content_hash, dimensions)
                if cached:
                    logger.info("使用缓存结果")
                    cached["is_cached"] = True
                    return cached["report"]

            # 3. 执行分析
            report = await self._execute_analysis(
                chapters_data=chapters_data,
                project=project,
                dimensions=dimensions,
                depth=analysis_depth,
                user_id=user_id  # ✅ 传递user_id
            )

            # 4. 计算统计信息
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

            # 5. 保存到数据库
            content_hash = self._compute_content_hash(chapters_data)
            report_id = await self._save_report(
                report_data=report,
                user_id=user_id,
                project_id=project_id,
                analysis_scope="multi_chapter" if len(
                    chapters_data) > 1 else "single_chapter",
                dimensions=dimensions,
                content_hash=content_hash,
                statistics=statistics
            )

            report["report_id"] = report_id
            report["statistics"].update(statistics)

            logger.info(
                f"质量分析完成: duration={duration_ms}ms, tokens={statistics['total_tokens']}")
            return report

        except Exception as e:
            logger.error(f"质量分析失败: {e}", exc_info=True)
            raise

    async def _load_project_data(self, project_id: int, chapter_ids: Optional[List[int]] = None):
        """加载项目和章节数据"""
        # 获取项目
        query = select(NovelProject).where(NovelProject.id == project_id)
        result = await self.db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 获取章节
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.status == "completed"  # 仅分析已完成的章节
        )

        if chapter_ids:
            query = query.where(NovelChapter.id.in_(chapter_ids))

        query = query.order_by(NovelChapter.chapter_number)
        result = await self.db.execute(query)
        chapters = result.scalars().all()

        # 提取章节数据
        chapters_data = []
        for chapter in chapters:
            content = chapter.final_content or chapter.draft_content or ""
            if content.strip():  # 仅包含有内容的章节
                chapters_data.append({
                    "id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.chapter_title,
                    "content": content,
                    "word_count": len(content),
                    "metadata": chapter.chapter_metadata or {}
                })

        return project, chapters_data

    async def _execute_analysis(
        self,
        chapters_data: List[Dict],
        project: Any,
        dimensions: List[str],
        depth: str,
        user_id: int = 0
    ) -> Dict:
        """执行分析任务"""

        # 第一层: 规则引擎分析(零Token)
        rule_engine = self._get_rule_engine()
        rule_results = await rule_engine.analyze_all(chapters_data, dimensions)

        # 如果仅快速模式,直接返回规则引擎结果
        if depth == "quick":
            return self._build_report_from_rules(rule_results, chapters_data)

        # 第二层和第三层: LLM分析(按需触发)
        llm_tasks = []
        for dimension in dimensions:
            if dimension in ["structure", "character", "experience"]:  # 需要LLM的维度
                analyzer = self._get_analyzer(dimension)
                llm_tasks.append(analyzer.analyze(
                    chapters_data=chapters_data,
                    project=project,
                    rule_results=rule_results.get(dimension, {}),
                    depth=depth,
                    db=self.db,
                    user_id=user_id  # ✅ 使用实际的user_id
                ))
            else:
                llm_tasks.append(None)  # 仅规则引擎的维度

        # 并行执行LLM分析
        llm_results = await asyncio.gather(*[task for task in llm_tasks if task], return_exceptions=True)

        # 合并结果
        all_issues = []
        dimension_scores = {}

        # 合并规则引擎结果
        for dimension, results in rule_results.items():
            if "issues" in results:
                all_issues.extend(results["issues"])
            if "score" in results:
                dimension_scores[dimension] = results["score"]

        # 合并LLM分析结果
        llm_idx = 0
        for i, dimension in enumerate(dimensions):
            if llm_tasks[i] is not None:
                if llm_idx < len(llm_results) and not isinstance(llm_results[llm_idx], Exception):
                    result = llm_results[llm_idx]
                    if "issues" in result:
                        all_issues.extend(result["issues"])
                    if "score" in result:
                        dimension_scores[dimension] = result["score"]
                llm_idx += 1

        # 计算综合评分
        overall_score = sum(dimension_scores.values()) / \
            len(dimension_scores) if dimension_scores else 0

        # 构建报告
        report = {
            "project_id": project.id,
            "analysis_scope": "multi_chapter" if len(chapters_data) > 1 else "single_chapter",
            "chapters_analyzed": [ch["id"] for ch in chapters_data],
            "dimensions": dimensions,
            "overall_score": round(overall_score, 2),
            "dimension_scores": dimension_scores,
            "issues": all_issues,
            "statistics": {
                "total_tokens": sum(r.get("tokens", 0) for r in llm_results if not isinstance(r, Exception)),
                "rule_engine_tokens": 0,
                "llm_tokens": sum(r.get("tokens", 0) for r in llm_results if not isinstance(r, Exception))
            }
        }

        return report

    def _build_report_from_rules(self, rule_results: Dict, chapters_data: List[Dict]) -> Dict:
        """仅从规则引擎结果构建报告"""
        all_issues = []
        dimension_scores = {}

        for dimension, results in rule_results.items():
            if "issues" in results:
                all_issues.extend(results["issues"])
            if "score" in results:
                dimension_scores[dimension] = results["score"]

        overall_score = sum(dimension_scores.values()) / \
            len(dimension_scores) if dimension_scores else 0

        return {
            "project_id": 0,
            "analysis_scope": "multi_chapter" if len(chapters_data) > 1 else "single_chapter",
            "chapters_analyzed": [ch["id"] for ch in chapters_data],
            "dimensions": list(rule_results.keys()),
            "overall_score": round(overall_score, 2),
            "dimension_scores": dimension_scores,
            "issues": all_issues,
            "statistics": {
                "total_tokens": 0,
                "rule_engine_tokens": 0,
                "llm_tokens": 0
            }
        }


# ==================== 服务工厂 ====================

def get_quality_control_service(db: AsyncSession) -> QualityControlService:
    """获取质量管控服务实例"""
    return QualityControlService(db)
