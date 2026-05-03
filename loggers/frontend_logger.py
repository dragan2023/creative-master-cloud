"""前端请求日志收集器"""
from datetime import datetime
from core.models import LogRecord

class FrontendLogger:
    """前端请求日志 - Playwright拦截"""
    
    def __init__(self):
        self.requests = []
        self.responses = []
        self.failed = []
        
    def setup(self, page):
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_failed)
        
    def _on_request(self, req):
        self.requests.append({
            'time': datetime.now(),
            'url': req.url,
            'method': req.method,
            'type': req.resource_type
        })
    
    def _on_response(self, resp):
        self.responses.append({
            'time': datetime.now(),
            'url': resp.url,
            'status': resp.status
        })
    
    def _on_failed(self, req):
        self.failed.append({
            'time': datetime.now(),
            'url': req.url,
            'error': req.failure
        })
    
    def get_api_requests(self):
        return [r for r in self.requests if '/api/' in r['url']]
