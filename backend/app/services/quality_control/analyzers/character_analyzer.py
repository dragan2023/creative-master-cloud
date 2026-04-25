"""
人物塑造分析器

分析角色一致性、台词指纹、配角活跃度

@date: 2026-04-12
"""
import re
from typing import Dict, List, Any
from sqlalchemy import select


class CharacterAnalyzer:
    """人物塑造分析器"""

    async def analyze(self, chapters_data: List[Dict], project: Any,
                      rule_results: Dict = None, depth: str = "standard",
                      db=None, user_id: int = 0, **kwargs) -> Dict:
        """
        分析人物塑造质量

        Args:
            chapters_data: 章节数据列表
            project: 项目对象
            rule_results: 规则引擎结果
            depth: 分析深度
            db: 数据库会话
            user_id: 用户ID
        """
        issues = []

        # 从项目设定中提取角色列表
        character_names = await self._extract_character_names(project, db)

        if depth == "quick":
            # 快速模式:仅检查角色出场
            return await self._quick_analyze(chapters_data, character_names)

        # 标准/深度模式:完整分析
        # 1. 统计角色出场
        character_stats = self._analyze_character_mentions(
            chapters_data, character_names)

        # 2. 检查角色消失
        issues.extend(self._check_character_absence(
            character_stats, chapters_data))

        # 3. 检查角色一致性(需要LLM)
        if depth in ["standard", "deep"]:
            llm_issues = await self._check_character_consistency_with_llm(
                chapters_data, character_stats, db, user_id
            )
            issues.extend(llm_issues)

        # 4. 计算得分
        score = 100 - len(issues) * 10
        score = max(0, min(100, score))

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_characters": len(character_names),
                "active_characters": len([c for c in character_stats.values() if c["count"] > 0])
            }
        }

    async def _extract_character_names(self, project: Any, db) -> List[str]:
        """从项目设定中提取角色名称"""
        character_names = []

        try:
            # 尝试从generation_config中解析角色设定
            if project.generation_config:
                import json
                config = json.loads(project.generation_config)

                # 检查是否有characters字段
                if "characters" in config:
                    for char in config["characters"]:
                        if isinstance(char, dict) and "name" in char:
                            character_names.append(char["name"])
                        elif isinstance(char, str):
                            character_names.append(char)

                # 检查character_profiles字段
                if "character_profiles" in config:
                    profiles = config["character_profiles"]
                    if isinstance(profiles, list):
                        for profile in profiles:
                            if isinstance(profile, dict) and "name" in profile:
                                character_names.append(profile["name"])

            # 如果没有找到,使用默认角色名
            if not character_names:
                character_names = ["主角"]

        except Exception as e:
            # 解析失败,使用默认值
            character_names = ["主角"]

        return character_names

    async def _quick_analyze(self, chapters_data: List[Dict], character_names: List[str]) -> Dict:
        """快速分析:仅检查角色出场"""
        issues = []
        character_stats = self._analyze_character_mentions(
            chapters_data, character_names)
        issues.extend(self._check_character_absence(
            character_stats, chapters_data))

        score = 100 - len(issues) * 15
        return {"score": max(0, score), "issues": issues, "tokens": 0}

    def _analyze_character_mentions(self, chapters_data: List[Dict],
                                    character_names: List[str]) -> Dict:
        """统计角色出场情况"""
        character_stats = {}

        for name in character_names:
            character_stats[name] = {
                "count": 0,
                "chapters": [],
                "last_chapter": 0,
                "first_chapter": 999999,
                "total_mentions": 0
            }

        for ch in chapters_data:
            content = ch.get("content", "")
            chapter_num = ch.get("chapter_number", 0)

            for name in character_names:
                # 使用正则匹配完整角色名
                pattern = re.compile(re.escape(name))
                matches = pattern.findall(content)
                count = len(matches)

                if count > 0:
                    character_stats[name]["count"] += 1
                    character_stats[name]["chapters"].append(chapter_num)
                    character_stats[name]["last_chapter"] = chapter_num
                    character_stats[name]["first_chapter"] = min(
                        character_stats[name]["first_chapter"], chapter_num
                    )
                    character_stats[name]["total_mentions"] += count

        return character_stats

    def _check_character_absence(self, character_stats: Dict,
                                 chapters_data: List[Dict]) -> List[Dict]:
        """检查角色消失问题"""
        issues = []

        if not chapters_data:
            return issues

        total_chapters = chapters_data[-1].get("chapter_number", 0)

        for name, stats in character_stats.items():
            # 跳过只在后面章节出现的角色
            if stats["count"] == 0:
                continue

            # 计算消失章节数
            gap = total_chapters - stats["last_chapter"]

            # 重要角色消失阈值:30章
            if gap > 30 and stats["count"] > 3:
                issues.append({
                    "id": f"CHAR-ABSENCE-{name}",
                    "dimension": "character",
                    "category": "角色消失",
                    "severity": "warning",
                    "location": {"chapter": stats["last_chapter"]},
                    "description": f"角色'{name}'已{gap}章未出场",
                    "evidence": f"上次出场: 第{stats['last_chapter']}章, 累计出场{stats['count']}次",
                    "suggestion": "建议安排角色露脸或通过他人转述提及近况,保持角色活跃度",
                    "metadata": {
                        "character": name,
                        "gap": gap,
                        "total_appearances": stats["count"]
                    }
                })

        return issues

    async def _check_character_consistency_with_llm(self, chapters_data: List[Dict],
                                                    character_stats: Dict,
                                                    db, user_id: int) -> List[Dict]:
        """使用LLM检查角色一致性"""
        issues = []

        try:
            from app.services.quality_control.engines.llm_engine import LLMAnalysisEngine
            from app.agents.llm_manager import get_llm_manager
            from app.services.quality_control.prompts.quality_prompts import QUALITY_PROMPTS

            llm_engine = LLMAnalysisEngine(
                get_llm_manager(), db=db, user_id=user_id)

            # 选择出场最多的3个角色进行分析
            top_characters = sorted(
                character_stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:3]

            for name, stats in top_characters:
                # 获取角色出现的章节内容(最多3章)
                sample_chapters = []
                for ch in chapters_data:
                    if ch["chapter_number"] in stats["chapters"][:3]:
                        content = ch.get("content", "")
                        # 提取包含角色名的段落
                        paragraphs = content.split('\n')
                        relevant_paragraphs = [
                            p for p in paragraphs if name in p
                        ][:5]  # 最多5个段落

                        if relevant_paragraphs:
                            sample_chapters.append({
                                "chapter": ch["chapter_number"],
                                "title": ch.get("title", ""),
                                "excerpts": '\n'.join(relevant_paragraphs)
                            })

                if not sample_chapters:
                    continue

                # 调用LLM分析角色一致性
                # 模板要求 profile(角色设定JSON) 和 actions(行为记录文本)
                import json as _json
                profile_text = _json.dumps({
                    "name": name,
                    "total_appearances": stats["count"],
                    "chapter_range": f"{stats['first_chapter']}-{stats['last_chapter']}"
                }, ensure_ascii=False)
                prompt = QUALITY_PROMPTS.get("character_consistency", "").format(
                    profile=profile_text,
                    actions="\n\n".join([
                        f"第{ch['chapter']}章 {ch['title']}\n{ch['excerpts']}"
                        for ch in sample_chapters
                    ])
                )

                result = await llm_engine.analyze_with_llm(
                    prompt=prompt,
                    max_tokens=1500
                )

                # 解析LLM结果
                if result.get("consistency_score", 100) < 70:
                    issues.append({
                        "id": f"CHAR-CONSISTENCY-{name}",
                        "dimension": "character",
                        "category": "角色不一致",
                        "severity": "critical",
                        "location": {"chapter": sample_chapters[0]["chapter"]},
                        "description": f"角色'{name}'行为或性格存在不一致",
                        "evidence": result.get("evidence", ""),
                        "suggestion": result.get("suggestion", "建议统一角色性格设定"),
                        "metadata": {
                            "character": name,
                            "consistency_score": result.get("consistency_score", 0)
                        }
                    })

        except Exception as e:
            # LLM分析失败不影响整体结果，但必须记录日志便于排查
            import logging
            _logger = logging.getLogger("quality_control.character_analyzer")
            _logger.warning(f"角色一致性LLM分析失败: {e}", exc_info=True)

        return issues
