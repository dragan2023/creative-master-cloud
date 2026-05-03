"""防重复提交修复"""
from core.models import Issue, FixRecord

class DuplicateSubmitFix:
    """自动添加防重复提交逻辑"""
    
    def __init__(self):
        self.confidence = 0.95
        self.requires_review = False
    
    def can_fix(self, issue: Issue) -> bool:
        return issue.type == 'DUPLICATE_SUBMIT'
    
    async def apply(self, issue: Issue) -> FixRecord:
        # 实际修复需要解析前端代码并添加loading检查
        # 这里标记为待人工修复
        return FixRecord(
            issue=issue,
            strategy_name='duplicate_submit_fix',
            success=False,
            details="需人工添加loading检查",
            requires_review=True
        )
