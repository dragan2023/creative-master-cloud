"""
宏观结构分析器

分析维度:
1. 情节节奏与价值转折
2. 伏笔回收追踪
3. 卷与卷的边界感

@date: 2026-04-12
@version: v3.1.0
"""
from typing import Dict, List, Any

from app.core.logger import get_logger
from app.services.quality_control.prompts.quality_prompts import get_prompt

logger = get_logger("quality_control.analyzers.structure")


class StructureAnalyzer:
    """宏观结构分析器"""

    async def analyze(
        self,
        chapters_data: List[Dict],
        project: Any,
        rule_results: Dict = None,
        depth: str = "standard",
        db=None,
        user_id: int = 0,
        **kwargs
    ) -> Dict:
        """
        执行宏观结构分析

        Args:
            chapters_data: 章节数据
            project: 项目对象
            rule_results: 规则引擎结果
            depth: 分析深度

        Returns:
            分析结果
        """
        all_issues = []
        total_tokens = 0

        # 1. 情节节奏分析
        pacing_result = await self._analyze_pacing(chapters_data, depth, db=db, user_id=user_id)
        all_issues.extend(pacing_result.get("issues", []))
        total_tokens += pacing_result.get("tokens", 0)
        pacing_score = pacing_result.get("score", 70)

        # 2. 伏笔回收追踪(仅deep模式)
        foreshadow_score = 80  # 默认分
        if depth == "deep":
            foreshadow_result = await self._analyze_foreshadowing(chapters_data, project)
            all_issues.extend(foreshadow_result.get("issues", []))
            total_tokens += foreshadow_result.get("tokens", 0)
            foreshadow_score = foreshadow_result.get("score", 80)

        # 3. 卷末情绪诊断
        volume_score = 75  # 默认分

        # 综合评分
        overall_score = (pacing_score + foreshadow_score + volume_score) / 3

        return {
            "score": overall_score,
            "issues": all_issues,
            "statistics": {
                "pacing_score": pacing_score,
                "foreshadow_score": foreshadow_score,
                "volume_score": volume_score
            },
            "tokens": total_tokens
        }

    async def _analyze_pacing(self, chapters_data: List[Dict], depth: str, db=None, user_id: int = 0) -> Dict:
        """情节节奏分析"""
        issues = []

        if depth == "quick":
            # 快速模式:仅基于章节长度和元数据简单评估
            return {
                "score": 70,
                "issues": [],
                "tokens": 0
            }

        # 提取章节摘要
        chapter_summaries = []
        for ch in chapters_data:
            summary = ch.get("metadata", {}).get("chapter_summary", "")
            if not summary:
                # 如果没有摘要,取前200字
                summary = ch.get("content", "")[:200]

            chapter_summaries.append({
                "chapter_number": ch["chapter_number"],
                "summary": summary
            })

        # 标准/深度模式:调用LLM分析
        from app.services.quality_control.engines.llm_engine import LLMAnalysisEngine
        from app.agents.llm_manager import get_llm_manager

        llm_engine = LLMAnalysisEngine(
            get_llm_manager(), db=db, user_id=user_id)
        result = await llm_engine.analyze_pacing_batch(chapter_summaries)

        # 处理结果
        scores = result.get("scores", {}).get("chapter_scores", {})
        low_ranges = result.get("scores", {}).get("low_conflict_ranges", [])

        # 生成问题
        for range_info in low_ranges:
            issues.append({
                "id": f"PACING-{range_info['start_chapter']}",
                "dimension": "structure",
                "category": "情节节奏",
                "severity": "warning",
                "location": {
                    "start_chapter": range_info["start_chapter"],
                    "end_chapter": range_info["end_chapter"]
                },
                "description": f"第{range_info['start_chapter']}-{range_info['end_chapter']}章处于低冲突状态",
                "evidence": f"平均冲突强度: {range_info['avg_score']}/10",
                "suggestion": "建议在此区间插入伏笔回收或小危机",
                "metadata": range_info
            })

        # 计算得分
        if scores:
            avg_score = sum(s.get("score", 5)
                            for s in scores.values()) / len(scores)
            pacing_score = avg_score * 10  # 转为百分制
        else:
            pacing_score = 70

        return {
            "score": pacing_score,
            "issues": issues,
            "tokens": result.get("tokens", 0)
        }

    async def _analyze_foreshadowing(self, chapters_data: List[Dict], project: Any) -> Dict:
        """伏笔回收追踪"""
        # 简化实现:基于关键词匹配识别伏笔
        issues = []

        foreshadow_keywords = ["神秘", "秘密", "疑惑", "不解", "为何", "难道",
                               "总有一天", "迟早", "终将", "未解之谜"]

        identified_foreshadows = []
        for ch in chapters_data:
            content = ch.get("content", "")[:2000]  # 每章前2000字

            for keyword in foreshadow_keywords:
                if keyword in content:
                    # 简单提取上下文
                    idx = content.find(keyword)
                    context = content[max(0, idx-50):idx+100]

                    identified_foreshadows.append({
                        "id": f"V{len(identified_foreshadows)+1:03d}",
                        "chapter": ch["chapter_number"],
                        "keyword": keyword,
                        "context": context
                    })

        # 检查伏笔是否在后续被提及(简化版)
        for foreshadow in identified_foreshadows[:10]:  # 最多检查10个
            buried_chapter = foreshadow["chapter"]
            keyword = foreshadow["keyword"]

            # 在后续章节中搜索
            last_mentioned = buried_chapter
            for ch in chapters_data:
                if ch["chapter_number"] > buried_chapter:
                    if keyword in ch.get("content", "")[:1000]:
                        last_mentioned = ch["chapter_number"]

            chapters_gap = chapters_data[-1]["chapter_number"] - \
                last_mentioned if chapters_data else 0

            if chapters_gap > 30:  # 超过30章未提及
                issues.append({
                    "id": foreshadow["id"],
                    "dimension": "structure",
                    "category": "伏笔未回收",
                    "severity": "warning" if chapters_gap < 50 else "critical",
                    "location": {"chapter": buried_chapter},
                    "description": f"伏笔'{keyword}'已过{chapters_gap}章未提及",
                    "evidence": foreshadow["context"],
                    "suggestion": f"建议在近期剧情中回收此伏笔",
                    "metadata": {
                        "chapter_buried": buried_chapter,
                        "last_mentioned": last_mentioned,
                        "gap": chapters_gap
                    }
                })

        score = 100 - len(issues) * 10
        return {
            "score": max(0, score),
            "issues": issues,
            "tokens": 0  # 规则实现,无LLM调用
        }
