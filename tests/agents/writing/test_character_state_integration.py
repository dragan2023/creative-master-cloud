"""
多Agent协作文学作品生成系统 - 人物状态集成测试

模块: tests.agents.writing
文件: test_character_state_integration.py
功能: 测试人物状态更新功能与多agent正文生成系统的集成

创建时间: 2026-04-01
最后修改: 2026-04-01
版本: 1.0.0
作者: AI Assistant
"""
import pytest
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch

from app.agents.writing.base_agent import AgentContext, AgentResult
from app.agents.writing.character_state_tracker import (
    CharacterStateTracker,
    CharacterState,
    CharacterStatus,
    ChapterSnapshot
)
from app.agents.writing.character_state_interface import (
    CharacterStateInterface,
    CharacterStateData,
    create_character_state_interface
)


class TestCharacterStateTracker:
    """人物状态追踪器测试"""
    
    @pytest.fixture
    def tracker(self):
        """创建追踪器实例"""
        return CharacterStateTracker(project_id=1)
    
    @pytest.fixture
    def sample_profiles(self) -> List[Dict[str, Any]]:
        """示例人物设定"""
        return [
            {
                "name": "沈无衣",
                "identity": "监察御史",
                "location": "京城",
                "personality": "沉稳内敛",
                "background": "出身寒门，凭借才学入仕"
            },
            {
                "name": "苏映雪",
                "identity": "太傅之女",
                "location": "苏府",
                "personality": "聪慧机敏"
            }
        ]
    
    @pytest.mark.asyncio
    async def test_initialize(self, tracker, sample_profiles):
        """测试初始化"""
        await tracker.initialize(sample_profiles)
        
        assert tracker._initialized is True
        assert len(tracker._character_states) == 2
        assert "沈无衣" in tracker._character_states
        assert "苏映雪" in tracker._character_states
    
    @pytest.mark.asyncio
    async def test_get_character_state(self, tracker, sample_profiles):
        """测试获取人物状态"""
        await tracker.initialize(sample_profiles)
        
        state = tracker.get_character_state("沈无衣")
        assert state is not None
        assert state.identity == "监察御史"
        assert state.location == "京城"
    
    @pytest.mark.asyncio
    async def test_update_character_state(self, tracker, sample_profiles):
        """测试更新人物状态"""
        await tracker.initialize(sample_profiles)
        
        tracker.update_character_state(
            name="沈无衣",
            updates={
                "location": "江南",
                "status_change": "奉命出巡江南"
            },
            chapter_num=1
        )
        
        state = tracker.get_character_state("沈无衣")
        assert state.location == "江南"
        assert state.status_change == "奉命出巡江南"
    
    @pytest.mark.asyncio
    async def test_record_chapter_snapshot(self, tracker, sample_profiles):
        """测试记录章节快照"""
        await tracker.initialize(sample_profiles)
        
        content = "沈无衣来到江南，见到了苏映雪。"
        snapshot = tracker.record_chapter_snapshot(
            chapter_num=1,
            chapter_title="初遇",
            content=content,
            characters_present=["沈无衣", "苏映雪"]
        )
        
        assert snapshot.chapter_num == 1
        assert snapshot.chapter_title == "初遇"
        assert "沈无衣" in snapshot.characters
        assert "苏映雪" in snapshot.characters
    
    @pytest.mark.asyncio
    async def test_detect_new_characters(self, tracker, sample_profiles):
        """测试检测新人物"""
        await tracker.initialize(sample_profiles)
        
        content = '''
        沈无衣走进茶楼，只见一个青衣女子正在窗边品茶。
        青衣女子抬起头，笑道："大人来得正好。"
        '''
        
        new_chars = tracker.detect_new_characters(content)
        assert isinstance(new_chars, list)
    
    @pytest.mark.asyncio
    async def test_get_state_for_prompt(self, tracker, sample_profiles):
        """测试获取状态提示词"""
        await tracker.initialize(sample_profiles)
        
        state_text = tracker.get_state_for_prompt()
        
        assert "沈无衣" in state_text
        assert "监察御史" in state_text
        assert "京城" in state_text
    
    @pytest.mark.asyncio
    async def test_get_relationship_summary(self, tracker, sample_profiles):
        """测试获取关系摘要"""
        await tracker.initialize(sample_profiles)
        
        tracker.add_relationship_change(
            chapter_num=1,
            char1="沈无衣",
            char2="苏映雪",
            relationship_type="知己",
            previous_state="陌生人",
            new_state="相识",
            description="茶楼初遇"
        )
        
        summary = tracker.get_relationship_summary()
        assert "沈无衣" in summary
        assert "苏映雪" in summary


class TestCharacterStateInterface:
    """人物状态接口测试"""
    
    @pytest.fixture
    def tracker(self):
        """创建追踪器实例"""
        tracker = CharacterStateTracker(project_id=1)
        return tracker
    
    @pytest.fixture
    def interface(self, tracker):
        """创建接口实例"""
        return CharacterStateInterface(tracker=tracker)
    
    @pytest.fixture
    def sample_profiles(self) -> List[Dict[str, Any]]:
        """示例人物设定"""
        return [
            {
                "name": "沈无衣",
                "identity": "监察御史",
                "location": "京城",
                "personality": "沉稳内敛"
            },
            {
                "name": "苏映雪",
                "identity": "太傅之女",
                "location": "苏府",
                "personality": "聪慧机敏"
            }
        ]
    
    @pytest.mark.asyncio
    async def test_get_state_data_for_context(self, interface, tracker, sample_profiles):
        """测试获取上下文状态数据"""
        await tracker.initialize(sample_profiles)
        
        data = interface.get_state_data_for_context(chapter_num=1)
        
        assert isinstance(data, CharacterStateData)
        assert len(data.character_states) == 2
        assert "沈无衣" in data.character_location_map
        assert "苏映雪" in data.character_identity_map
    
    def test_extract_state_updates_from_result(self, interface):
        """测试从结果提取状态更新"""
        editor_result = {
            "data": {
                "character_state_updates": [
                    {
                        "character": "沈无衣",
                        "updates": {
                            "location": "江南",
                            "status_change": "奉命出巡"
                        },
                        "evidence": "沈无衣奉命前往江南查案"
                    }
                ],
                "new_characters": [
                    {
                        "name": "李青衣",
                        "identity": "江湖侠客",
                        "location": "江南"
                    }
                ]
            }
        }
        
        updates = interface.extract_state_updates_from_result(editor_result)
        
        assert len(updates["character_state_updates"]) == 1
        assert len(updates["new_characters"]) == 1
        assert updates["character_state_updates"][0]["character"] == "沈无衣"
    
    @pytest.mark.asyncio
    async def test_apply_state_updates(self, interface, tracker, sample_profiles):
        """测试应用状态更新"""
        await tracker.initialize(sample_profiles)
        
        updates = {
            "character_state_updates": [
                {
                    "character": "沈无衣",
                    "updates": {
                        "location": "江南",
                        "status_change": "奉命出巡"
                    }
                }
            ],
            "new_characters": [
                {
                    "name": "李青衣",
                    "identity": "江湖侠客",
                    "location": "江南"
                }
            ],
            "relationship_changes": []
        }
        
        result = interface.apply_state_updates(updates, chapter_num=2)
        
        assert result is True
        
        state = tracker.get_character_state("沈无衣")
        assert state.location == "江南"
        
        new_char = tracker.get_character_state("李青衣")
        assert new_char is not None
        assert new_char.identity == "江湖侠客"
    
    @pytest.mark.asyncio
    async def test_get_character_location_context(self, interface, tracker, sample_profiles):
        """测试获取人物位置上下文"""
        await tracker.initialize(sample_profiles)
        
        locations = interface.get_character_location_context(["沈无衣", "苏映雪"])
        
        assert "沈无衣" in locations
        assert locations["沈无衣"] == "京城"
        assert "苏映雪" in locations
        assert locations["苏映雪"] == "苏府"
    
    @pytest.mark.asyncio
    async def test_prepare_context_for_scene(self, interface, tracker, sample_profiles):
        """测试准备场景上下文"""
        await tracker.initialize(sample_profiles)
        
        context = interface.prepare_context_for_scene(
            scene_characters=["沈无衣", "苏映雪"],
            scene_location="茶楼"
        )
        
        assert "characters" in context
        assert "沈无衣" in context["characters"]
        assert "苏映雪" in context["characters"]
        assert len(context["location_conflicts"]) > 0


class TestAgentContextIntegration:
    """AgentContext人物状态集成测试"""
    
    def test_context_character_state_fields(self):
        """测试Context人物状态字段"""
        context = AgentContext(
            task_id="test_task",
            unit_index=1,
            character_state_snapshot="沈无衣: 监察御史, 京城",
            relationship_summary="沈无衣与苏映雪: 相识",
            character_location_map={"沈无衣": "京城", "苏映雪": "苏府"},
            character_identity_map={"沈无衣": "监察御史", "苏映雪": "太傅之女"},
            active_characters=["沈无衣", "苏映雪"]
        )
        
        assert context.character_state_snapshot == "沈无衣: 监察御史, 京城"
        assert context.relationship_summary == "沈无衣与苏映雪: 相识"
        assert len(context.character_location_map) == 2
        assert len(context.active_characters) == 2


class TestStateConsistency:
    """状态一致性测试"""
    
    @pytest.fixture
    def tracker(self):
        """创建追踪器实例"""
        return CharacterStateTracker(project_id=1)
    
    @pytest.fixture
    def interface(self, tracker):
        """创建接口实例"""
        return CharacterStateInterface(tracker=tracker)
    
    @pytest.mark.asyncio
    async def test_location_consistency_check(self, interface, tracker):
        """测试位置一致性检查"""
        profiles = [
            {"name": "沈无衣", "identity": "监察御史", "location": "京城"}
        ]
        await tracker.initialize(profiles)
        
        tracker.record_chapter_snapshot(
            chapter_num=1,
            chapter_title="第一章",
            content="沈无衣在京城处理公务。",
            characters_present=["沈无衣"]
        )
        
        result = interface.check_state_consistency(
            content="沈无衣突然出现在江南...",
            chapter_num=2
        )
        
        assert "issues" in result or "warnings" in result
    
    @pytest.mark.asyncio
    async def test_state_evolution_tracking(self, tracker):
        """测试状态演变追踪"""
        profiles = [
            {"name": "沈无衣", "identity": "监察御史", "location": "京城"}
        ]
        await tracker.initialize(profiles)
        
        tracker.update_character_state(
            name="沈无衣",
            updates={"location": "江南", "status_change": "出巡"},
            chapter_num=1
        )
        
        tracker.record_chapter_snapshot(
            chapter_num=1,
            chapter_title="出巡",
            content="沈无衣奉命前往江南。",
            characters_present=["沈无衣"]
        )
        
        evolution = tracker.get_state_evolution("沈无衣")
        
        assert len(evolution) > 0
        assert evolution[0]["chapter"] == 1


class TestPromptIntegration:
    """提示词集成测试"""
    
    @pytest.fixture
    def tracker(self):
        """创建追踪器实例"""
        return CharacterStateTracker(project_id=1)
    
    @pytest.mark.asyncio
    async def test_state_in_writer_prompt(self, tracker):
        """测试状态信息在写作提示词中的集成"""
        profiles = [
            {"name": "沈无衣", "identity": "监察御史", "location": "京城"},
            {"name": "苏映雪", "identity": "太傅之女", "location": "苏府"}
        ]
        await tracker.initialize(profiles)
        
        tracker.add_relationship_change(
            chapter_num=1,
            char1="沈无衣",
            char2="苏映雪",
            relationship_type="知己",
            previous_state="陌生人",
            new_state="相识",
            description="茶楼初遇"
        )
        
        state_text = tracker.get_state_for_prompt(chapter_num=2)
        relation_text = tracker.get_relationship_summary()
        
        assert "沈无衣" in state_text
        assert "监察御史" in state_text
        assert "苏映雪" in relation_text


def run_tests():
    """运行测试"""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_tests()
