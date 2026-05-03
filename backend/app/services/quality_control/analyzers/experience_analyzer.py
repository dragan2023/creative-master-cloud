"""
阅读体验分析器

分析章末悬念、金句密度、段落舒适度

@date: 2026-04-12
"""
import re
from typing import Dict, List, Any


class ExperienceAnalyzer:
    """阅读体验分析器"""

    async def analyze(self, chapters_data: List[Dict], project: Any,
                      rule_results: Dict = None, depth: str = "standard",
                      db=None, user_id: int = 0, **kwargs) -> Dict:
        """
        分析阅读体验质量

        Args:
            chapters_data: 章节数据列表
            project: 项目对象
            rule_results: 规则引擎结果
            depth: 分析深度
            db: 数据库会话
            user_id: 用户ID
        """
        issues = []

        if depth == "quick":
            return await self._quick_analyze(chapters_data)

        # 标准/深度模式:完整分析
        # 1. 章末悬念分析(规则)
        issues.extend(self._analyze_chapter_hooks(chapters_data))

        # 2. 段落舒适度分析(规则)
        issues.extend(self._analyze_paragraph_comfort(chapters_data))

        # 3. 金句密度分析(LLM)
        if depth in ["standard", "deep"]:
            llm_issues = await self._analyze_golden_quotes_with_llm(
                chapters_data, db, user_id
            )
            issues.extend(llm_issues)

        # 计算得分
        score = 100 - len(issues) * 5
        score = max(0, min(100, score))

        return {
            "score": score,
            "issues": issues[:30],  # 最多30个问题
            "tokens": 0,
            "metadata": {
                "avg_paragraph_length": self._calc_avg_paragraph_length(chapters_data),
                "hook_score": self._calc_hook_score(chapters_data)
            }
        }

    async def _quick_analyze(self, chapters_data: List[Dict]) -> Dict:
        """快速分析"""
        issues = []
        issues.extend(self._analyze_chapter_hooks(chapters_data))

        score = 100 - len(issues) * 5
        return {"score": max(0, score), "issues": issues[:20], "tokens": 0}

    def _analyze_chapter_hooks(self, chapters_data: List[Dict]) -> List[Dict]:
        """分析章末悬念"""
        issues = []

        for ch in chapters_data:
            content = ch.get("content", "")
            if len(content) < 200:
                continue

            ending = content[-200:]

            # 检测疑问句
            question_marks = len(re.findall(r'[?？]', ending))

            # 检测悬念词
            suspense_words = len(re.findall(
                r'突然|忽然|却|没想到|竟然|但是|然而|谁知', ending))

            # 检测省略号(表示未尽)
            ellipsis = len(re.findall(r'\.{3}|……', ending))

            # 如果没有任何悬念元素
            if question_marks == 0 and suspense_words == 0 and ellipsis == 0 and len(ending) > 100:
                issues.append({
                    "id": f"HOOK-{ch['chapter_number']}",
                    "dimension": "experience",
                    "category": "章末平淡",
                    "severity": "info",
                    "location": {"chapter": ch["chapter_number"]},
                    "description": f"第{ch['chapter_number']}章结尾缺乏悬念",
                    "evidence": ending[:100] + "...",
                    "suggestion": "建议在结尾增加悬念、疑问或转折点,吸引读者继续阅读",
                    "metadata": {
                        "ending_length": len(ending),
                        "has_question": question_marks > 0,
                        "has_suspense": suspense_words > 0
                    }
                })

        return issues

    def _analyze_paragraph_comfort(self, chapters_data: List[Dict]) -> List[Dict]:
        """分析段落舒适度"""
        issues = []

        for ch in chapters_data:
            content = ch.get("content", "")
            paragraphs = content.split('\n')

            # 过滤空行
            paragraphs = [p.strip() for p in paragraphs if p.strip()]

            if not paragraphs:
                continue

            # 检测超长段落(>300字)
            long_paragraphs = [p for p in paragraphs if len(p) > 300]

            if len(long_paragraphs) > 3:
                issues.append({
                    "id": f"PARA-LONG-{ch['chapter_number']}",
                    "dimension": "experience",
                    "category": "段落过长",
                    "severity": "warning",
                    "location": {"chapter": ch["chapter_number"]},
                    "description": f"第{ch['chapter_number']}章有{len(long_paragraphs)}个超长段落",
                    "evidence": f"最长段落: {max(len(p) for p in long_paragraphs)}字",
                    "suggestion": "建议将长段落拆分,每段控制在200字以内,提升移动端阅读体验",
                    "metadata": {
                        "long_paragraph_count": len(long_paragraphs),
                        "max_paragraph_length": max(len(p) for p in long_paragraphs)
                    }
                })

        return issues

    def _calc_avg_paragraph_length(self, chapters_data: List[Dict]) -> float:
        """计算平均段落长度"""
        total_length = 0
        total_paragraphs = 0

        for ch in chapters_data:
            content = ch.get("content", "")
            paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
            total_length += sum(len(p) for p in paragraphs)
            total_paragraphs += len(paragraphs)

        return total_length / total_paragraphs if total_paragraphs > 0 else 0

    def _calc_hook_score(self, chapters_data: List[Dict]) -> float:
        """计算章末悬念得分"""
        if not chapters_data:
            return 0

        good_hooks = 0

        for ch in chapters_data:
            content = ch.get("content", "")
            if len(content) < 200:
                continue

            ending = content[-200:]
            question_marks = len(re.findall(r'[?？]', ending))
            suspense_words = len(re.findall(r'突然|忽然|却|没想到|竟然', ending))

            if question_marks > 0 or suspense_words > 0:
                good_hooks += 1

        return (good_hooks / len(chapters_data)) * 100

    async def _analyze_golden_quotes_with_llm(self, chapters_data: List[Dict],
                                              db, user_id: int) -> List[Dict]:
        """使用LLM分析金句密度"""
        issues = []

        try:
            from app.services.quality_control.engines.llm_engine import LLMAnalysisEngine
            from app.agents.llm_manager import get_llm_manager
            from app.services.quality_control.prompts.quality_prompts import QUALITY_PROMPTS

            llm_engine = LLMAnalysisEngine(
                get_llm_manager(), db=db, user_id=user_id)

            # 批量分析(每次5章)
            batch_size = 5
            for i in range(0, len(chapters_data), batch_size):
                batch = chapters_data[i:i+batch_size]

                # 提取每章内容（完整内容以确保不遗漏任何精彩片段）
                chapter_excerpts = []
                for ch in batch:
                    content = ch.get("content", "")
                    excerpt = content  # 不再截断，确保金句分析覆盖全文
                    chapter_excerpts.append({
                        "chapter": ch["chapter_number"],
                        "title": ch.get("title", ""),
                        "excerpt": excerpt
                    })

                # 调用LLM分析金句
                # 模板键名为 "highlight_extraction"，占位符为 {chapter_content}
                prompt = QUALITY_PROMPTS.get("highlight_extraction", "").format(
                    chapter_content="\n\n".join([
                        f"第{ch['chapter']}章 {ch['title']}\n{ch['excerpt']}"
                        for ch in chapter_excerpts
                    ])
                )

                result = await llm_engine.analyze_with_llm(
                    prompt=prompt,
                    max_tokens=1000
                )

                # 检查金句密度
                quote_density = result.get("quote_density", 0)
                if quote_density < 0.5:  # 每章少于0.5个金句
                    issues.append({
                        "id": f"QUOTE-DENSITY-{batch[0]['chapter_number']}",
                        "dimension": "experience",
                        "category": "金句密度低",
                        "severity": "info",
                        "location": {"chapter": batch[0]["chapter_number"]},
                        "description": f"第{batch[0]['chapter_number']}-{batch[-1]['chapter_number']}章金句密度偏低",
                        "evidence": f"金句密度: {quote_density:.2f}句/章",
                        "suggestion": "建议增加精彩对白、深刻感悟或优美描写,提升文本文学性",
                        "metadata": {
                            "quote_density": quote_density,
                            "chapter_range": f"{batch[0]['chapter_number']}-{batch[-1]['chapter_number']}"
                        }
                    })

        except Exception as e:
            # LLM分析失败不影响整体结果，但必须记录日志便于排查
            import logging
            _logger = logging.getLogger("quality_control.experience_analyzer")
            _logger.warning(f"金句密度LLM分析失败: {e}", exc_info=True)

        return issues
