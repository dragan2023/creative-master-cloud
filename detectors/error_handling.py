"""错误处理检测"""
from core.models import Issue

class ErrorHandlingDetector:
    """检测错误提示缺失"""
    
    async def detect(self, page, console_errors: list, failed_requests: list) -> list:
        issues = []
        
        # 检查控制台错误但未提示用户
        if console_errors and len(console_errors) > 3:
            issues.append(Issue(
                type='MISSING_ERROR_FEEDBACK',
                severity='medium',
                location=page.url,
                description=f"控制台有{len(console_errors)}个错误但未提示用户",
                category='feedback_gap'
            ))
        
        # 检查500错误
        for req in failed_requests:
            if req.get('status') == 500:
                issues.append(Issue(
                    type='SERVER_ERROR_NO_FEEDBACK',
                    severity='high',
                    location=req.get('url', ''),
                    description="服务器500错误无友好提示",
                    category='feedback_gap'
                ))
        
        return issues
