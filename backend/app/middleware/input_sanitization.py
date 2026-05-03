"""输入消毒中间件

防止XSS攻击和恶意输入
根据Vibe Coding模拟检测协议 - 异常输入注入防护
"""
import re
import html
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """输入消毒中间件"""
    
    # 危险模式列表
    DANGEROUS_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),  # script标签
        re.compile(r'javascript:', re.IGNORECASE),  # javascript协议
        re.compile(r'on\w+\s*=', re.IGNORECASE),  # 事件处理器
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),  # iframe
        re.compile(r'<object[^>]*>', re.IGNORECASE),  # object
        re.compile(r'<embed[^>]*>', re.IGNORECASE),  # embed
        re.compile(r'DROP\s+TABLE', re.IGNORECASE),  # SQL注入
        re.compile(r'DELETE\s+FROM', re.IGNORECASE),  # SQL注入
        re.compile(r'UNION\s+SELECT', re.IGNORECASE),  # SQL注入
    ]
    
    # 最大输入长度
    # 注意：MAX_TOTAL_LENGTH 检查的是请求体原始字节数（非字符数），中文 UTF-8 每字 3 字节
    # 29000 中文字 ≈ 87000 字节，加上 JSON 结构开销，100KB 严重不足
    # 提升到 10MB 以支持大纲/单元概述等大文本上传
    MAX_FIELD_LENGTH = 5_000_000   # 单字段最大 500 万字符（约 15MB UTF-8），防止静默截断
    MAX_TOTAL_LENGTH = 10_000_000  # 请求体最大 10MB 字节，防止 XSS 中间件误杀正常大文本
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 只处理POST/PUT请求
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return await call_next(request)
        
        # 跳过文件上传
        content_type = request.headers.get('content-type', '')
        if 'multipart/form-data' in content_type:
            return await call_next(request)
        
        # 读取并验证请求体
        try:
            body = await request.body()
            
            # 检查总长度
            if len(body) > self.MAX_TOTAL_LENGTH:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"请求体过大（最大{self.MAX_TOTAL_LENGTH}字节）"
                    }
                )
            
            # 尝试解析JSON
            import json
            try:
                body_json = json.loads(body)
            except json.JSONDecodeError:
                # 不是JSON，放行
                return await call_next(request)
            
            # 消毒所有字符串字段
            sanitized_body = self._sanitize_dict(body_json)
            
            # 重新序列化
            sanitized_json = json.dumps(sanitized_body, ensure_ascii=False).encode('utf-8')
            
            # [修复] 直接替换请求体的缓存内容，而不是替换 _receive 函数。
            # 替换 _receive 会破坏 BaseHTTPMiddleware 的流式响应（StreamingResponse）
            # 机制——Starlette 在流式响应中会多次调用 receive() 来检测客户端断开连接，
            # 返回非预期消息类型会触发 RuntimeError: Unexpected message received。
            # 直接设置 _body 缓存则不影响 receive 管道，同时保证下游获取消毒后的数据。
            request._body = sanitized_json
            
        except Exception as e:
            # 如果处理失败，放行原始请求
            print(f"[InputSanitization] 消毒失败: {e}")
        
        return await call_next(request)
    
    def _sanitize_dict(self, data: dict) -> dict:
        """递归消毒字典中的所有字符串"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self._sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = self._sanitize_list(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_list(self, data: list) -> list:
        """递归消毒列表中的所有字符串"""
        sanitized = []
        for item in data:
            if isinstance(item, str):
                sanitized.append(self._sanitize_string(item))
            elif isinstance(item, dict):
                sanitized.append(self._sanitize_dict(item))
            elif isinstance(item, list):
                sanitized.append(self._sanitize_list(item))
            else:
                sanitized.append(item)
        return sanitized
    
    def _sanitize_string(self, text: str) -> str:
        """消毒单个字符串"""
        # 【修复】不再静默截断超长字段，仅做安全模式检查
        # 长度限制由下游 Schema 验证（Pydantic max_length）和业务逻辑自行处理
        
        # 检查危险模式
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.search(text):
                # 移除危险内容
                text = pattern.sub('', text)
        
        # HTML转义（保留基本格式）
        # 注意：不完全转义，因为某些字段可能允许Markdown
        # 只移除危险的HTML标签
        text = self._remove_dangerous_html(text)
        
        return text
    
    def _remove_dangerous_html(self, text: str) -> str:
        """移除危险的HTML标签"""
        # 移除script标签及其内容
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # 移除事件处理器
        text = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
        
        # 移除javascript:协议
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        
        return text
