"""大纲生成器 - 单元概述质量分析Mixin"""
from typing import Dict
from typing import List
from typing import Any
import re
import os
from app.services.quality_control import QualityControlService


class QcUnitAnalysisMixin:
    """单元概述质量分析"""

    async def _analyze_unit_summaries_quality(
        self,
        qc_service: Any,
        chapters_data: List[Dict],
        dimensions: List[str],
        depth: str = "deep",
        global_outline: str = "",
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        db: Any = None,
        user_id: int = 0,
        project_id: int = 0
    ) -> Dict[str, Any]:
        """
        分析单元概述质量（使用专用的单元概述五维度质控机制）

        五维度检测：
        1. unit_structure（单元结构层）- 单元长度分布、衔接流畅度、情节节奏
        2. unit_character（人物发展层）- 人物状态变化、关系逻辑
        3. unit_consistency（一致性层）- 与全局大纲的偏离度、核心要素完整性
        4. unit_timeline_space（时间线与空间逻辑层）- 人物位置、出场时间线、事件因果、状态连续性
        5. unit_ooc（人物OOC层）- 人物行为是否违背人设

        Args:
            qc_service: QualityControlService 实例
            chapters_data: 章节数据列表
            dimensions: 分析维度
            depth: 分析深度（v3.0强制deep）
            global_outline: 全局大纲内容
            user_id: 用户ID
            project_id: 项目ID

        Returns:
            质量报告字典
        """
        try:
            # 导入专用的单元概述分析器
            from app.services.quality_control.analyzers.unit_quality_analyzer import (
                UnitStructureAnalyzer,
                UnitCharacterAnalyzer,
                UnitConsistencyAnalyzer,
                UnitTimelineSpaceAnalyzer,
                UnitOOCAnalyzer
            )

            # 创建虚拟项目对象（单元概述阶段还没有project_id）
            class VirtualProject:
                def __init__(self):
                    self.id = project_id
                    self.title = "单元概述"
                    self.genre = ""
                    self.target_audience = ""
                    self.style_tags = []
                    # 使用传入的真实数据，而非空字典
                    self.character_profiles = character_profiles or {}
                    self.world_settings = worldview_settings or {}
                    self.plot_outline = global_outline

            virtual_project = VirtualProject()

            # 执行五个维度的分析
            all_issues = []
            dimension_scores = {}
            total_tokens = 0
            cross_validation_data = None

            # 维度1: 单元结构层
            if "unit_structure" in dimensions:
                self.logger.info("[单元概述质控] 开始单元结构层检测...")
                structure_analyzer = UnitStructureAnalyzer()
                structure_result = await structure_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    db=db or self.db,
                    user_id=user_id,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,  # v2.0新增
                    worldview_settings=virtual_project.world_settings  # v2.0新增
                )
                all_issues.extend(structure_result.get("issues", []))
                dimension_scores["unit_structure"] = structure_result.get(
                    "score", 50)
                total_tokens += structure_result.get("tokens", 0)
                self.logger.info(
                    f"[单元概述质控] 单元结构层完成，得分: {structure_result.get('score', 50)}")

            # 维度2: 人物发展层
            if "unit_character" in dimensions:
                self.logger.info("[单元概述质控] 开始人物发展层检测...")
                character_analyzer = UnitCharacterAnalyzer()
                character_result = await character_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,  # v2.0新增
                    db=db or self.db,
                    user_id=user_id
                )
                all_issues.extend(character_result.get("issues", []))
                dimension_scores["unit_character"] = character_result.get(
                    "score", 50)
                total_tokens += character_result.get("tokens", 0)
                self.logger.info(
                    f"[单元概述质控] 人物发展层完成，得分: {character_result.get('score', 50)}")

            # 维度3: 一致性层
            if "unit_consistency" in dimensions:
                self.logger.info("[单元概述质控] 开始一致性层检测...")
                consistency_analyzer = UnitConsistencyAnalyzer()
                consistency_result = await consistency_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    db=db or self.db,
                    user_id=user_id,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,  # v2.0新增
                    worldview_settings=virtual_project.world_settings  # v2.0新增
                )
                all_issues.extend(consistency_result.get("issues", []))
                dimension_scores["unit_consistency"] = consistency_result.get(
                    "score", 50)
                total_tokens += consistency_result.get("tokens", 0)

            # v2.0新增: 提取交叉验证数据
                cross_validation_data = consistency_result.get(
                    "cross_validation")

                self.logger.info(
                    f"[单元概述质控] 一致性层完成，得分: {consistency_result.get('score', 50)}")

            # 维度4: 时间线与空间逻辑层
            if "unit_timeline_space" in dimensions:
                self.logger.info("[单元概述质控] 开始时间线与空间逻辑层检测...")
                timeline_analyzer = UnitTimelineSpaceAnalyzer()
                timeline_result = await timeline_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    db=db or self.db,
                    user_id=user_id,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,
                    worldview_settings=virtual_project.world_settings
                )
                all_issues.extend(timeline_result.get("issues", []))
                dimension_scores["unit_timeline_space"] = timeline_result.get(
                    "score", 50)
                total_tokens += timeline_result.get("tokens", 0)
                self.logger.info(
                    f"[单元概述质控] 时间线空间层完成，得分: {timeline_result.get('score', 50)}")

            # 维度5: 人物OOC层
            if "unit_ooc" in dimensions:
                self.logger.info("[单元概述质控] 开始人物OOC层检测...")
                ooc_analyzer = UnitOOCAnalyzer()
                ooc_result = await ooc_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    db=db or self.db,
                    user_id=user_id,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,
                    worldview_settings=virtual_project.world_settings
                )
                all_issues.extend(ooc_result.get("issues", []))
                dimension_scores["unit_ooc"] = ooc_result.get(
                    "score", 50)
                total_tokens += ooc_result.get("tokens", 0)
                self.logger.info(
                    f"[单元概述质控] 人物OOC层完成，得分: {ooc_result.get('score', 50)}")

            # 计算综合评分
            overall_score = (
                sum(dimension_scores.values()) / len(dimension_scores)
                if dimension_scores else 0
            )

            # 构建质量报告
            # v2.1: 为每个issue添加auto_fix字段(初始为None,用户点击时动态生成)
            issues_with_auto_fix = []
            for issue in all_issues:
                issue_with_fix = issue.copy()
                issue_with_fix["auto_fix"] = None  # 初始为None
                issues_with_auto_fix.append(issue_with_fix)

            report = {
                "overall_score": round(overall_score, 2),
                "dimension_scores": dimension_scores,
                "issues": issues_with_auto_fix,
                "project_id": project_id,  # v2.1新增: 添加项目ID
                "statistics": {
                    "total_tokens": total_tokens,
                    "total_units": len(chapters_data),
                    "critical_issues": len([i for i in all_issues if i.get("severity") == "critical"]),
                    "warning_issues": len([i for i in all_issues if i.get("severity") == "warning"])
                }
            }

            # v2.0新增: 添加交叉验证数据(如果有)
            if cross_validation_data:
                report["cross_validation"] = cross_validation_data

            self.logger.info(
                f"[单元概述质控] 检测完成，综合得分: {overall_score:.2f}, "
                f"发现问题: {len(all_issues)}个"
            )

            return report

        except Exception as e:
            self.logger.error(f"[单元概述质量分析] 分析失败: {str(e)}")
            import traceback
            self.logger.error(f"[单元概述质量分析] 异常堆栈: {traceback.format_exc()}")
            # 返回空报告
            return {
                "overall_score": 0,
                "dimension_scores": {},
                "issues": [],
                "statistics": {}
            }


    def _format_all_units(
        self,
        full_parsed: Dict[str, Dict[str, Any]],
        content_type: str
    ) -> str:
        """格式化所有单元为完整文本"""
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
            content_type, "章"
        )

        lines = []
        for unit_num in sorted(full_parsed.keys(), key=lambda x: int(x)):
            unit = full_parsed[unit_num]
            title = unit.get("title", "")
            summary = unit.get("summary", "")

            lines.append(f"### 第{unit_num}{unit_label}：{title}")
            lines.append(f"**本{unit_label}梗概**：{summary}")
            lines.append("")

        return "\n".join(lines)

    # ==================== 全局大纲质量管控方法 ====================


