"""质控批量修正机制正式测试

验证当前生产接口：
1. BATCH_QUALITY_FIX_PROMPT_NOVEL / BATCH_QUALITY_FIX_PROMPT_SCRIPT 模板占位符与关键原则
2. _get_batch_fix_prompt / _get_fix_prompt 内容类型选择函数
3. QualityFixGenerator._format_issues_list 输出格式
4. quality_control_v2 拆分包公共入口可导入
"""
import pytest

from app.services.quality_control.fix_generator import (
    BATCH_QUALITY_FIX_PROMPT_NOVEL,
    BATCH_QUALITY_FIX_PROMPT_SCRIPT,
    QUALITY_FIX_PROMPT_NOVEL,
    QUALITY_FIX_PROMPT_SCRIPT,
    QualityFixGenerator,
    _get_batch_fix_prompt,
    _get_fix_prompt,
)

# generate_batch_fix 实际 format() 时传入的全部占位符
REQUIRED_BATCH_PLACEHOLDERS = [
    "{issue_count}",
    "{all_issues_list}",
    "{chapter_number}",
    "{original_content}",
    "{unit_summary}",
    "{knowledge_graph_context}",
    "{character_profiles}",
    "{worldview_settings}",
]

# 批量修正提示词必须保留的关键原则表述
REQUIRED_BATCH_PRINCIPLES = ["整体视角", "辩证思考", "避免冲突", "正向优化", "适度修改"]


class TestBatchFixPromptTemplates:
    """批量修正提示词模板结构测试"""

    @pytest.mark.parametrize(
        "template",
        [BATCH_QUALITY_FIX_PROMPT_NOVEL, BATCH_QUALITY_FIX_PROMPT_SCRIPT],
        ids=["novel", "script"],
    )
    def test_batch_prompt_contains_all_required_placeholders(self, template):
        missing = [p for p in REQUIRED_BATCH_PLACEHOLDERS if p not in template]
        assert missing == [], f"批量修正提示词缺少占位符: {missing}"

    @pytest.mark.parametrize(
        "template",
        [BATCH_QUALITY_FIX_PROMPT_NOVEL, BATCH_QUALITY_FIX_PROMPT_SCRIPT],
        ids=["novel", "script"],
    )
    def test_batch_prompt_contains_key_principles(self, template):
        missing = [p for p in REQUIRED_BATCH_PRINCIPLES if p not in template]
        assert missing == [], f"批量修正提示词缺少关键原则: {missing}"

    @pytest.mark.parametrize(
        "template",
        [BATCH_QUALITY_FIX_PROMPT_NOVEL, BATCH_QUALITY_FIX_PROMPT_SCRIPT],
        ids=["novel", "script"],
    )
    def test_batch_prompt_format_renders_without_key_error(self, template):
        """模板必须能被 generate_batch_fix 的实参集合完整渲染"""
        rendered = template.format(
            issue_count=2,
            all_issues_list="问题清单",
            chapter_number=3,
            original_content="原始内容",
            unit_summary="概述",
            knowledge_graph_context="图谱上下文",
            character_profiles="人物",
            worldview_settings="世界观",
        )
        assert "问题清单" in rendered
        assert "原始内容" in rendered


class TestPromptSelectionByContentType:
    """内容类型 → 提示词模板选择函数测试"""

    def test_novel_selects_novel_batch_template(self):
        assert _get_batch_fix_prompt("novel") is BATCH_QUALITY_FIX_PROMPT_NOVEL

    def test_series_script_selects_script_batch_template(self):
        assert _get_batch_fix_prompt("series_script") is BATCH_QUALITY_FIX_PROMPT_SCRIPT

    def test_movie_script_selects_script_batch_template(self):
        assert _get_batch_fix_prompt("movie_script") is BATCH_QUALITY_FIX_PROMPT_SCRIPT

    def test_unknown_type_falls_back_to_novel_batch_template(self):
        assert _get_batch_fix_prompt("unknown_type") is BATCH_QUALITY_FIX_PROMPT_NOVEL

    def test_single_fix_prompt_selection_matches_content_type(self):
        assert _get_fix_prompt("novel") is QUALITY_FIX_PROMPT_NOVEL
        assert _get_fix_prompt("series_script") is QUALITY_FIX_PROMPT_SCRIPT
        assert _get_fix_prompt("movie_script") is QUALITY_FIX_PROMPT_SCRIPT
        assert _get_fix_prompt("unknown_type") is QUALITY_FIX_PROMPT_NOVEL


class TestFormatIssuesList:
    """问题列表格式化输出测试"""

    def test_formats_every_issue_with_identifier_and_fields(self):
        generator = QualityFixGenerator()
        issues = [
            {
                "id": "issue_001",
                "category": "逻辑矛盾",
                "severity": "critical",
                "description": "人物A在第三章已经死亡，但在第五章又出现了",
                "suggestion": "删除第五章中人物A的出现，或修改为回忆/幻觉场景",
            },
            {
                "id": "issue_002",
                "category": "节奏平淡",
                "severity": "medium",
                "description": "本章节缺乏冲突和悬念，节奏过于平缓",
                "suggestion": "增加突发事件或内心冲突",
            },
            {
                "id": "issue_003",
                "category": "人物OOC",
                "severity": "high",
                "description": "人物B的行为与设定不符",
                "suggestion": "调整人物B的行为",
            },
        ]

        formatted = generator._format_issues_list(issues)

        assert "问题1 [issue_001]" in formatted
        assert "问题2 [issue_002]" in formatted
        assert "问题3 [issue_003]" in formatted
        assert "逻辑矛盾" in formatted
        assert "critical" in formatted
        assert "人物A在第三章已经死亡" in formatted
        assert "删除第五章中人物A的出现，或修改为回忆/幻觉场景" in formatted

    def test_empty_issue_list_returns_explicit_marker(self):
        generator = QualityFixGenerator()
        assert generator._format_issues_list([]) == "无问题"


class TestBatchFixPublicSurface:
    """批量修正公开方法与拆分包入口测试"""

    def test_generator_exposes_batch_fix_methods(self):
        generator = QualityFixGenerator()
        assert callable(generator.generate_batch_fix)
        assert callable(generator._format_issues_list)
        assert callable(generator._parse_batch_llm_response)
        assert callable(generator._fallback_batch_fix)

    def test_quality_control_v2_common_exports_fix_entry(self):
        from app.api.v1.endpoints.novel_writer.quality_control_v2._common import (
            _generate_fixes_for_issues,
        )

        assert callable(_generate_fixes_for_issues)
