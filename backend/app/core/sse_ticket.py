"""SSE Ticket 管理器

提供短期一次性 ticket 用于 SSE 连接认证。
替代 URL 中直接传递 token 的方式，提升安全性。
"""
import secrets
import time
from typing import Optional, Dict
from dataclasses import dataclass, field


@dataclass
class Ticket:
    """SSE 连接 ticket"""
    ticket_id: str
    user_id: int
    project_id: int
    created_at: float
    expires_at: float
    used: bool = False

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.used and not self.is_expired


class SSETicketManager:
    """SSE Ticket 管理器（单例）"""

    def __init__(self, ttl_seconds: int = 60):
        """
        Args:
            ttl_seconds: ticket 有效期（秒），默认 60 秒
        """
        self._tickets: Dict[str, Ticket] = {}
        self._ttl_seconds = ttl_seconds

    def create_ticket(self, user_id: int, project_id: int) -> str:
        """
        创建一次性 SSE ticket

        Args:
            user_id: 用户 ID
            project_id: 项目 ID

        Returns:
            ticket 字符串
        """
        ticket_id = secrets.token_urlsafe(32)
        now = time.time()

        ticket = Ticket(
            ticket_id=ticket_id,
            user_id=user_id,
            project_id=project_id,
            created_at=now,
            expires_at=now + self._ttl_seconds
        )

        self._tickets[ticket_id] = ticket
        return ticket_id

    def validate_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """
        验证 ticket

        Args:
            ticket_id: ticket 字符串

        Returns:
            有效的 ticket 对象，如果无效则返回 None
        """
        ticket = self._tickets.get(ticket_id)

        if ticket is None:
            return None

        if not ticket.is_valid:
            # 清理无效 ticket
            self._tickets.pop(ticket_id, None)
            return None

        # 标记为已使用
        ticket.used = True
        return ticket

    def cleanup_expired(self) -> int:
        """清理过期 ticket，返回清理数量"""
        expired = [
            tid for tid, t in self._tickets.items()
            if t.is_expired or t.used
        ]
        for tid in expired:
            self._tickets.pop(tid, None)
        return len(expired)

    @property
    def active_count(self) -> int:
        """当前活跃 ticket 数量"""
        return sum(1 for t in self._tickets.values() if t.is_valid)


# 全局单例
_sse_ticket_manager: Optional[SSETicketManager] = None


def get_sse_ticket_manager() -> SSETicketManager:
    """获取 SSE Ticket 管理器单例"""
    global _sse_ticket_manager
    if _sse_ticket_manager is None:
        _sse_ticket_manager = SSETicketManager()
    return _sse_ticket_manager
