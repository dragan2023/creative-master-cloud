"""防重复提交检测"""
from core.models import Issue
from datetime import datetime

class DuplicateSubmitDetector:
    """检测500ms内的重复请求"""
    
    async def detect(self, page, action_log: list, request_log: list) -> list:
        issues = []
        
        # 分析相同URL的请求时间
        url_times = {}
        for req in request_log:
            url = req.get('url', '')
            if '/api/' not in url:
                continue
            
            if url not in url_times:
                url_times[url] = []
            url_times[url].append(req.get('time', datetime.now()))
        
        # 检查短时间重复
        for url, times in url_times.items():
            if len(times) < 2:
                continue
            
            times.sort()
            for i in range(len(times) - 1):
                delta = (times[i+1] - times[i]).total_seconds() * 1000
                if delta < 500:
                    issues.append(Issue(
                        type='DUPLICATE_SUBMIT',
                        severity='high',
                        location=url,
                        description=f"500ms内重复请求{len(times)}次",
                        category='operation_gap',
                        reproduction_steps="快速点击按钮"
                    ))
                    break
        
        return issues
