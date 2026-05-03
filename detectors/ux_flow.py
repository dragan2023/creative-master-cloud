"""用户体验流检测"""
from core.models import Issue

class UXFlowDetector:
    """检测5类体验断层"""
    
    async def detect(self, page, action_log: list) -> list:
        issues = []
        
        # 检查加载状态指示器
        has_loading = await page.locator('.el-loading-mask, .loading, [class*="loading"]').count() > 0
        
        # 检查操作反馈
        click_count = sum(1 for a in action_log if a.action_type == 'click')
        if click_count > 5 and not has_loading:
            issues.append(Issue(
                type='MISSING_LOADING_INDICATOR',
                severity='medium',
                location=page.url,
                description="多次点击无加载指示器",
                category='feedback_gap'
            ))
        
        return issues
