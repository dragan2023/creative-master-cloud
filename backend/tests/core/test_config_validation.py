"""
功能开关配置测试

验证 ENABLE_QUALITY_CONTROL 环境变量的解析契约
（定义位置: app/services/outline_generator/api/constants.py）。

历史背景: 旧版为脚本式测试（print + return bool + main 入口），
且检查已不存在的单文件 outline_generator.py 路径，已按修复计划 01 重写。
"""
import importlib

import pytest


@pytest.fixture
def constants_module():
    """提供 constants 模块，测试结束后恢复原始开关值（不污染其他测试）"""
    from app.services.outline_generator.api import constants

    original_flag = constants.ENABLE_QUALITY_CONTROL
    yield constants
    constants.ENABLE_QUALITY_CONTROL = original_flag


class TestEnableQualityControlFlag:
    """ENABLE_QUALITY_CONTROL 环境变量解析契约"""

    def test_default_is_enabled_when_env_missing(
            self, constants_module, monkeypatch):
        monkeypatch.delenv("ENABLE_QUALITY_CONTROL", raising=False)
        importlib.reload(constants_module)
        assert constants_module.ENABLE_QUALITY_CONTROL is True

    def test_false_value_disables_quality_control(
            self, constants_module, monkeypatch):
        monkeypatch.setenv("ENABLE_QUALITY_CONTROL", "false")
        importlib.reload(constants_module)
        assert constants_module.ENABLE_QUALITY_CONTROL is False

    def test_true_value_enables_quality_control(
            self, constants_module, monkeypatch):
        monkeypatch.setenv("ENABLE_QUALITY_CONTROL", "true")
        importlib.reload(constants_module)
        assert constants_module.ENABLE_QUALITY_CONTROL is True

    @pytest.mark.parametrize("raw_value,expected", [
        ("TRUE", True),
        ("True", True),
        ("FALSE", False),
        ("False", False),
    ])
    def test_value_parsing_is_case_insensitive(
            self, constants_module, monkeypatch, raw_value, expected):
        monkeypatch.setenv("ENABLE_QUALITY_CONTROL", raw_value)
        importlib.reload(constants_module)
        assert constants_module.ENABLE_QUALITY_CONTROL is expected

    def test_non_boolean_string_falls_back_to_disabled(
            self, constants_module, monkeypatch):
        """当前契约: 仅 "true"(忽略大小写) 视为启用，其他值一律禁用"""
        monkeypatch.setenv("ENABLE_QUALITY_CONTROL", "yes")
        importlib.reload(constants_module)
        assert constants_module.ENABLE_QUALITY_CONTROL is False


class TestPackageReexport:
    """包级导出必须保持向后兼容"""

    def test_package_reexports_quality_control_flag(self):
        from app.services import outline_generator

        assert hasattr(outline_generator, "ENABLE_QUALITY_CONTROL")
        assert isinstance(outline_generator.ENABLE_QUALITY_CONTROL, bool)
