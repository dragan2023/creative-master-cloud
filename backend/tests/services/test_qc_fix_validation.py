"""质控修正机制契约测试

直接测试 QualityFixGenerator 与 quality_control_v2 API 层的当前契约：
1. 不同内容类型选择正确的修正提示词
2. 空问题批次不调用模型
3. 模型异常按现有契约降级（批量→单个→静态降级），并保留原文
4. API 层将 content_type、单元概述传递给生成器；合规问题跳过修正
"""
from types import SimpleNamespace

import pytest

from app.services.quality_control.fix_generator import (
    QUALITY_FIX_PROMPT_NOVEL,
    QUALITY_FIX_PROMPT_SCRIPT,
    QualityFixGenerator,
)
from app.api.v1.endpoints.novel_writer.quality_control_v2._common import (
    _generate_fixes_for_issues,
)


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content
        self.usage = {"total_tokens": 42}


class FakeLLMProvider:
    """记录 prompt 的假 LLM 提供者；可配置为始终抛异常"""

    def __init__(self, payload: str = "", raise_error: bool = False):
        self.payload = payload
        self.raise_error = raise_error
        self.prompts = []

    async def generate(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        if self.raise_error:
            raise RuntimeError("llm unavailable")
        return FakeLLMResponse(self.payload)


class FakeLLMManager:
    def __init__(self, provider):
        self.provider = provider
        self.provider_requests = 0

    async def get_provider_from_db(self, db, user_id):
        self.provider_requests += 1
        return self.provider

    async def get_system_provider(self, name):
        self.provider_requests += 1
        return self.provider


BATCH_SUCCESS_PAYLOAD = """```json
{
  "fixed_content": "修正后的完整内容",
  "description": "综合修正说明",
  "changes_made": ["修改点1"],
  "confidence": 0.9,
  "issues_addressed": ["issue_1"]
}
```"""


def _build_generator(provider: FakeLLMProvider) -> QualityFixGenerator:
    generator = QualityFixGenerator()
    generator.llm_manager = FakeLLMManager(provider)
    return generator


def _build_issue(issue_id: str = "issue_1", category: str = "逻辑矛盾") -> dict:
    return {
        "id": issue_id,
        "category": category,
        "severity": "warning",
        "description": f"{category}描述",
        "location": {"chapter_number": 1},
    }


class TestPromptTemplateStructure:
    """单问题修正提示词结构测试"""

    @pytest.mark.parametrize(
        "template",
        [QUALITY_FIX_PROMPT_NOVEL, QUALITY_FIX_PROMPT_SCRIPT],
        ids=["novel", "script"],
    )
    def test_single_fix_prompt_contains_unit_summary_placeholder(self, template):
        assert "{unit_summary}" in template

    @pytest.mark.parametrize(
        "template",
        [QUALITY_FIX_PROMPT_NOVEL, QUALITY_FIX_PROMPT_SCRIPT],
        ids=["novel", "script"],
    )
    def test_single_fix_prompt_keeps_positive_principles(self, template):
        for principle in ["正向优化", "适度修改", "内容完整性", "灵活处理", "保持创造性"]:
            assert principle in template, f"提示词缺少修正原则: {principle}"

    @pytest.mark.parametrize(
        "template",
        [QUALITY_FIX_PROMPT_NOVEL, QUALITY_FIX_PROMPT_SCRIPT],
        ids=["novel", "script"],
    )
    def test_single_fix_prompt_has_no_forced_modification_directive(self, template):
        assert "你必须对原始内容进行具体的文本修改" not in template


class TestGenerateBatchFixContract:
    """QualityFixGenerator.generate_batch_fix 契约测试"""

    @pytest.mark.asyncio
    async def test_empty_issue_batch_skips_model_call(self):
        provider = FakeLLMProvider(BATCH_SUCCESS_PAYLOAD)
        generator = _build_generator(provider)

        result = await generator.generate_batch_fix(
            issues=[], chapter_content="原始内容"
        )

        assert result["type"] == "no_issues"
        assert result["fixed"] == "原始内容"
        assert result["confidence"] == 1.0
        assert result["issues_addressed"] == []
        assert provider.prompts == [], "空批次不得调用模型"
        assert generator.llm_manager.provider_requests == 0

    @pytest.mark.asyncio
    async def test_novel_type_renders_novel_prompt(self):
        provider = FakeLLMProvider(BATCH_SUCCESS_PAYLOAD)
        generator = _build_generator(provider)

        result = await generator.generate_batch_fix(
            issues=[_build_issue()],
            chapter_content="原始内容",
            content_type="novel",
        )

        assert result["type"] == "batch_llm_generated"
        assert result["fixed"] == "修正后的完整内容"
        assert len(provider.prompts) == 1
        rendered_prompt = provider.prompts[0]
        assert "专业的小说创作编辑" in rendered_prompt
        assert "内容完整性铁律" not in rendered_prompt, "novel 类型不得使用剧本模板"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content_type", ["series_script", "movie_script"])
    async def test_script_types_render_script_prompt(self, content_type):
        provider = FakeLLMProvider(BATCH_SUCCESS_PAYLOAD)
        generator = _build_generator(provider)

        await generator.generate_batch_fix(
            issues=[_build_issue()],
            chapter_content="原始内容",
            content_type=content_type,
        )

        rendered_prompt = provider.prompts[0]
        assert "专业的剧本创作编辑" in rendered_prompt
        assert "内容完整性铁律" in rendered_prompt

    @pytest.mark.asyncio
    async def test_model_exception_degrades_by_contract_and_keeps_original(self):
        """批量失败→单问题修正也失败→静态降级；原文必须保留且置信度降为低值"""
        provider = FakeLLMProvider(raise_error=True)
        generator = _build_generator(provider)

        result = await generator.generate_batch_fix(
            issues=[_build_issue(category="未知类别")],
            chapter_content="原始内容",
            content_type="novel",
        )

        # 契约：批量失败降级为单问题修正（fallback_single），
        # 单问题修正再失败时使用静态降级并保持原文
        assert result["type"] == "fallback_single"
        assert result["original"] == "原始内容"
        assert result["fixed"] == "原始内容"
        assert result["confidence"] == 0.0
        assert result["issues_addressed"] == ["issue_1"]
        # 批量调用 1 次 + 降级单问题调用 1 次
        assert len(provider.prompts) == 2


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
            "changes_made": [],
            "confidence": 0.9,
            "issues_addressed": [issue.get("id") for issue in kwargs["issues"]],
            "original": kwargs["chapter_content"],
            "tokens_used": 5,
            "type": "batch_llm_generated",
        }


class FakeKGHelper:
    def query_relevant_entities(self, **kwargs):
        return {"characters": [], "events": [], "relationships": [], "foreshadows": []}

    def format_kg_context(self, kg_data):
        return "空图谱"


@pytest.fixture
def api_fakes(monkeypatch):
    import app.services.quality_control.kg_helper as kg_helper_module
    import app.services.quality_control.fix_generator as fix_generator_module

    RecordingFixGenerator.instances = []
    monkeypatch.setattr(kg_helper_module, "get_kg_helper", lambda: FakeKGHelper())
    monkeypatch.setattr(
        fix_generator_module, "QualityFixGenerator", RecordingFixGenerator
    )
    return RecordingFixGenerator


class TestGenerateFixesForIssuesAPI:
    """API 层 _generate_fixes_for_issues 契约测试"""

    @pytest.mark.asyncio
    async def test_unit_summary_and_content_type_forwarded(self, api_fakes):
        issues = [_build_issue("issue_1")]
        chapters_data = [
            {
                "chapter_number": 1,
                "content": "第1单元正文",
                "unit_summary": "第1单元概述",
            }
        ]
        project = SimpleNamespace(id=9, character_profiles=[], worldview_settings={})

        result = await _generate_fixes_for_issues(
            issues=issues,
            chapters_data=chapters_data,
            project=project,
            db=None,
            user_id=3,
            content_type="series_script",
        )

        generator = api_fakes.instances[0]
        assert len(generator.batch_calls) == 1
        call = generator.batch_calls[0]
        assert call["content_type"] == "series_script"
        assert call["unit_summary"] == "第1单元概述"
        assert call["chapter_content"] == "第1单元正文"
        assert result[0]["auto_fix"]["type"] == "batch_llm_generated"

    @pytest.mark.asyncio
    async def test_compliance_issues_skip_fix_generation(self, api_fakes):
        compliance_issue = _build_issue("issue_c", "敏感内容")
        compliance_issue["is_compliance"] = True

        result = await _generate_fixes_for_issues(
            issues=[compliance_issue],
            chapters_data=[{"chapter_number": 1, "content": "第1单元正文"}],
            project=SimpleNamespace(id=9, character_profiles=[], worldview_settings={}),
            db=None,
            user_id=3,
            content_type="novel",
        )

        assert result[0]["auto_fix"] is None, "合规问题只提醒不自动修正"
        assert api_fakes.instances == [], "全部为合规问题时不得创建修正生成器"

    @pytest.mark.asyncio
    async def test_issue_without_chapter_content_degrades_to_none(self, api_fakes):
        """章节内容为空时按契约跳过修正并置 auto_fix=None"""
        issues = [_build_issue("issue_1")]
        chapters_data = [{"chapter_number": 1, "content": ""}]

        result = await _generate_fixes_for_issues(
            issues=issues,
            chapters_data=chapters_data,
            project=SimpleNamespace(id=9, character_profiles=[], worldview_settings={}),
            db=None,
            user_id=3,
            content_type="novel",
        )

        assert result[0]["auto_fix"] is None
        generator_calls = [
            call
            for generator in api_fakes.instances
            for call in generator.batch_calls
        ]
        assert generator_calls == [], "无内容章节不得调用修正生成器"
