"""模块注册表测试"""
import pytest
from app.core.module_registry import (
    MODULE_REGISTRY, get_module_config, get_all_module_ids
)


class TestModuleRegistry:
    def test_registry_not_empty(self):
        assert len(MODULE_REGISTRY) > 0
    
    def test_get_module_config_valid(self):
        # 使用第一个注册的模块测试
        module_id = list(MODULE_REGISTRY.keys())[0]
        config = get_module_config(module_id)
        assert config.module_id == module_id
        assert config.display_name is not None
    
    def test_get_module_config_invalid(self):
        with pytest.raises(ValueError) as exc_info:
            get_module_config("nonexistent_module")
        assert "nonexistent_module" in str(exc_info.value)
    
    def test_get_all_module_ids(self):
        ids = get_all_module_ids()
        assert len(ids) == len(MODULE_REGISTRY)
        assert all(isinstance(mid, str) for mid in ids)
    
    def test_all_modules_have_required_fields(self):
        for module_id, config in MODULE_REGISTRY.items():
            assert config.module_id, f"{module_id} 缺少 module_id"
            assert config.display_name, f"{module_id} 缺少 display_name"
            assert config.api_path, f"{module_id} 缺少 api_path"
            assert config.kb_category, f"{module_id} 缺少 kb_category"
    
    def test_module_config_has_kb_category(self):
        for module_id, config in MODULE_REGISTRY.items():
            assert hasattr(config, 'kb_category')
            assert config.kb_category is not None
    
    def test_module_config_has_supports_flags(self):
        for module_id, config in MODULE_REGISTRY.items():
            assert hasattr(config, 'supports_knowledge')
            assert hasattr(config, 'supports_search')
            assert hasattr(config, 'supports_trending')
