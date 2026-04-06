"""
测试基础设施配置

提供公共 fixtures 用于测试。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import pytest
import sys
import os

# 确保 backend 目录在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# 模型测试 fixtures
@pytest.fixture
def sample_generation_data():
    """生成记录测试数据"""
    return {
        "output_content": "测试内容",
        "provider": "test",
        "model_name": "test-model",
        "token_count": 100,
        "duration_ms": 5000
    }


@pytest.fixture
def sample_knowledge_base_data():
    """知识库测试数据"""
    return {
        "name": "测试知识库",
        "description": "测试描述",
        "document_count": 10
    }


@pytest.fixture
def sample_novel_project_data():
    """小说项目测试数据"""
    return {
        "title": "测试项目",
        "outline_content": "测试大纲内容"
    }
