"""性能监控"""
from core.models import Issue

class PerformanceMonitor:
    """检测页面性能"""
    
    async def detect(self, page) -> list:
        issues = []
        
        try:
            # 获取性能指标
            perf = await page.evaluate("""() => {
                const timing = performance.getEntriesByType("navigation")[0];
                return {
                    loadTime: timing.loadEventEnd - timing.startTime,
                    domReady: timing.domContentLoadedEventEnd - timing.startTime
                };
            }""")
            
            if perf.get('loadTime', 0) > 5000:
                issues.append(Issue(
                    type='SLOW_PAGE_LOAD',
                    severity='medium',
                    location=page.url,
                    description=f"页面加载{perf['loadTime']:.0f}ms (>5秒)",
                    category='operation_gap'
                ))
        except:
            pass
        
        return issues
