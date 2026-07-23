"""
配置加载与版本一致性测试

覆盖 04 号治理计划的两项验收要求：
1. Pydantic v2 迁移到 model_config，消除 class-based `Config` 弃用告警；
2. 产品版本以 version.json.current_version 为唯一来源，后端配置读取该值。
"""
import json
import os
import warnings

from app.core.config import Settings, get_settings, get_version_from_file


def _load_version_json() -> dict:
    """读取项目根目录 version.json，供版本一致性断言使用。"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    project_root = os.path.dirname(backend_dir)
    version_path = os.path.join(project_root, "version.json")
    with open(version_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_settings_uses_model_config_not_legacy_class():
    """Settings 应使用 model_config，且不再保留旧式内部 class Config。"""
    assert isinstance(Settings.model_config, dict)
    assert Settings.model_config.get("env_file") == ".env"
    assert Settings.model_config.get("case_sensitive") is True
    assert Settings.model_config.get("extra") == "ignore"
    # 旧式 class Config 迁移后不应再作为普通嵌套类存在
    legacy = Settings.__dict__.get("Config")
    assert legacy is None


def test_settings_instantiation_has_no_pydantic_deprecation():
    """实例化配置不应触发 pydantic 关于 class-based Config 的弃用告警。"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Settings()

    deprecations = [
        str(w.message)
        for w in caught
        if "class-based `config`" in str(w.message).lower()
        or "class-based config" in str(w.message).lower()
    ]
    assert not deprecations, f"存在 pydantic 弃用告警: {deprecations}"


def test_app_version_single_source_from_version_json():
    """后端版本必须与 version.json.current_version 保持一致。"""
    expected = _load_version_json()["current_version"]
    assert get_version_from_file() == expected
    assert get_settings().APP_VERSION == expected
