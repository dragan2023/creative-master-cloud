"""KnowledgeBase 模型业务方法测试"""
import pytest
from datetime import timedelta
from app.core.time import utc_now
from app.models.knowledge_base import (
    KnowledgeBase, KnowledgeBaseType, 
    KnowledgeBaseStatus, KnowledgeBaseCategory
)


class TestKnowledgeBaseModel:
    """KnowledgeBase 模型业务方法测试"""
    
    def test_is_expired_true(self):
        kb = KnowledgeBase()
        # 设置过期时间为昨天
        kb.expires_at = utc_now().replace(tzinfo=None) - timedelta(days=1)
        assert kb.is_expired() is True
    
    def test_is_expired_false(self):
        kb = KnowledgeBase()
        # 设置过期时间为明天
        kb.expires_at = utc_now().replace(tzinfo=None) + timedelta(days=1)
        assert kb.is_expired() is False
    
    def test_is_expired_no_expiry(self):
        kb = KnowledgeBase()
        kb.expires_at = None
        assert kb.is_expired() is False
    
    def test_is_ready_for_use_true(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.READY
        kb.expires_at = None
        assert kb.is_ready_for_use() is True
    
    def test_is_ready_for_use_not_ready(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.PROCESSING
        assert kb.is_ready_for_use() is False
    
    def test_is_ready_for_use_expired(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.READY
        kb.expires_at = utc_now().replace(tzinfo=None) - timedelta(days=1)
        assert kb.is_ready_for_use() is False
    
    def test_is_processing_true(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.PROCESSING
        assert kb.is_processing() is True
    
    def test_is_processing_false(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.READY
        assert kb.is_processing() is False
    
    def test_is_failed_true(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.FAILED
        assert kb.is_failed() is True
    
    def test_is_failed_false(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.READY
        assert kb.is_failed() is False
    
    def test_mark_ready(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.PROCESSING
        kb.mark_ready(document_count=10)
        assert kb.status == KnowledgeBaseStatus.READY
        assert kb.document_count == 10
    
    def test_mark_ready_no_count(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.PROCESSING
        kb.document_count = 5
        kb.mark_ready()  # 不传document_count，应保持原值
        assert kb.status == KnowledgeBaseStatus.READY
        assert kb.document_count == 5
    
    def test_mark_failed(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.PROCESSING
        kb.mark_failed()
        assert kb.status == KnowledgeBaseStatus.FAILED
    
    def test_mark_processing(self):
        kb = KnowledgeBase()
        kb.status = KnowledgeBaseStatus.PENDING
        kb.mark_processing()
        assert kb.status == KnowledgeBaseStatus.PROCESSING
    
    def test_repr(self):
        kb = KnowledgeBase()
        kb.id = 1
        kb.name = "测试知识库"
        kb.type = KnowledgeBaseType.TEMP
        kb.category = KnowledgeBaseCategory.GENERAL
        repr_str = repr(kb)
        assert "KnowledgeBase" in repr_str
        assert "测试知识库" in repr_str
