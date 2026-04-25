"""
monitoring/_base.py - 中断检测与处理 Mixin

包含 MonitoringBaseMixin，提供中断检测、处理和追踪器获取方法。

@date: 2026-04-24
@version: v3.0.0
"""
from typing import Any, Dict, Optional


class MonitoringBaseMixin:
    """监控基础 Mixin

    提供：
    - _check_interrupted: 检查是否被中断
    - interrupt: 中断当前任务
    - get_character_tracker: 获取人物状态追踪器实例
    """

    # 由主类提供的属性
    _interrupt_event: Any
    _agent_instances: Dict[Any, Any]
    _current_task: Any
    logger: Any
    _character_tracker: Optional[Any]

    # 从其他 Mixin 继承的方法
    _send_ws_message: callable

    def _check_interrupted(self) -> bool:
        """检查是否被中断

        Returns:
            True表示已被中断
        """
        return not self._interrupt_event.is_set()

    async def interrupt(self) -> None:
        """中断当前任务"""
        self.logger.info("收到中断信号，正在停止任务...")
        self._interrupt_event.clear()

        for agent_role, agent in self._agent_instances.items():
            try:
                if hasattr(agent, 'interrupt'):
                    await agent.interrupt()
                    self.logger.debug(f"已通知 {agent_role} Agent 中断")
            except Exception as e:
                self.logger.warning(f"通知 {agent_role} Agent 中断失败: {e}")

        if self._current_task:
            await self._send_ws_message("status_change", {
                "old_status": "running",
                "new_status": "interrupted",
                "message": "任务已被用户中断"
            })

    def get_character_tracker(self):
        """获取人物状态追踪器实例"""
        return self._character_tracker
