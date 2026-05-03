"""错误提示修复"""
from core.models import Issue, FixRecord

class ErrorMessageFix:
    """添加错误提示"""
    
    def __init__(self):
        self.confidence = 0.90
        self.requires_review = False
    
    def can_fix(self, issue: Issue) -> bool:
        return 'MISSING_ERROR_FEEDBACK' in issue.type
    
    async def apply(self, issue: Issue) -> FixRecord:
        return FixRecord(
            issue=issue,
            strategy_name='error_message_fix',
            success=False,
            details="需人工添加ElMessage.error()",
            requires_review=True
        )
