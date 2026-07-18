"""三维质控 v2.0 正式测试

覆盖当前生产接口：
1. FeedbackLearningManager：反馈记录、误报率、阈值调整、统计与文件持久化（tmp_path 隔离）
2. CrossValidationEngine.validate_all：问题结构、维度得分、综合得分与元数据
3. SmartSuggestionEngine.generate_suggestions：问题增强字段
4. 单元质量分析器（结构/人物/一致性）与可控假 LLM 的集成
"""
import json

import pytest

from app.services.quality_control.analyzers.feedback_learning import (
    FeedbackLearningManager,
)
from app.services.quality_control.analyzers.cross_validation import (
    get_cross_validation_engine,
)
from app.services.quality_control.analyzers.smart_suggestions import (
    get_smart_suggestion_engine,
)
from app.services.quality_control.analyzers.unit_quality_analyzer import (
    UnitCharacterAnalyzer,
    UnitConsistencyAnalyzer,
    UnitStructureAnalyzer,
)


TEST_USER_ID = 999


@pytest.fixture
def isolated_feedback_manager(tmp_path):
    """使用 tmp_path 隔离反馈数据目录，避免写入项目真实数据目录"""
    return FeedbackLearningManager(data_dir=str(tmp_path / "feedback_learning"))


class TestFeedbackLearning:
    """用户反馈学习模块测试（数据目录已隔离）"""

    def test_record_feedback_returns_entry_and_persists_file(
        self, isolated_feedback_manager, tmp_path
    ):
        feedback = isolated_feedback_manager.record_feedback(
            user_id=TEST_USER_ID,
            project_id=1,
            issue_id="UL-1",
            dimension="unit_structure",
            category="单元过短",
            feedback_type="false_positive",
            comment="测试反馈",
        )

        assert feedback.feedback_id.startswith("FB-")
        assert feedback.user_id == TEST_USER_ID
        assert feedback.feedback_type == "false_positive"

        feedback_file = (
            tmp_path / "feedback_learning" / f"user_{TEST_USER_ID}_feedback.json"
        )
        assert feedback_file.exists(), "反馈必须持久化到隔离目录"
        persisted = json.loads(feedback_file.read_text(encoding="utf-8"))
        assert len(persisted) == 1
        assert persisted[0]["issue_id"] == "UL-1"
        assert persisted[0]["feedback_type"] == "false_positive"

    def test_false_positive_rate_reflects_recorded_feedback(
        self, isolated_feedback_manager
    ):
        """样本量达到 3 条后，误报率按时间加权比例计算（近期反馈权重几乎相同）"""
        for feedback_type in (
            "false_positive",
            "false_positive",
            "accepted",
            "accepted",
        ):
            isolated_feedback_manager.record_feedback(
                user_id=TEST_USER_ID,
                project_id=1,
                issue_id=f"UL-{feedback_type}",
                dimension="unit_structure",
                category="单元过短",
                feedback_type=feedback_type,
            )

        rate = isolated_feedback_manager.get_false_positive_rate(
            user_id=TEST_USER_ID,
            dimension="unit_structure",
            category="单元过短",
        )
        assert rate == pytest.approx(0.5, rel=1e-3)

    def test_false_positive_rate_small_sample_returns_conservative_value(
        self, isolated_feedback_manager
    ):
        """生产契约：相关反馈少于 3 条时返回保守值 0.2"""
        isolated_feedback_manager.record_feedback(
            user_id=TEST_USER_ID,
            project_id=1,
            issue_id="UL-1",
            dimension="unit_structure",
            category="单元过短",
            feedback_type="false_positive",
        )

        rate = isolated_feedback_manager.get_false_positive_rate(
            user_id=TEST_USER_ID,
            dimension="unit_structure",
            category="单元过短",
        )
        assert rate == pytest.approx(0.2)

    def test_false_positive_rate_without_feedback_is_zero(
        self, isolated_feedback_manager
    ):
        rate = isolated_feedback_manager.get_false_positive_rate(
            user_id=TEST_USER_ID,
            dimension="unit_structure",
            category="不存在的分类",
        )
        assert rate == 0.0

    def test_false_positive_feedback_raises_threshold(
        self, isolated_feedback_manager
    ):
        base_threshold = 0.3
        before = isolated_feedback_manager.get_adjusted_threshold(
            dimension="unit_structure",
            category="单元过短",
            base_threshold=base_threshold,
        )
        assert before == pytest.approx(base_threshold)

        isolated_feedback_manager.record_feedback(
            user_id=TEST_USER_ID,
            project_id=1,
            issue_id="UL-1",
            dimension="unit_structure",
            category="单元过短",
            feedback_type="false_positive",
        )

        after = isolated_feedback_manager.get_adjusted_threshold(
            dimension="unit_structure",
            category="单元过短",
            base_threshold=base_threshold,
        )
        assert after == pytest.approx(base_threshold + 0.05)

    def test_learning_statistics_counts_all_feedback(
        self, isolated_feedback_manager
    ):
        for index in range(3):
            isolated_feedback_manager.record_feedback(
                user_id=TEST_USER_ID,
                project_id=1,
                issue_id=f"UL-{index}",
                dimension="unit_structure",
                category="单元过短",
                feedback_type="accepted",
            )

        stats = isolated_feedback_manager.get_learning_statistics(
            user_id=TEST_USER_ID
        )
        assert stats["total_feedbacks"] == 3
        assert stats["dimensions"]["unit_structure"]["accepted"] == 3


class TestCrossValidation:
    """多维度交叉验证引擎测试（纯规则，无 LLM 依赖）"""

    @pytest.mark.asyncio
    async def test_validate_all_returns_scores_issues_and_metadata(self):
        engine = get_cross_validation_engine()
        chapters_data = [
            {"chapter_number": index, "content": f"第{index}单元内容，包含一些情节描述"}
            for index in range(1, 11)
        ]

        result = await engine.validate_all(
            chapters_data=chapters_data,
            global_outline="这是一个关于主角成长的故事，包含决战、转折和觉醒",
            character_profiles=[
                {"name": "主角", "abilities": ["火球术"], "personality": ["勇敢"]}
            ],
            worldview_settings={"rules": ["魔法需要吟唱"]},
            depth="standard",
            db=None,
            user_id=TEST_USER_ID,
        )

        assert isinstance(result["issues"], list)
        for issue in result["issues"]:
            assert issue.get("severity"), "每个问题必须带有严重度"
            assert issue.get("description"), "每个问题必须带有描述"
        assert result["total_validations"] == 4
        assert 0.0 <= result["overall_score"] <= 100.0
        for score in result["validation_scores"].values():
            assert 0.0 <= score <= 100.0
        assert result["metadata"]["total_units"] == 10
        assert result["metadata"]["has_global_outline"] is True

    @pytest.mark.asyncio
    async def test_validate_all_without_optional_inputs_skips_dimensions(self):
        engine = get_cross_validation_engine()
        chapters_data = [
            {"chapter_number": index, "content": f"第{index}单元内容"}
            for index in range(1, 4)
        ]

        result = await engine.validate_all(chapters_data=chapters_data)

        assert "character_worldview_consistency" not in result["validation_scores"]
        assert "plot_outline_consistency" not in result["validation_scores"]
        assert result["metadata"]["has_global_outline"] is False


class TestSmartSuggestions:
    """智能修正建议引擎测试"""

    def test_generate_suggestions_enriches_every_issue(self):
        engine = get_smart_suggestion_engine()
        issues = [
            {
                "id": "UL-1",
                "dimension": "unit_structure",
                "category": "单元过短",
                "severity": "warning",
                "location": {"chapter_number": 1},
                "description": "第1单元概述仅30字，内容过于简略",
                "evidence": "这是很短的内容",
                "suggestion": "建议补充关键情节要素",
                "metadata": {"length": 30},
            },
            {
                "id": "UT-1",
                "dimension": "unit_structure",
                "category": "单元衔接",
                "severity": "info",
                "location": {"chapter_number": 2},
                "description": "第2单元与第3单元之间的衔接可能不够流畅",
                "evidence": "两个单元都较短",
                "suggestion": "建议增加逻辑关联词",
                "metadata": {},
            },
        ]
        chapters_data = [
            {"chapter_number": index, "content": f"第{index}单元的内容描述"}
            for index in range(1, 6)
        ]

        enhanced = engine.generate_suggestions(
            issues=issues, chapters_data=chapters_data
        )

        assert len(enhanced) == 2
        for issue in enhanced:
            assert issue.get("priority"), "每个问题必须生成优先级"
            assert issue.get("fix_difficulty"), "每个问题必须生成修正难度"
            assert issue.get("suggestion"), "每个问题必须保留修复建议"


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content
        self.usage = {"total_tokens": 10}


class FakeLLMProvider:
    """返回固定结构化 JSON 的假 LLM 提供者（不访问网络）"""

    def __init__(self, payload: str):
        self.payload = payload
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs):
        self.call_count += 1
        return FakeLLMResponse(self.payload)


class FakeLLMManager:
    def __init__(self, provider):
        self.provider = provider

    async def get_provider_from_db(self, db, user_id):
        return self.provider


LENGTH_ISSUE_PAYLOAD = """```json
{
  "length_issues": [
    {
      "unit_number": 1,
      "issue_type": "过短",
      "description": "第1单元概述过短，信息不足",
      "severity": "warning"
    }
  ]
}
```"""


class TestUnitAnalyzerIntegration:
    """单元质量分析器与假 LLM 的集成测试"""

    @pytest.fixture
    def fake_llm(self, monkeypatch):
        import importlib

        # app.agents 包属性 llm_manager（LLMManager 实例）会遮蔽子模块名，
        # 必须通过 importlib 拿到真正的模块对象后再打补丁
        llm_manager_module = importlib.import_module("app.agents.llm_manager")

        provider = FakeLLMProvider(LENGTH_ISSUE_PAYLOAD)
        manager = FakeLLMManager(provider)
        monkeypatch.setattr(llm_manager_module, "get_llm_manager", lambda: manager)
        return provider

    @pytest.fixture
    def sample_chapters(self):
        return [
            {
                "id": index,
                "chapter_number": index,
                "content": f"第{index}单元的详细内容包括冲突和转折",
            }
            for index in range(1, 6)
        ]

    @pytest.fixture
    def sample_project(self):
        class ProjectStub:
            id = 1
            title = "测试项目"

        return ProjectStub()

    @pytest.mark.asyncio
    async def test_structure_analyzer_reports_llm_detected_issue(
        self, fake_llm, sample_chapters, sample_project
    ):
        analyzer = UnitStructureAnalyzer()
        result = await analyzer.analyze(
            chapters_data=sample_chapters,
            project=sample_project,
            depth="standard",
            db=None,
            user_id=TEST_USER_ID,
        )

        assert fake_llm.call_count > 0, "分析器必须调用（假）LLM"
        assert 0.0 <= result["score"] <= 100.0
        length_issues = [
            issue
            for issue in result["issues"]
            if issue.get("category") == "过短"
        ]
        assert len(length_issues) == 1, "假 LLM 注入的问题必须出现在结果中"
        detected = length_issues[0]
        assert detected["severity"] == "warning"
        assert detected["suggestion"], "问题必须携带修复建议"
        assert detected["location"]["chapter_number"] == 1

    @pytest.mark.asyncio
    async def test_character_analyzer_returns_score_and_issue_list(
        self, fake_llm, sample_chapters, sample_project
    ):
        analyzer = UnitCharacterAnalyzer()
        result = await analyzer.analyze(
            chapters_data=sample_chapters,
            project=sample_project,
            depth="standard",
            db=None,
            user_id=TEST_USER_ID,
        )

        assert 0.0 <= result["score"] <= 100.0
        assert isinstance(result["issues"], list)

    @pytest.mark.asyncio
    async def test_consistency_analyzer_returns_score_and_issue_list(
        self, fake_llm, sample_chapters, sample_project
    ):
        analyzer = UnitConsistencyAnalyzer()
        result = await analyzer.analyze(
            chapters_data=sample_chapters,
            project=sample_project,
            global_outline="这是一个包含主角成长和决战的故事",
            character_profiles=[{"name": "主角", "abilities": []}],
            worldview_settings={"rules": []},
            depth="standard",
            db=None,
            user_id=TEST_USER_ID,
        )

        assert 0.0 <= result["score"] <= 100.0
        assert isinstance(result["issues"], list)
