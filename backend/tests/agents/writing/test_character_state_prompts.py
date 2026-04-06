"""
人物状态追踪提示词模板单元测试

测试范围:
1. 模块导入正确性
2. 提示词模板完整性
3. 小说/剧本分类处理
4. 辅助函数功能
"""
import pytest
import sys
sys.path.insert(0, '.')


class TestCharacterStatePromptsImport:
    """测试模块导入"""
    
    def test_import_character_state_prompts(self):
        """测试导入character_state_prompts模块"""
        from app.agents.writing.prompts.character_state_prompts import CHARACTER_STATE_PROMPTS
        assert CHARACTER_STATE_PROMPTS is not None
        assert isinstance(CHARACTER_STATE_PROMPTS, dict)
    
    def test_import_constants(self):
        """测试导入常量"""
        from app.agents.writing.prompts.character_state_prompts import (
            NOVEL_STATE_DIMENSIONS,
            SCRIPT_STATE_DIMENSIONS,
            STATE_CHANGE_TYPES,
            VISUAL_PRESENTATION_GUIDE
        )
        assert len(NOVEL_STATE_DIMENSIONS) > 0
        assert len(SCRIPT_STATE_DIMENSIONS) > 0
        assert len(STATE_CHANGE_TYPES) > 0
        assert len(VISUAL_PRESENTATION_GUIDE) > 0
    
    def test_import_functions(self):
        """测试导入函数"""
        from app.agents.writing.prompts.character_state_prompts import (
            get_writer_system_prompt,
            get_writer_user_prompt,
            get_editor_system_prompt,
            get_editor_user_prompt,
            format_state_change_table
        )
        assert callable(get_writer_system_prompt)
        assert callable(get_writer_user_prompt)
        assert callable(get_editor_system_prompt)
        assert callable(get_editor_user_prompt)
        assert callable(format_state_change_table)


class TestCharacterStatePromptsContent:
    """测试提示词内容"""
    
    def test_prompt_keys_exist(self):
        """测试提示词键存在"""
        from app.agents.writing.prompts.character_state_prompts import CHARACTER_STATE_PROMPTS
        
        required_keys = [
            "novel_writer_system",
            "novel_writer_user",
            "script_writer_system",
            "script_writer_user",
            "novel_editor_system",
            "novel_editor_user",
            "script_editor_system",
            "script_editor_user"
        ]
        
        for key in required_keys:
            assert key in CHARACTER_STATE_PROMPTS, f"Missing key: {key}"
    
    def test_novel_writer_system_content(self):
        """测试小说写作系统提示词内容"""
        from app.agents.writing.prompts.character_state_prompts import CHARACTER_STATE_PROMPTS
        
        prompt = CHARACTER_STATE_PROMPTS["novel_writer_system"]
        
        assert "人物状态一致性" in prompt
        assert "状态变化维度" in prompt
        assert "能力变化" in prompt
        assert "身份变化" in prompt
        assert "地点变化" in prompt
    
    def test_script_writer_system_content(self):
        """测试剧本写作系统提示词内容"""
        from app.agents.writing.prompts.character_state_prompts import CHARACTER_STATE_PROMPTS
        
        prompt = CHARACTER_STATE_PROMPTS["script_writer_system"]
        
        assert "视觉化" in prompt or "镜头" in prompt or "场景" in prompt
        assert "人物状态一致性" in prompt
    
    def test_editor_prompts_content(self):
        """测试编辑提示词内容"""
        from app.agents.writing.prompts.character_state_prompts import CHARACTER_STATE_PROMPTS
        
        novel_editor = CHARACTER_STATE_PROMPTS["novel_editor_user"]
        script_editor = CHARACTER_STATE_PROMPTS["script_editor_user"]
        
        assert "人物状态" in novel_editor
        assert "人物状态" in script_editor
        assert "一致性" in novel_editor
        assert "一致性" in script_editor


class TestContentTypeSpecificPrompts:
    """测试内容类型分类处理"""
    
    def test_get_writer_system_prompt_novel(self):
        """测试获取小说写作系统提示词"""
        from app.agents.writing.prompts.character_state_prompts import (
            get_writer_system_prompt,
            CHARACTER_STATE_PROMPTS
        )
        
        prompt = get_writer_system_prompt("novel")
        assert prompt == CHARACTER_STATE_PROMPTS["novel_writer_system"]
    
    def test_get_writer_system_prompt_script(self):
        """测试获取剧本写作系统提示词"""
        from app.agents.writing.prompts.character_state_prompts import (
            get_writer_system_prompt,
            CHARACTER_STATE_PROMPTS
        )
        
        prompt = get_writer_system_prompt("script")
        assert prompt == CHARACTER_STATE_PROMPTS["script_writer_system"]
    
    def test_get_editor_system_prompt_novel(self):
        """测试获取小说编辑系统提示词"""
        from app.agents.writing.prompts.character_state_prompts import (
            get_editor_system_prompt,
            CHARACTER_STATE_PROMPTS
        )
        
        prompt = get_editor_system_prompt("novel")
        assert prompt == CHARACTER_STATE_PROMPTS["novel_editor_system"]
    
    def test_get_editor_system_prompt_script(self):
        """测试获取剧本编辑系统提示词"""
        from app.agents.writing.prompts.character_state_prompts import (
            get_editor_system_prompt,
            CHARACTER_STATE_PROMPTS
        )
        
        prompt = get_editor_system_prompt("script")
        assert prompt == CHARACTER_STATE_PROMPTS["script_editor_system"]


class TestHelperFunctions:
    """测试辅助函数"""
    
    def test_format_state_change_table_empty(self):
        """测试空状态变化表格"""
        from app.agents.writing.prompts.character_state_prompts import format_state_change_table
        
        result = format_state_change_table([])
        assert "无重要人物状态变化" in result
    
    def test_format_state_change_table_with_data(self):
        """测试有数据的状态变化表格"""
        from app.agents.writing.prompts.character_state_prompts import format_state_change_table
        
        state_changes = [
            {
                "character": "沈无衣",
                "change_type": "location",
                "before": "京城",
                "after": "江南",
                "reason": "奉命出巡",
                "evidence": "沈无衣奉命前往江南查案"
            }
        ]
        
        result = format_state_change_table(state_changes)
        assert "沈无衣" in result
        assert "京城" in result
        assert "江南" in result


class TestWriterPromptsIntegration:
    """测试writer_prompts集成"""
    
    def test_writer_prompts_import(self):
        """测试writer_prompts导入"""
        from app.agents.writing.prompts.writer_prompts import (
            WRITER_PROMPTS,
            get_writer_prompts,
            get_state_dimensions
        )
        
        assert WRITER_PROMPTS is not None
        assert callable(get_writer_prompts)
        assert callable(get_state_dimensions)
    
    def test_get_writer_prompts_novel(self):
        """测试获取小说写作提示词"""
        from app.agents.writing.prompts.writer_prompts import get_writer_prompts
        
        prompts = get_writer_prompts("novel")
        assert "system" in prompts
        assert "user" in prompts
        assert len(prompts["system"]) > 0
        assert len(prompts["user"]) > 0
    
    def test_get_writer_prompts_script(self):
        """测试获取剧本写作提示词"""
        from app.agents.writing.prompts.writer_prompts import get_writer_prompts
        
        prompts = get_writer_prompts("script")
        assert "system" in prompts
        assert "user" in prompts
        assert len(prompts["system"]) > 0
    
    def test_get_state_dimensions(self):
        """测试获取状态维度"""
        from app.agents.writing.prompts.writer_prompts import get_state_dimensions
        
        novel_dims = get_state_dimensions("novel")
        script_dims = get_state_dimensions("script")
        
        assert len(novel_dims) > 0
        assert len(script_dims) > 0
        assert "能力变化" in novel_dims
        assert "身份变化" in novel_dims


class TestEditorPromptsIntegration:
    """测试editor_prompts集成"""
    
    def test_editor_prompts_import(self):
        """测试editor_prompts导入"""
        from app.agents.writing.prompts.editor_prompts import (
            EDITOR_PROMPTS,
            get_editor_prompts,
            get_state_check_dimensions
        )
        
        assert EDITOR_PROMPTS is not None
        assert callable(get_editor_prompts)
        assert callable(get_state_check_dimensions)
    
    def test_get_editor_prompts_novel(self):
        """测试获取小说编辑提示词"""
        from app.agents.writing.prompts.editor_prompts import get_editor_prompts
        
        prompts = get_editor_prompts("novel")
        assert "system" in prompts
        assert "user" in prompts
        assert len(prompts["system"]) > 0
    
    def test_get_editor_prompts_script(self):
        """测试获取剧本编辑提示词"""
        from app.agents.writing.prompts.editor_prompts import get_editor_prompts
        
        prompts = get_editor_prompts("script")
        assert "system" in prompts
        assert "user" in prompts
        assert len(prompts["system"]) > 0
    
    def test_get_state_check_dimensions(self):
        """测试获取状态检查维度"""
        from app.agents.writing.prompts.editor_prompts import get_state_check_dimensions
        
        novel_dims = get_state_check_dimensions("novel")
        script_dims = get_state_check_dimensions("script")
        
        assert len(novel_dims) > 0
        assert len(script_dims) > 0


class TestPromptsPackageInit:
    """测试prompts包初始化"""
    
    def test_package_imports(self):
        """测试包级别导入"""
        from app.agents.writing.prompts import (
            CHARACTER_STATE_PROMPTS,
            NOVEL_STATE_DIMENSIONS,
            SCRIPT_STATE_DIMENSIONS,
            get_writer_prompts,
            get_editor_prompts
        )
        
        assert CHARACTER_STATE_PROMPTS is not None
        assert len(NOVEL_STATE_DIMENSIONS) > 0
        assert len(SCRIPT_STATE_DIMENSIONS) > 0
        assert callable(get_writer_prompts)
        assert callable(get_editor_prompts)
