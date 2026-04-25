"""
monitoring/_ws.py - WebSocket消息推送 Mixin

包含 MonitoringWSMixin，提供 WebSocket 消息推送方法。

@date: 2026-04-24
@version: v3.0.0
"""
from typing import Any, Optional


class MonitoringWSMixin:
    """WebSocket消息推送 Mixin

    提供 _send_ws_message 方法 - 安全地发送WebSocket消息。
    """

    # 由主类提供的属性
    _ws_manager: Optional[Any]
    _current_task: Optional[Any]
    logger: Any

    async def _send_ws_message(self, msg_type: str, data: dict) -> None:
        """发送WebSocket消息的辅助方法

        安全地发送WebSocket消息，失败不影响主流程。

        Args:
            msg_type: 消息类型
            data: 消息数据
        """
        if not self._ws_manager:
            self.logger.warning(f"[WS消息] 发送失败: _ws_manager未设置, msg_type={msg_type}")
            return
        if not self._current_task:
            self.logger.warning(f"[WS消息] 发送失败: _current_task未设置, msg_type={msg_type}")
            return

        try:
            task_id = self._current_task.id

            if msg_type == "task_progress":
                await self._ws_manager.send_task_progress(
                    task_id=task_id,
                    completed_units=data.get("completed_units", 0),
                    total_units=data.get("total_units", 0),
                    current_unit=data.get("current_unit"),
                    current_scene=data.get("current_scene")
                )
            elif msg_type == "unit_progress":
                await self._ws_manager.send_unit_progress(
                    task_id=task_id,
                    unit_index=data.get("unit_index", 0),
                    unit_title=data.get("unit_title", ""),
                    status=data.get("status", "processing"),
                    progress=data.get("progress", 0.0)
                )
            elif msg_type == "scene_progress":
                await self._ws_manager.send_scene_progress(
                    task_id=task_id,
                    unit_index=data.get("unit_index", 0),
                    scene_index=data.get("scene_index", 0),
                    scene_title=data.get("scene_title", ""),
                    status=data.get("status", "pending")
                )
            elif msg_type == "statistics":
                await self._ws_manager.send_statistics(
                    task_id=task_id,
                    stats=data
                )
            elif msg_type == "workflow_step":
                await self._ws_manager.send_workflow_step(
                    task_id=task_id,
                    step=data.get("step", ""),
                    status=data.get("status", "running"),
                    message=data.get("message", ""),
                    agent_name=data.get("agent_name"),
                    unit_index=data.get("unit_index"),
                    scene_index=data.get("scene_index"),
                    icon=data.get("icon"),
                    data=data.get("extra_data")
                )
            elif msg_type == "unit_quality_control":
                result = await self._ws_manager.send_custom_message(
                    task_id=task_id,
                    msg_type="unit_quality_control",
                    data=data
                )
                self.logger.info(
                    f"[WS消息] unit_quality_control已发送: "
                    f"task_id={task_id}, unit_index={data.get('unit_index')}, "
                    f"status={data.get('status')}, 连接数={result}"
                )
        except Exception as e:
            self.logger.warning(f"WebSocket消息发送失败: type={msg_type}, error={str(e)}")
