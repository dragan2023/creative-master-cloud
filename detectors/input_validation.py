"""输入验证检测"""
from core.models import Issue

class InputValidationDetector:
    """检测XSS、SQL注入等"""
    
    async def detect(self, page, action_log: list) -> list:
        issues = []
        
        # 检查是否有异常输入被接受
        for action in action_log:
            if action.action_type == 'input':
                value = action.value
                if '<script>' in value.lower() or 'javascript:' in value.lower():
                    issues.append(Issue(
                        type='XSS_VULNERABILITY',
                        severity='critical',
                        location=action.page_url,
                        description=f"XSS向量未被过滤: {value[:50]}",
                        category='fault_tolerance_gap'
                    ))
        
        return issues
