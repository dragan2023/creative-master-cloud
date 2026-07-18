"""
单元概述生成接口测试（按当前实际接口重写）

历史背景:
- 旧版测试面向已删除的 generate_unit_summaries_batched / batch_mode 接口, 全部失效
- 当前实现的公开入口:
  * OutlineGenerator.generate_unit_summaries        (非流式, unit_summary_generate.py)
  * OutlineGenerator.generate_unit_summaries_stream (流式,   unit_summary_stream.py)

覆盖范围（修复计划 01 阶段 3.4）:
1. 接口契约: atomic_mode / existing_content / existing_parsed / start_from_unit /
   project_id / narrative_mode 参数真实存在, 旧 batch 接口确认已移除
2. 非流式路由: 原子化模式转发、legacy 模式生成、剧本类型自动禁用质控、QC 模式分支
3. 流式路由: 原子化转发参数透传、全新生成事件序列、续生成合并与防御性过滤、
   project_id 持久化
4. 异常路径: provider 缺失、解析失败、取消事件
"""
import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.outline_generator import OutlineGenerator


# ============================================================
# 测试辅助
# ============================================================

class FakeLLMResponse:
    """模拟非流式 LLM 响应"""

    def __init__(self, content: str, model: str = "fake-model"):
        self.content = content
        self.model = model


class FakeStreamProvider:
    """模拟流式 LLM 提供商"""

    model_name = "fake-model"

    def __init__(self, chunks):
        self._chunks = list(chunks)

    def get_model_info(self):
        return {"provider": "fake", "model": self.model_name}

    async def generate(self, prompt, temperature=0.5, **kwargs):
        return FakeLLMResponse("".join(self._chunks))

    async def generate_stream(self, prompt, temperature=0.5, **kwargs):
        for chunk in self._chunks:
            yield chunk


def make_generator(db=None) -> OutlineGenerator:
    """构造被测生成器, 隔离提示词与 LLM 管理器依赖"""
    generator = OutlineGenerator(db=db)
    generator.prompt_manager = MagicMock()
    generator.prompt_manager.get_default_prompt.return_value = "TEMPLATE"
    generator.prompt_manager.render_prompt.return_value = "RENDERED_PROMPT"
    generator.llm_manager = MagicMock()
    return generator


def attach_provider(generator, provider):
    """将假 provider 挂到 llm_manager 上"""
    generator.llm_manager.get_provider_from_db = AsyncMock(
        return_value=provider)


def parse_sse_events(raw_events):
    """将 SSE 字符串解析为 (event_type, data) 列表"""
    parsed = []
    for raw in raw_events:
        event_type = None
        data = None
        for line in raw.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):].strip()
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        parsed.append((event_type, data))
    return parsed


def workflow_payloads(events, wf_type=None):
    """筛选 workflow 事件负载"""
    return [
        data for etype, data in events
        if etype == "workflow" and (
            wf_type is None or data.get("type") == wf_type)
    ]


async def collect_stream(agen):
    """消费异步生成器为列表"""
    return [event async for event in agen]


# ============================================================
# 1. 接口契约
# ============================================================

class TestCurrentInterfaceContract:
    """当前公开接口的签名契约"""

    def test_generate_unit_summaries_signature_matches_current_interface(self):
        params = inspect.signature(
            OutlineGenerator.generate_unit_summaries).parameters
        for expected in (
            "global_outline", "unit_count", "content_type", "series_type",
            "episode_duration_range", "provider", "model", "temperature",
            "user_id", "enable_quality_control", "qc_mode",
            "title_style", "title_style_name", "atomic_mode", "project_id",
        ):
            assert expected in params, f"非流式接口缺少参数: {expected}"

    def test_stream_signature_supports_resume_atomic_and_narrative(self):
        params = inspect.signature(
            OutlineGenerator.generate_unit_summaries_stream).parameters
        for expected in (
            "existing_content", "existing_parsed", "start_from_unit",
            "atomic_mode", "project_id", "narrative_mode", "cancel_event",
        ):
            assert expected in params, f"流式接口缺少参数: {expected}"
        assert params["start_from_unit"].default == 1
        assert params["narrative_mode"].default == "serialized"

    def test_legacy_batched_interface_removed(self):
        assert not hasattr(OutlineGenerator, "generate_unit_summaries_batched"), \
            "旧的 generate_unit_summaries_batched 接口应已删除"
        stream_params = inspect.signature(
            OutlineGenerator.generate_unit_summaries_stream).parameters
        assert "batch_mode" not in stream_params
        assert "batch_size" not in stream_params


# ============================================================
# 2. 非流式路由
# ============================================================

class TestUnitQualityDimensionRegistry:
    """单元概述生成使用的质量维度必须在当前分析器注册表中真实存在"""

    UNIT_SUMMARY_DIMENSIONS = (
        "unit_structure", "unit_character", "unit_consistency",
        "unit_timeline_space", "unit_ooc",
    )

    def test_unit_summary_dimensions_resolve_to_registered_analyzers(self):
        from app.services.quality_control import QualityControlService

        service = QualityControlService(db=None)
        for dimension in self.UNIT_SUMMARY_DIMENSIONS:
            analyzer = service._get_analyzer(dimension)
            assert analyzer is not None, f"维度 {dimension} 未注册分析器"
            assert analyzer.__class__.__name__.startswith(
                ("Unit",)), f"维度 {dimension} 解析到了非单元分析器"

    def test_unknown_dimension_raises_value_error(self):
        from app.services.quality_control import QualityControlService

        service = QualityControlService(db=None)
        with pytest.raises(ValueError):
            service._get_analyzer("batched_legacy_dimension")


class TestGenerateUnitSummariesRouting:
    """generate_unit_summaries 的原子化/legacy 路由与质控分支"""

    @pytest.mark.asyncio
    async def test_atomic_mode_routes_to_atomic_generator_with_forwarded_parameters(self):
        generator = make_generator(db=MagicMock())
        provider = FakeStreamProvider([])
        attach_provider(generator, provider)
        generator.generate_all_chapters_atomic = AsyncMock(return_value={
            "success": True,
            "parsed": {"1": {"title": "第1章", "summary": "S1"}},
        })

        result = await generator.generate_unit_summaries(
            global_outline="全局大纲",
            unit_count=3,
            content_type="novel",
            provider="openai",
            user_id=9,
            enable_quality_control=False,
            atomic_mode=True,
            project_id=77,
        )

        assert result["success"] is True
        forwarded = generator.generate_all_chapters_atomic.await_args.kwargs
        assert forwarded["global_outline"] == "全局大纲"
        assert forwarded["unit_count"] == 3
        assert forwarded["project_id"] == 77
        assert forwarded["start_from_unit"] == 1
        assert forwarded["existing_parsed"] is None
        assert forwarded["llm_provider"] is provider
        assert result["quality_control_enabled"] is False

    @pytest.mark.asyncio
    async def test_atomic_mode_auto_qc_attaches_quality_report(self):
        generator = make_generator(db=MagicMock())
        attach_provider(generator, FakeStreamProvider([]))
        generator.generate_all_chapters_atomic = AsyncMock(return_value={
            "success": True,
            "parsed": {"1": {"title": "第1章", "summary": "S1",
                             "full_content": "F1"}},
        })
        quality_report = {"issues": [], "overall_score": 92}
        generator._analyze_unit_summaries_quality = AsyncMock(
            return_value=quality_report)

        result = await generator.generate_unit_summaries(
            global_outline="大纲",
            unit_count=1,
            content_type="novel",
            enable_quality_control=True,
            qc_mode="auto",
            atomic_mode=True,
        )

        assert result["quality_control"] == quality_report
        assert result["qc_mode"] == "auto"
        qc_kwargs = generator._analyze_unit_summaries_quality.await_args.kwargs
        assert qc_kwargs["depth"] == "deep"
        assert qc_kwargs["dimensions"] == [
            "unit_structure", "unit_character", "unit_consistency",
            "unit_timeline_space", "unit_ooc"]
        assert qc_kwargs["chapters_data"][0]["chapter_number"] == 1

    @pytest.mark.asyncio
    async def test_atomic_mode_manual_qc_skips_quality_analysis(self):
        generator = make_generator(db=MagicMock())
        attach_provider(generator, FakeStreamProvider([]))
        generator.generate_all_chapters_atomic = AsyncMock(return_value={
            "success": True,
            "parsed": {"1": {"title": "第1章", "summary": "S1"}},
        })
        generator._analyze_unit_summaries_quality = AsyncMock()

        result = await generator.generate_unit_summaries(
            global_outline="大纲",
            unit_count=1,
            content_type="novel",
            enable_quality_control=True,
            qc_mode="manual",
            atomic_mode=True,
        )

        assert result["qc_mode"] == "manual"
        assert result["quality_control"] is None
        generator._analyze_unit_summaries_quality.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_script_content_type_disables_auto_quality_control(self):
        generator = make_generator(db=MagicMock())
        attach_provider(generator, FakeStreamProvider([]))
        generator.generate_all_chapters_atomic = AsyncMock(return_value={
            "success": True,
            "parsed": {"1": {"title": "第1集", "summary": "S1"}},
        })
        generator._analyze_unit_summaries_quality = AsyncMock()

        result = await generator.generate_unit_summaries(
            global_outline="大纲",
            unit_count=1,
            content_type="series_script",
            enable_quality_control=True,
            qc_mode="auto",
            atomic_mode=True,
        )

        assert result["success"] is True
        generator._analyze_unit_summaries_quality.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_legacy_mode_generates_content_and_parses_units(self):
        generator = make_generator(db=MagicMock())
        provider = FakeStreamProvider(["第1章 标题A\n梗概：内容A"])
        attach_provider(generator, provider)
        parsed_units = {
            "1": {"unit_number": 1, "title": "标题A", "summary": "内容A"}}
        generator.parse_unit_summaries = MagicMock(return_value=parsed_units)

        result = await generator.generate_unit_summaries(
            global_outline="全局大纲",
            unit_count=1,
            content_type="novel",
            provider="openai",
            enable_quality_control=False,
            atomic_mode=False,
        )

        assert result["success"] is True
        assert result["parsed"] == parsed_units
        assert result["content"] == "第1章 标题A\n梗概：内容A"
        assert result["provider"] == "openai"
        assert result["model"] == "fake-model"
        parse_args = generator.parse_unit_summaries.call_args.args
        assert parse_args[1] == 1
        assert parse_args[2] == "novel"

    @pytest.mark.asyncio
    async def test_legacy_mode_reports_error_when_provider_missing(self):
        generator = make_generator(db=MagicMock())
        generator.llm_manager.get_provider_from_db = AsyncMock(
            return_value=None)

        result = await generator.generate_unit_summaries(
            global_outline="大纲",
            unit_count=2,
            content_type="novel",
            provider="ghost",
            enable_quality_control=False,
            atomic_mode=False,
        )

        assert result["success"] is False
        assert "未找到LLM提供商" in result["error"]


# ============================================================
# 3. 流式原子化转发
# ============================================================

class TestGenerateUnitSummariesStreamAtomic:
    """流式接口在原子化模式下的参数透传"""

    @pytest.mark.asyncio
    async def test_atomic_stream_forwards_parameters_and_passes_events_through(self):
        generator = make_generator(db=MagicMock())
        provider = FakeStreamProvider([])
        attach_provider(generator, provider)

        captured = {}

        async def fake_atomic_stream(**kwargs):
            captured.update(kwargs)
            yield "event: unit_start\ndata: {\"unit\": 1}\n\n"
            yield "event: complete\ndata: {}\n\n"

        generator.generate_all_chapters_atomic_stream = fake_atomic_stream
        existing = {"1": {"title": "已有"}}
        cancel_event = object()

        raw_events = await collect_stream(
            generator.generate_unit_summaries_stream(
                global_outline="大纲",
                unit_count=4,
                content_type="novel",
                user_id=5,
                atomic_mode=True,
                project_id=7,
                narrative_mode="episodic",
                existing_parsed=existing,
                start_from_unit=2,
                cancel_event=cancel_event,
            ))

        assert captured["narrative_mode"] == "episodic"
        assert captured["project_id"] == 7
        assert captured["start_from_unit"] == 2
        assert captured["existing_parsed"] == existing
        assert captured["cancel_event"] is cancel_event
        assert captured["llm_provider"] is provider
        assert raw_events == [
            "event: unit_start\ndata: {\"unit\": 1}\n\n",
            "event: complete\ndata: {}\n\n",
        ]


# ============================================================
# 4. 流式 legacy 模式（全新生成 / 续生成 / 异常路径）
# ============================================================

class TestGenerateUnitSummariesStreamLegacy:
    """流式接口在非原子化模式下的事件序列与合并逻辑"""

    @staticmethod
    def _make_db_with_project():
        fake_project = MagicMock()
        fake_result = MagicMock()
        fake_result.scalar_one_or_none.return_value = fake_project
        db = MagicMock()
        db.execute = AsyncMock(return_value=fake_result)
        db.commit = AsyncMock()
        return db, fake_project

    @pytest.mark.asyncio
    async def test_full_generation_emits_complete_event_sequence(self):
        generator = make_generator(db=MagicMock())
        chunks = ["第1章 标题A\n梗概：内容A\n", "第2章 标题B\n梗概：内容B\n"]
        attach_provider(generator, FakeStreamProvider(chunks))
        generator.parse_unit_summaries = MagicMock(return_value={
            "1": {"title": "标题A", "summary": "内容A"},
            "2": {"title": "标题B", "summary": "内容B"},
        })

        events = parse_sse_events(await collect_stream(
            generator.generate_unit_summaries_stream(
                global_outline="大纲",
                unit_count=2,
                content_type="novel",
                enable_quality_control=False,
                atomic_mode=False,
            )))

        generate_steps = [
            data for data in workflow_payloads(events, "step")
            if data.get("step") == "generate"]
        assert [step["status"] for step in generate_steps] == [
            "running", "done"]
        content_texts = [
            data["text"] for etype, data in events if etype == "content"]
        assert content_texts == chunks
        assert workflow_payloads(events, "qc_hint"), "应发送质控手动触发提示"
        assert workflow_payloads(events, "complete"), "应发送完成事件"
        assert not workflow_payloads(events, "error")

    @pytest.mark.asyncio
    async def test_resume_mode_merges_existing_units_and_filters_invalid_numbers(self):
        db, fake_project = self._make_db_with_project()
        generator = make_generator(db=db)
        attach_provider(
            generator, FakeStreamProvider(["第3章 新标题\n梗概：新内容\n"]))
        generator._build_resume_context = MagicMock(return_value="CTX")
        generator._build_resume_prompt = MagicMock(return_value="RESUME_PROMPT")
        existing_parsed = {
            "1": {"title": "旧1", "summary": "旧S1"},
            "2": {"title": "旧2", "summary": "旧S2"},
        }
        # 新解析结果: "2"重复(应跳过), "3"-"5"有效, "6"越界(应跳过)
        generator.parse_unit_summaries = MagicMock(return_value={
            "2": {"title": "重复2", "summary": "X"},
            "3": {"title": "新3", "summary": "S3"},
            "4": {"title": "新4", "summary": "S4"},
            "5": {"title": "新5", "summary": "S5"},
            "6": {"title": "越界6", "summary": "S6"},
        })

        events = parse_sse_events(await collect_stream(
            generator.generate_unit_summaries_stream(
                global_outline="大纲",
                unit_count=5,
                content_type="novel",
                enable_quality_control=False,
                atomic_mode=False,
                existing_content="已有内容",
                existing_parsed=existing_parsed,
                start_from_unit=3,
                project_id=42,
                narrative_mode="episodic",
            )))

        resume_steps = [
            data for data in workflow_payloads(events, "step")
            if data.get("step") == "resume_detection"]
        assert resume_steps, "续生成模式应发送 resume_detection 事件"
        prompt_kwargs = generator._build_resume_prompt.call_args.kwargs
        assert prompt_kwargs["start_from_unit"] == 3
        assert prompt_kwargs["narrative_mode"] == "episodic"
        context_kwargs = generator._build_resume_context.call_args.kwargs
        assert context_kwargs["existing_parsed"] == existing_parsed

        merged = fake_project.unit_summaries
        assert set(merged.keys()) == {"1", "2", "3", "4", "5"}
        assert merged["2"]["title"] == "旧2", "重复章节应保留已有内容"
        assert merged["3"]["is_resumed"] is True
        assert merged["5"]["is_resumed"] is True
        db.commit.assert_awaited()
        assert workflow_payloads(events, "complete")

    @pytest.mark.asyncio
    async def test_full_generation_saves_parsed_units_to_project(self):
        db, fake_project = self._make_db_with_project()
        generator = make_generator(db=db)
        attach_provider(
            generator, FakeStreamProvider(["第1章 标题\n梗概：内容\n"]))
        parsed_units = {"1": {"title": "标题", "summary": "内容"}}
        generator.parse_unit_summaries = MagicMock(return_value=parsed_units)

        events = parse_sse_events(await collect_stream(
            generator.generate_unit_summaries_stream(
                global_outline="大纲",
                unit_count=1,
                content_type="novel",
                enable_quality_control=False,
                atomic_mode=False,
                project_id=11,
            )))

        assert fake_project.unit_summaries == parsed_units
        db.commit.assert_awaited()
        assert workflow_payloads(events, "complete")

    @pytest.mark.asyncio
    async def test_parse_failure_emits_error_event(self):
        generator = make_generator(db=MagicMock())
        attach_provider(generator, FakeStreamProvider(["无法解析的输出"]))
        generator.parse_unit_summaries = MagicMock(return_value={})

        events = parse_sse_events(await collect_stream(
            generator.generate_unit_summaries_stream(
                global_outline="大纲",
                unit_count=2,
                content_type="novel",
                enable_quality_control=False,
                atomic_mode=False,
            )))

        errors = workflow_payloads(events, "error")
        assert errors, "解析失败应发送 error 事件"
        assert "解析失败" in errors[0]["message"]
        assert not workflow_payloads(events, "complete"), \
            "解析失败后不应发送 complete 事件"

    @pytest.mark.asyncio
    async def test_cancel_event_emits_cancelled_event(self):
        import threading

        generator = make_generator(db=MagicMock())
        attach_provider(
            generator, FakeStreamProvider(["chunk-1", "chunk-2"]))
        generator.parse_unit_summaries = MagicMock(return_value={})
        cancel_event = threading.Event()
        cancel_event.set()

        events = parse_sse_events(await collect_stream(
            generator.generate_unit_summaries_stream(
                global_outline="大纲",
                unit_count=2,
                content_type="novel",
                enable_quality_control=False,
                atomic_mode=False,
                cancel_event=cancel_event,
            )))

        assert workflow_payloads(events, "cancelled"), \
            "取消后应发送 cancelled 事件"
        content_texts = [
            data for etype, data in events if etype == "content"]
        assert content_texts == [], "取消后不应继续输出内容"

    @pytest.mark.asyncio
    async def test_provider_missing_emits_error_event(self):
        generator = make_generator(db=MagicMock())
        generator.llm_manager.get_provider_from_db = AsyncMock(
            return_value=None)

        events = parse_sse_events(await collect_stream(
            generator.generate_unit_summaries_stream(
                global_outline="大纲",
                unit_count=2,
                content_type="novel",
                enable_quality_control=False,
                atomic_mode=False,
            )))

        errors = workflow_payloads(events, "error")
        assert errors, "provider 缺失应发送 error 事件"
        assert "生成失败" in errors[0]["message"]
