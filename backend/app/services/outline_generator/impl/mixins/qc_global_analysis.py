"""大纲生成器 - 全局大纲质量分析Mixin"""
from typing import Dict
from typing import List
from typing import Any
import re
from app.services.quality_control import QualityControlService


class QcGlobalAnalysisMixin:
    """全局大纲质量分析"""

    async def analyze_global_outline_quality(
        self,
        global_outline_content: str,
        project,
        user_id: int,
        dimensions: List[str] = None,
        depth: str = "standard",
        task_id: str = None  # v1.1新增: SSE任务ID，用于实时进度推送
    ) -> Dict[str, Any]:
        """
        对全局大纲执行质量分析(用户手动触发)

        Args:
            global_outline_content: 全局大纲内容
            project: 项目对象
            user_id: 用户ID
            dimensions: 分析维度(默认全部四维度)
            depth: 分析深度(quick/standard/deep)
            task_id: SSE任务ID(v1.1新增,用于实时进度推送)

        Returns:
            质控报告字典
        """
        if dimensions is None:
            dimensions = [
                "global_structure",
                "global_character_worldview",
                "global_plot_consistency",
                "global_storyline_integrity"
            ]

        self.logger.info(f"[全局大纲质控] 开始分析,维度: {dimensions}, 深度: {depth}")

        try:
            # 1. 初始化质控服务
            from app.services.quality_control import QualityControlService
            qc_service = QualityControlService(db=self.db)

            # 2. 构建分析数据
            analysis_data = {
                "content": global_outline_content,
                "project": project,
                "character_profiles": getattr(project, 'character_profiles', None) or [],
                "worldview_settings": getattr(project, 'worldview_settings', None) or {}
            }

            # 3. 执行多维度分析
            quality_report = await self._analyze_global_outline_dimensions(
                qc_service=qc_service,
                analysis_data=analysis_data,
                dimensions=dimensions,
                depth=depth,
                user_id=user_id,
                task_id=task_id  # v1.1新增: 传递task_id以支持SSE推送
            )

            self.logger.info(
                f"[全局大纲质控] 分析完成,总分: {quality_report.get('overall_score', 0)}, "
                f"问题数: {len(quality_report.get('issues', []))}"
            )

            return quality_report

        except Exception as e:
            self.logger.error(f"[全局大纲质控] 分析失败: {e!r}")
            return {
                "success": False,
                "error": str(e),
                "overall_score": 0,
                "dimension_scores": {},
                "issues": []
            }


    async def _analyze_global_outline_dimensions(
        self,
        qc_service,
        analysis_data,
        dimensions,
        depth,
        user_id,
        task_id: str = None  # v1.1新增: SSE任务ID
    ) -> Dict[str, Any]:
        """
        执行全局大纲多维度分析(v1.1优化: 并行调用+SSE进度推送)

        优化点:
        - 使用asyncio.gather并行执行四个维度的LLM分析
        - SSE实时推送每个维度的分析进度
        - 预计加速比: 3-4倍(原需40-80分钟,现需10-20分钟)
        """
        import asyncio

        dimension_scores = {}
        all_issues = []

        global_outline = analysis_data["content"]
        project = analysis_data["project"]
        character_profiles = analysis_data.get("character_profiles", [])
        worldview_settings = analysis_data.get("worldview_settings", {})

        total_dimensions = len(dimensions)
        self.logger.info(
            f"[全局大纲质控] 开始并行分析 {total_dimensions} 个维度: {dimensions}"
        )

        # v1.1新增: SSE进度推送 - 开始
        if task_id:
            try:
                from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                await publish_qc_progress(
                    task_id=task_id,
                    event_type="started",
                    message=f"开始分析{total_dimensions}个维度",
                    data={"total_dimensions": total_dimensions,
                          "dimensions": dimensions}
                )
            except Exception as e:
                self.logger.warning(f"[全局大纲质控] SSE推送失败: {e}")

        # v1.1修复: 使用共享计数器跟踪已完成维度数
        completed_count = 0
        completed_lock = asyncio.Lock()

        # ✅ 优化: 并行执行所有维度分析
        async def analyze_single_dimension(dimension: str, index: int):
            """单个维度分析任务"""
            nonlocal completed_count
            try:
                self.logger.info(f"[全局大纲质控] 维度 {dimension} 开始分析...")

                # v1.1新增: SSE进度推送 - 维度开始
                if task_id:
                    from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                    await publish_qc_progress(
                        task_id=task_id,
                        event_type="progress",
                        dimension=dimension,
                        status="running",
                        progress=0,  # 开始时进度为0
                        message=f"正在分析: {dimension}"
                    )

                analyzer = qc_service._get_analyzer(dimension)
                self.logger.info(
                    f"[全局大纲质控] 维度 {dimension} 获取分析器成功，准备调用analyze方法...")

                result = await analyzer.analyze(
                    global_outline=global_outline,
                    project=project,
                    character_profiles=character_profiles,
                    worldview_settings=worldview_settings,
                    depth=depth,
                    db=self.db,
                    user_id=user_id
                )

                self.logger.info(
                    f"[全局大纲质控] 维度 {dimension} 分析完成，得分: {result.get('score', 0)}, 问题数: {len(result.get('issues', []))}")

                # v1.1修复: 原子更新已完成计数
                async with completed_lock:
                    completed_count += 1
                    current_progress = int(
                        (completed_count / total_dimensions) * 100)

                # v1.1新增: SSE进度推送 - 维度完成
                if task_id:
                    from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                    await publish_qc_progress(
                        task_id=task_id,
                        event_type="progress",
                        dimension=dimension,
                        status="success",
                        progress=current_progress,
                        message=f"分析完成: {dimension}",
                        data={
                            "score": result.get("score", 0),
                            "issues_count": len(result.get("issues", [])),
                            "completed_dimensions": completed_count
                        }
                    )

                return {
                    "dimension": dimension,
                    "success": True,
                    "score": result.get("score", 0),
                    "issues": result.get("issues", []),
                    "metadata": result.get("metadata", {})
                }

            except Exception as e:
                self.logger.error(
                    f"[全局大纲质控] 维度 {dimension} 分析失败: {e!r}"
                )

                # v1.1修复: 原子更新已完成计数（失败也算完成）
                async with completed_lock:
                    completed_count += 1
                    current_progress = int(
                        (completed_count / total_dimensions) * 100)

                # v1.1新增: SSE进度推送 - 维度失败
                if task_id:
                    try:
                        from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                        await publish_qc_progress(
                            task_id=task_id,
                            event_type="progress",
                            dimension=dimension,
                            status="failed",
                            progress=current_progress,
                            message=f"分析失败: {dimension}",
                            data={"error": str(
                                e), "completed_dimensions": completed_count}
                        )
                    except Exception as save_err:
                        logger.warning(f"保存维度分析失败状态失败: {save_err}")

                return {
                    "dimension": dimension,
                    "success": False,
                    "score": 0,
                    "issues": [],
                    "error": str(e)
                }

        # 并行执行所有维度分析
        tasks = [analyze_single_dimension(dim, idx)
                 for idx, dim in enumerate(dimensions)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"[全局大纲质控] 维度分析异常: {result!r}")
                continue

            dimension = result["dimension"]
            dimension_scores[dimension] = result["score"]
            all_issues.extend(result["issues"])

            if result["success"]:
                self.logger.info(
                    f"[全局大纲质控] 维度 {dimension} 分析完成, "
                    f"得分: {result['score']}, 问题数: {len(result['issues'])}"
                )
            else:
                self.logger.warning(
                    f"[全局大纲质控] 维度 {dimension} 分析失败: {result.get('error')}"
                )

        # 计算总分(各维度平均分)
        overall_score = (
            sum(dimension_scores.values()) / len(dimension_scores)
            if dimension_scores else 0
        )

        self.logger.info(
            f"[全局大纲质控] 并行分析完成, "
            f"总分: {overall_score:.1f}, 总问题数: {len(all_issues)}"
        )

        # v1.1新增: SSE进度推送 - 全部完成
        if task_id:
            try:
                from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                await publish_qc_progress(
                    task_id=task_id,
                    event_type="completed",
                    progress=100,
                    message="所有维度分析完成",
                    data={
                        "overall_score": overall_score,
                        "total_issues": len(all_issues),
                        "dimension_scores": dimension_scores
                    }
                )
            except Exception as e:
                self.logger.warning(f"[全局大纲质控] SSE完成推送失败: {e}")

        # 生成智能建议
        all_issues = self._generate_global_outline_smart_suggestions(
            all_issues, global_outline
        )

        return {
            "success": True,
            "overall_score": round(overall_score, 1),
            "dimension_scores": dimension_scores,
            "issues": all_issues,
            "original_outline": global_outline,  # 保存原始大纲内容，用于LLM修正
            "metadata": {
                "dimensions_analyzed": dimensions,
                "depth": depth,
                "outline_length": len(global_outline),
                "total_issues": len(all_issues)
            }
        }


    def _generate_global_outline_smart_suggestions(
        self,
        issues: List[Dict],
        global_outline: str
    ) -> List[Dict]:
        """为全局大纲问题生成智能修正建议"""
        try:
            from app.services.quality_control.analyzers.smart_suggestions import get_smart_suggestion_engine
            suggestion_engine = get_smart_suggestion_engine()

            # 构建chapters_data格式(兼容smart_suggestions)
            chapters_data = [{
                "content": global_outline,
                "summary": global_outline[:500]
            }]

            enhanced_issues = suggestion_engine.generate_suggestions(
                issues=issues,
                chapters_data=chapters_data
            )

            return enhanced_issues

        except Exception as e:
            self.logger.warning(f"[全局大纲质控] 生成智能建议失败: {e!r}")
            return issues


