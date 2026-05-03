"""用户行为日志"""
from datetime import datetime
from core.models import UserAction

class BehaviorLogger:
    """记录用户操作轨迹"""
    
    def __init__(self):
        self.actions = []
        
    def log(self, action_type: str, target: str = "", value: str = "", 
            url: str = "", **kwargs):
        action = UserAction(
            timestamp=datetime.now(),
            action_type=action_type,
            target_element=target,
            value=value,
            page_url=url,
            metadata=kwargs
        )
        self.actions.append(action)
        return action
    
    def export_json(self):
        return [
            {
                'time': a.timestamp.isoformat(),
                'type': a.action_type,
                'target': a.target_element,
                'value': a.value,
                'url': a.page_url
            }
            for a in self.actions
        ]
