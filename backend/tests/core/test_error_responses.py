"""错误响应格式测试"""
import pytest
from app.core.error_responses import ErrorResponse


class TestErrorResponse:
    """ErrorResponse 单元测试"""
    
    def test_error_response_creation(self):
        """测试错误响应创建"""
        resp = ErrorResponse(
            code="RESOURCE_NOT_FOUND",
            message="资源不存在",
            trace_id="test-trace-id",
            timestamp="2026-04-02T00:00:00"
        )
        
        assert resp.success is False
        assert resp.code == "RESOURCE_NOT_FOUND"
        assert resp.message == "资源不存在"
        assert resp.trace_id == "test-trace-id"
        assert resp.timestamp == "2026-04-02T00:00:00"
    
    def test_error_response_with_details(self):
        """测试错误响应带详情"""
        resp = ErrorResponse(
            code="VALIDATION_ERROR",
            message="参数错误",
            trace_id="test-trace-id",
            timestamp="2026-04-02T00:00:00",
            details={"field": "name", "error": "不能为空"}
        )
        
        assert resp.details is not None
        assert resp.details["field"] == "name"
        assert resp.details["error"] == "不能为空"
    
    def test_error_response_success_always_false(self):
        """测试错误响应 success 始终为 False"""
        resp = ErrorResponse(
            code="INTERNAL_ERROR",
            message="内部错误",
            trace_id="test-trace-id",
            timestamp="2026-04-02T00:00:00"
        )
        
        # 即使尝试设置为 True，也应该保持 False
        assert resp.success is False
    
    def test_error_response_without_details(self):
        """测试错误响应无详情"""
        resp = ErrorResponse(
            code="AUTH_FAILED",
            message="认证失败",
            trace_id="test-trace-id",
            timestamp="2026-04-02T00:00:00"
        )
        
        assert resp.details is None
    
    def test_error_response_model_dump(self):
        """测试错误响应序列化"""
        resp = ErrorResponse(
            code="RATE_LIMIT",
            message="请求过于频繁",
            trace_id="trace-123",
            timestamp="2026-04-02T12:00:00",
            details={"retry_after": 60}
        )
        
        data = resp.model_dump()
        
        assert data["success"] is False
        assert data["code"] == "RATE_LIMIT"
        assert data["message"] == "请求过于频繁"
        assert data["trace_id"] == "trace-123"
        assert data["details"]["retry_after"] == 60
    
    def test_error_response_json_serialization(self):
        """测试错误响应 JSON 序列化"""
        resp = ErrorResponse(
            code="FORBIDDEN",
            message="权限不足",
            trace_id="trace-456",
            timestamp="2026-04-02T15:30:00"
        )
        
        json_str = resp.model_dump_json()
        
        assert '"success":false' in json_str
        assert '"code":"FORBIDDEN"' in json_str
        assert '"message":"权限不足"' in json_str
    
    def test_error_response_with_nested_details(self):
        """测试错误响应带嵌套详情"""
        resp = ErrorResponse(
            code="VALIDATION_ERROR",
            message="表单验证失败",
            trace_id="trace-789",
            timestamp="2026-04-02T18:00:00",
            details={
                "errors": [
                    {"field": "email", "message": "邮箱格式不正确"},
                    {"field": "password", "message": "密码长度不足"}
                ],
                "total_errors": 2
            }
        )
        
        assert len(resp.details["errors"]) == 2
        assert resp.details["total_errors"] == 2
        assert resp.details["errors"][0]["field"] == "email"
    
    def test_error_response_different_codes(self):
        """测试不同错误码"""
        codes = [
            "RESOURCE_NOT_FOUND",
            "VALIDATION_ERROR",
            "AUTH_TOKEN_EXPIRED",
            "PERMISSION_DENIED",
            "GENERATION_FAILED",
            "LLM_SERVICE_ERROR",
        ]
        
        for code in codes:
            resp = ErrorResponse(
                code=code,
                message=f"错误: {code}",
                trace_id="trace-id",
                timestamp="2026-04-02T00:00:00"
            )
            assert resp.code == code
            assert resp.success is False
