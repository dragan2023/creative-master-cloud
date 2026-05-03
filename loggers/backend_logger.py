"""后端日志收集器"""
import re
from datetime import datetime
from pathlib import Path
from core.models import LogRecord

class BackendLogger:
    """后端日志收集器"""
    
    def __init__(self, backend_log_path: str):
        self.backend_log_path = Path(backend_log_path)
        self.logs = []
        
    def collect_logs(self) -> list:
        """收集后端日志"""
        if not self.backend_log_path.exists():
            return []
        
        for log_file in self.backend_log_path.glob("*.log"):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        record = self._parse_line(line, str(log_file))
                        if record:
                            self.logs.append(record)
            except Exception as e:
                print(f"  ⚠ 读取失败 {log_file}: {e}")
        
        return self.logs
    
    def _parse_line(self, line: str, source: str) -> LogRecord:
        """解析日志行"""
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|WARNING|ERROR|DEBUG) \[(.+?)\] (.+)'
        match = re.match(pattern, line.strip())
        if match:
            ts_str, level, module, message = match.groups()
            return LogRecord(
                timestamp=datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S'),
                log_type='backend',
                level=level.lower(),
                message=message,
                source=f"{source} [{module}]"
            )
        return None
    
    def get_errors(self) -> list:
        return [log for log in self.logs if log.level == 'error']
