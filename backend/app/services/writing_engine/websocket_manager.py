"""
多Agent协作文学作品生成系统 - WebSocket管理器

模块: services.writing_engine
文件: websocket_manager.py
功能: 管理WebSocket连接，实现实时进度推送和状态通知

依赖关系:
    - 依赖: fastapi.WebSocket, app.core.logger
    - 被依赖: WritingPipeline, API层

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant

[2026-03-28] 多Agent重构: 统一WebSocket消息type值，添加task_complete/task_failed方法
"""
import json
from typing import Dict, Set, Any, Optional
from asyncio import Lock

from fastapi import WebSocket

from app.core.logger import get_logger


logger = get_logger("writing_engine.websocket_manager")


class WebSocketManager:
    """WebSocket连接管理器
    
    管理多个写作任务的WebSocket连接，支持：
    - 连接注册和注销
    - 按任务分组广播消息
    - 进度推送和状态变更通知
    
    线程安全：使用asyncio.Lock保护共享资源。
    """
    
    def __init__(self):
        """初始化WebSocket管理器"""
        # 按task_id分组的连接集合
        self._connections: Dict[int, Set[WebSocket]] = {}
        
        # 连接锁，保护共享资源
        self._lock = Lock()
    
    async def connect(self, task_id: int, websocket: WebSocket) -> None:
        """接受并注册WebSocket连接
        
        Args:
            task_id: 任务ID
            websocket: WebSocket连接对象
        """
        # 接受连接
        await websocket.accept()
        
        # 注册连接
        async with self._lock:
            if task_id not in self._connections:
                self._connections[task_id] = set()
            self._connections[task_id].add(websocket)
        
        logger.info(f"WebSocket连接已注册: task_id={task_id}, 当前连接数={len(self._connections.get(task_id, set()))}")
    
    async def disconnect(self, task_id: int, websocket: WebSocket) -> None:
        """移除WebSocket连接
        
        Args:
            task_id: 任务ID
            websocket: WebSocket连接对象
        """
        async with self._lock:
            if task_id in self._connections:
                self._connections[task_id].discard(websocket)
                
                # 如果没有连接了，移除task_id键
                if not self._connections[task_id]:
                    del self._connections[task_id]
        
        logger.info(f"WebSocket连接已移除: task_id={task_id}")
    
    async def broadcast(self, task_id: int, message: Dict[str, Any]) -> int:
        """向指定任务的所有连接广播消息
        
        Args:
            task_id: 任务ID
            message: 消息字典，将被JSON序列化
            
        Returns:
            int: 成功发送的连接数
        """
        connections = self._connections.get(task_id, set())
        if not connections:
            logger.debug(f"没有活跃的WebSocket连接: task_id={task_id}")
            return 0
        
        message_json = json.dumps(message, ensure_ascii=False)
        success_count = 0
        
        # 收集需要移除的断开连接
        disconnected = set()
        
        for websocket in connections:
            try:
                await websocket.send_text(message_json)
                success_count += 1
            except Exception as e:
                logger.warning(f"发送消息失败，连接将被移除: task_id={task_id}, error={str(e)}")
                disconnected.add(websocket)
        
        # 移除断开的连接
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._connections.get(task_id, set()).discard(ws)
        
        return success_count
    
    async def send_progress(
        self,
        task_id: int,
        agent_name: str,
        status: str,
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """发送进度推送消息
        
        Args:
            task_id: 任务ID
            agent_name: Agent名称
            status: Agent状态（如 "started", "processing", "completed", "failed"）
            data: 附加数据（可选）
            
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "task_progress",
            "task_id": task_id,
            "agent_name": agent_name,
            "status": status,
            "data": data or {},
            "timestamp": self._get_timestamp()
        }
        
        return await self.broadcast(task_id, message)
    
    async def send_status_change(
        self,
        task_id: int,
        old_status: str,
        new_status: str
    ) -> int:
        """发送状态变更通知
        
        Args:
            task_id: 任务ID
            old_status: 旧状态
            new_status: 新状态
            
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "status_change",
            "task_id": task_id,
            "old_status": old_status if isinstance(old_status, str) else old_status.value,
            "new_status": new_status if isinstance(new_status, str) else new_status.value,
            "timestamp": self._get_timestamp()
        }
        
        return await self.broadcast(task_id, message)
    
    async def send_unit_progress(
        self,
        task_id: int,
        unit_index: int,
        unit_title: str,
        status: str,
        progress: float = 0.0
    ) -> int:
        """发送单元进度推送
        
        Args:
            task_id: 任务ID
            unit_index: 单元序号
            unit_title: 单元标题
            status: 单元状态
            progress: 进度百分比（0-100）
            
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "unit_progress",
            "task_id": task_id,
            "unit_index": unit_index,
            "unit_title": unit_title,
            "status": status,
            "progress": progress,
            "timestamp": self._get_timestamp()
        }
        
        return await self.broadcast(task_id, message)
    
    async def send_scene_progress(
        self,
        task_id: int,
        unit_index: int,
        scene_index: int,
        scene_title: str,
        status: str
    ) -> int:
        """发送场景进度推送
        
        Args:
            task_id: 任务ID
            unit_index: 单元序号
            scene_index: 场景序号
            scene_title: 场景标题
            status: 场景状态
            
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "scene_progress",
            "task_id": task_id,
            "unit_index": unit_index,
            "scene_index": scene_index,
            "scene_title": scene_title,
            "status": status,
            "timestamp": self._get_timestamp()
        }
        
        return await self.broadcast(task_id, message)
    
    async def send_error(
        self,
        task_id: int,
        error_message: str,
        agent_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> int:
        """发送错误通知
        
        Args:
            task_id: 任务ID
            error_message: 错误消息
            agent_name: 相关Agent名称（可选）
            details: 错误详情（可选）
            
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "error",
            "task_id": task_id,
            "error_message": error_message,
            "agent_name": agent_name,
            "details": details or {},
            "timestamp": self._get_timestamp()
        }
        
        return await self.broadcast(task_id, message)
    
    async def send_task_progress(
        self,
        task_id: int,
        completed_units: int,
        total_units: int,
        current_unit: Optional[int] = None,
        current_scene: Optional[int] = None
    ) -> int:
        """发送整体任务进度推送
            
        前端期望格式：
        {
            "type": "task_progress",
            "task_id": int,
            "data": {
                "completed_units": int,
                "total_units": int,
                "current_unit": int,
                "current_scene": int
            },
            "timestamp": str
        }
            
        Args:
            task_id: 任务ID
            completed_units: 已完成单元数
            total_units: 总单元数
            current_unit: 当前处理的单元序号（可选）
            current_scene: 当前处理的场景序号（可选）
                
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "task_progress",
            "task_id": task_id,
            "data": {
                "completed_units": completed_units,
                "total_units": total_units,
                "current_unit": current_unit,
                "current_scene": current_scene
            },
            "timestamp": self._get_timestamp()
        }
            
        return await self.broadcast(task_id, message)
    
    async def send_statistics(
        self,
        task_id: int,
        stats: Dict[str, Any]
    ) -> int:
        """发送统计信息
            
        前端期望格式：
        {
            "type": "statistics",
            "task_id": int,
            "stats": {...},
            "timestamp": str
        }
            
        Args:
            task_id: 任务ID
            stats: 统计数据
                
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "statistics",
            "task_id": task_id,
            "stats": stats,
            "timestamp": self._get_timestamp()
        }
            
        return await self.broadcast(task_id, message)
    
    async def send_task_complete(
        self,
        task_id: int,
        total_units: int,
        total_word_count: int,
        total_tokens: int,
        total_cost: float,
        duration_sec: float
    ) -> int:
        """发送任务完成通知
        
        Args:
            task_id: 任务ID
            total_units: 完成的单元数
            total_word_count: 总字数
            total_tokens: 总Token消耗
            total_cost: 总费用
            duration_sec: 总耗时(秒)
            
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "task_complete",
            "task_id": task_id,
            "data": {
                "total_units": total_units,
                "total_word_count": total_word_count,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "duration_sec": duration_sec
            },
            "timestamp": self._get_timestamp()
        }
        
        return await self.broadcast(task_id, message)
    
    async def send_task_failed(
        self,
        task_id: int,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> int:
        """发送任务失败通知
        
        Args:
            task_id: 任务ID
            error_message: 错误消息
            error_details: 错误详情（可选）
            
        Returns:
            int: 成功发送的连接数
        """
        message = {
            "type": "task_failed",
            "task_id": task_id,
            "data": {
                "error": error_message,
                "details": error_details or {}
            },
            "timestamp": self._get_timestamp()
        }
        
        return await self.broadcast(task_id, message)
    
    async def send_workflow_step(
        self,
        task_id: int,
        step: str,
        status: str,
        message: str,
        agent_name: Optional[str] = None,
        unit_index: Optional[int] = None,
        scene_index: Optional[int] = None,
        icon: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """发送工作流步骤消息
        
        前端期望格式：
        {
            "type": "workflow_step",
            "task_id": int,
            "data": {
                "step": str,  // 步骤标识: structuring, writing, reviewing, assembling
                "status": str,  // running, done, error
                "message": str,  // 显示消息
                "agent_name": str,  // Agent名称
                "unit_index": int,  // 单元索引（可选）
                "scene_index": int,  // 场景索引（可选）
                "icon": str  // 图标名称
            },
            "timestamp": str
        }
        
        Args:
            task_id: 任务ID
            step: 步骤标识（如 structuring, writing, reviewing, assembling）
            status: 状态（running, done, error）
            message: 显示消息
            agent_name: Agent名称（可选）
            unit_index: 单元索引（可选）
            scene_index: 场景索引（可选）
            icon: 图标名称（可选）
            data: 附加数据（可选）
                
        Returns:
            int: 成功发送的连接数
        """
        msg_data = {
            "step": step,
            "status": status,
            "message": message
        }
        
        if agent_name:
            msg_data["agent_name"] = agent_name
        if unit_index is not None:
            msg_data["unit_index"] = unit_index
        if scene_index is not None:
            msg_data["scene_index"] = scene_index
        if icon:
            msg_data["icon"] = icon
        if data:
            msg_data.update(data)
            
        msg = {
            "type": "workflow_step",
            "task_id": task_id,
            "data": msg_data,
            "timestamp": self._get_timestamp()
        }
        
        return await self.broadcast(task_id, msg)
    
    def get_connection_count(self, task_id: int) -> int:
        """获取指定任务的连接数
        
        Args:
            task_id: 任务ID
            
        Returns:
            int: 连接数
        """
        return len(self._connections.get(task_id, set()))
    
    def get_total_connections(self) -> int:
        """获取所有任务的总连接数
        
        Returns:
            int: 总连接数
        """
        return sum(len(conns) for conns in self._connections.values())
    
    def get_active_tasks(self) -> list:
        """获取有活跃连接的任务ID列表
        
        Returns:
            list: 任务ID列表
        """
        return list(self._connections.keys())
    
    async def close_all(self) -> None:
        """关闭所有WebSocket连接"""
        async with self._lock:
            for task_id, connections in list(self._connections.items()):
                for websocket in connections:
                    try:
                        await websocket.close()
                    except Exception as e:
                        logger.warning(f"关闭WebSocket连接失败: task_id={task_id}, error={str(e)}")
            
            self._connections.clear()
            logger.info("所有WebSocket连接已关闭")
    
    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳（ISO格式）
        
        Returns:
            str: ISO格式时间戳
        """
        from datetime import datetime
        return datetime.now().isoformat()


# 全局WebSocket管理器实例
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """获取全局WebSocket管理器实例"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


def reset_websocket_manager() -> None:
    """重置全局WebSocket管理器"""
    global _websocket_manager
    _websocket_manager = WebSocketManager()
