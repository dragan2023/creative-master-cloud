"""控制台日志收集器"""
from datetime import datetime
from core.models import LogRecord

class ConsoleLogger:
    """浏览器控制台监听"""
    
    def __init__(self):
        self.logs = []
        self.errors = []
        
    def setup(self, page):
        page.on("console", self._on_message)
        
    def _on_message(self, msg):
        record = LogRecord(
            timestamp=datetime.now(),
            log_type='console',
            level=msg.type,
            message=msg.text,
            source=msg.location.get('url', '') if hasattr(msg, 'location') else ''
        )
        self.logs.append(record)
        if msg.type == 'error':
            self.errors.append(record)
    
    def get_errors(self):
        return self.errors
