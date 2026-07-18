"""知识图谱与质控修正流程集成测试

覆盖当前生产接口：
1. KGQueryHelper：单例、路径生成、上下文格式化
2. 修正提示词模板包含知识图谱占位符
3. quality_control_v2 拆分包 _generate_fixes_for_issues：
   - 知识图谱查询参数与上下文融合传递
   - 知识图谱/修正生成异常时按契约降级（auto_fix=None）
"""
from types import SimpleNamespace

import pytest

from app.services.quality_control.kg_helper import KGQueryHelper, get_kg_helper
from app.services.quality_control.fix_generator import (
    BATCH_QUALITY_FIX_PROMPT_NOVEL,
    BATCH_QUALITY_FIX_PROMPT_SCRIPT,
    QUALITY_FIX_PROMPT_NOVEL,
    QUALITY_FIX_PROMPT_SCRIPT,
)
from app.api.v1.endpoints.novel_writer.quality_control_v2._common import (
    _generate_fixes_for_issues,
)


class TestKGQueryHelper:
    """知识图谱查询辅助函数测试"""

    def test_get_kg_helper_returns_singleton(self):
        assert get_kg_helper() is get_kg_helper()

    def test_global_graph_path_contains_project_identifier(self):
        helper = KGQueryHelper()
        path = helper.get_global_graph_path(123)
        assert "project_123_global_graph.json" in path

    def test_format_kg_context_renders_all_sections(self):
        helper = KGQueryHelper()
        kg_data = {
            "characters": [
                {"text": "张三", "type": "人物", "status": "存活", "description": "主角"},
                {"text": "李四", "type": "人物", "status": "受伤", "description": ""},
            ],
            "relationships": [
                {"source": "张三", "target": "李四", "relation": "朋友", "description": ""}
            ],
            "events": [{"text": "第一次相遇", "type": "事件"}],
            "foreshadows": [{"text": "神秘的信件", "type": "伏笔"}],
        }

        formatted = helper.format_kg_context(kg_data)

        assert "【当前人物状态】" in formatted
        assert "张三" in formatted
        assert "状态：存活" in formatted
        assert "【人物关系】" in formatted
        assert "张三 朋友 李四" in formatted
        assert "【已发生事件】" in formatted
        assert "【未回收伏笔】" in formatted


class TestFixPromptKGPlaceholder:
    """修正提示词知识图谱占位符测试"""

    @pytest.mark.parametrize(
        "template",
        [
            QUALITY_FIX_PROMPT_NOVEL,
            QUALITY_FIX_PROMPT_SCRIPT,
            BATCH_QUALITY_FIX_PROMPT_NOVEL,
            BATCH_QUALITY_FIX_PROMPT_SCRIPT,
        ],
        ids=["single_novel", "single_script", "batch_novel", "batch_script"],
    )
    def test_prompt_contains_kg_placeholder_and_consistency_hint(self, template):
        assert "{knowledge_graph_context}" in template
        assert "知识图谱上下文" in template
        assert "修正时必须保持一致" in template


class RecordingKGHelper:
    """记录调用参数的假知识图谱辅助器"""

    def __init__(self, raise_on_query: bool = False):
        self.query_calls = []
        self.raise_on_query = raise_on_query

    def query_relevant_entities(self, project_id, unit_index, issue_category, max_entities):
        if self.raise_on_query:
            raise RuntimeError("kg query failed")
        self.query_calls.append(
            {
                "project_id": project_id,
                "unit_index": unit_index,
                "issue_category": issue_category,
                "max_entities": max_entities,
            }
        )
        return {"characters": [{"text": "张三"}], "events": [], "relationships": [], "foreshadows": []}

    def format_kg_context(self, kg_data):
        return "KG-CTX::张三"


class RecordingFixGenerator:
    """记录 generate_batch_fix 入参的假修正生成器"""

    instances = []

    def __init__(self):
        self.batch_calls = []
        RecordingFixGenerator.instances.append(self)

    async def generate_batch_fix(self, **kwargs):
        self.batch_calls.append(kwargs)
        return {
            "fixed": "修正后的内容",
            "description": "综合修正",
            "changes_made": ["修改点"],
            "confidence": 0.9,
            "issues_addressed": [issue.get("id") for issue in kwargs["issues"]],
            "original": kwargs["chapter_content"],
            "tokens_used": 5,
            "type": "batch_llm_generated",
        }


@pytest.fixture
def fake_kg_and_generator(monkeypatch):
    """注入假 KG 辅助器与假修正生成器（mock 打在生产查找符号的位置）"""
    import app.services.quality_control.kg_helper as kg_helper_module
    import app.services.quality_control.fix_generator as fix_generator_module

    fake_helper = RecordingKGHelper()
    RecordingFixGenerator.instances = []
    monkeypatch.setattr(kg_helper_module, "get_kg_helper", lambda: fake_helper)
    monkeypatch.setattr(
        fix_generator_module, "QualityFixGenerator", RecordingFixGenerator
    )
    return fake_helper


def _build_issue(issue_id: str, chapter_number: int, category: str) -> dict:
    return {
        "id": issue_id,
        "category": category,
        "severity": "warning",
        "description": f"{category}描述",
        "location": {"chapter_number": chapter_number},
    }


def _build_project() -> SimpleNamespace:
    return SimpleNamespace(id=123, character_profiles=[], worldview_settings={})


class TestGenerateFixesKGFlow:
    """API 层 _generate_fixes_for_issues 知识图谱链路测试"""

    @pytest.mark.asyncio
    async def test_kg_query_params_and_context_forwarded_to_generator(
        self, fake_kg_and_generator
    ):
        issues = [
            _build_issue("issue_1", 2, "逻辑矛盾"),
            _build_issue("issue_2", 2, "节奏平淡"),
        ]
        chapters_data = [
            {"chapter_number": 1, "content": "第1单元内容", "summary": "概述1"},
            {"chapter_number": 2, "content": "第2单元内容", "summary": "概述2"},
        ]

        result = await _generate_fixes_for_issues(
            issues=issues,
            chapters_data=chapters_data,
            project=_build_project(),
            db=None,
            user_id=7,
            content_type="novel",
        )

        # 知识图谱查询参数
        assert len(fake_kg_and_generator.query_calls) == 1
        query_call = fake_kg_and_generator.query_calls[0]
        assert query_call["project_id"] == 123
        assert query_call["unit_index"] == 2
        assert query_call["issue_category"] == "逻辑矛盾"
        assert query_call["max_entities"] == 15

        # 修正生成器收到融合后的图谱上下文与章节内容
        generator = RecordingFixGenerator.instances[0]
        assert len(generator.batch_calls) == 1
        batch_call = generator.batch_calls[0]
        assert batch_call["knowledge_graph_context"] == "KG-CTX::张三"
        assert batch_call["chapter_content"] == "第2单元内容"
        assert batch_call["content_type"] == "novel"

        # 每个问题都融合了同一批量修正结果
        for issue in result:
            assert issue["auto_fix"] is not None
            assert issue["auto_fix"]["fixed"] == "修正后的内容"
            assert set(issue["auto_fix"]["issues_addressed"]) == {"issue_1", "issue_2"}

    @pytest.mark.asyncio
    async def test_kg_exception_degrades_issue_fix_to_none(self, monkeypatch):
        import app.services.quality_control.kg_helper as kg_helper_module
        import app.services.quality_control.fix_generator as fix_generator_module

        failing_helper = RecordingKGHelper(raise_on_query=True)
        RecordingFixGenerator.instances = []
        monkeypatch.setattr(kg_helper_module, "get_kg_helper", lambda: failing_helper)
        monkeypatch.setattr(
            fix_generator_module, "QualityFixGenerator", RecordingFixGenerator
        )

        issues = [_build_issue("issue_1", 1, "逻辑矛盾")]
        chapters_data = [{"chapter_number": 1, "content": "第1单元内容"}]

        result = await _generate_fixes_for_issues(
            issues=issues,
            chapters_data=chapters_data,
            project=_build_project(),
            db=None,
            user_id=7,
            content_type="novel",
        )

        assert result[0]["auto_fix"] is None, "知识图谱异常必须按契约降级为 auto_fix=None"
        generator = RecordingFixGenerator.instances[0]
        assert generator.batch_calls == [], "知识图谱异常后不得再调用修正生成器"
