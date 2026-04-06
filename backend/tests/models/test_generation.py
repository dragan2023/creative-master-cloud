"""Generation 模型业务方法测试"""
import pytest
from app.models.generation import Generation, GenerationModule, GenerationStatus


class TestGenerationModel:
    """Generation 模型业务方法测试"""
    
    def test_is_completed_true(self):
        gen = Generation()
        gen.status = GenerationStatus.COMPLETED
        assert gen.is_completed() is True
    
    def test_is_completed_false(self):
        gen = Generation()
        gen.status = GenerationStatus.PROCESSING
        assert gen.is_completed() is False
    
    def test_is_failed(self):
        gen = Generation()
        gen.status = GenerationStatus.FAILED
        assert gen.is_failed() is True
    
    def test_can_delete_completed(self):
        gen = Generation()
        gen.status = GenerationStatus.COMPLETED
        assert gen.can_delete() is True
    
    def test_can_delete_failed(self):
        gen = Generation()
        gen.status = GenerationStatus.FAILED
        assert gen.can_delete() is True
    
    def test_can_delete_processing(self):
        gen = Generation()
        gen.status = GenerationStatus.PROCESSING
        assert gen.can_delete() is False
    
    def test_can_delete_pending(self):
        gen = Generation()
        gen.status = GenerationStatus.PENDING
        assert gen.can_delete() is False
    
    def test_get_duration_seconds(self):
        gen = Generation()
        gen.duration_ms = 5000
        assert gen.get_duration_seconds() == 5.0
    
    def test_get_duration_seconds_none(self):
        gen = Generation()
        gen.duration_ms = None
        assert gen.get_duration_seconds() == 0.0
    
    def test_get_duration_seconds_zero(self):
        gen = Generation()
        gen.duration_ms = 0
        assert gen.get_duration_seconds() == 0.0
    
    def test_mark_completed(self):
        gen = Generation()
        gen.status = GenerationStatus.PROCESSING
        gen.mark_completed(
            output_content="测试内容",
            provider="test",
            model_name="test-model",
            token_count=100,
            duration_ms=5000
        )
        assert gen.status == GenerationStatus.COMPLETED
        assert gen.output_content == "测试内容"
        assert gen.provider == "test"
        assert gen.model_name == "test-model"
        assert gen.token_count == 100
        assert gen.duration_ms == 5000
    
    def test_mark_completed_defaults(self):
        gen = Generation()
        gen.mark_completed(
            output_content="测试内容",
            provider="test",
            model_name="test-model"
        )
        assert gen.status == GenerationStatus.COMPLETED
        assert gen.token_count == 0
        assert gen.duration_ms == 0
    
    def test_mark_failed(self):
        gen = Generation()
        gen.mark_failed("测试错误")
        assert gen.status == GenerationStatus.FAILED
        assert gen.error_message == "测试错误"
    
    def test_is_processing_true(self):
        gen = Generation()
        gen.status = GenerationStatus.PROCESSING
        assert gen.is_processing() is True
    
    def test_is_processing_false(self):
        gen = Generation()
        gen.status = GenerationStatus.COMPLETED
        assert gen.is_processing() is False
    
    def test_repr(self):
        gen = Generation()
        gen.id = 1
        gen.module = GenerationModule.NOVEL
        gen.status = GenerationStatus.COMPLETED
        repr_str = repr(gen)
        assert "Generation" in repr_str
        assert "1" in repr_str
        assert "COMPLETED" in repr_str
