"""
监控服务
提供API请求统计、资源监控、健康检查等功能
"""
import time
import psutil
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field

from app.core.logger import get_logger
from app.core.config import get_settings

logger = get_logger("monitoring")
settings = get_settings()


@dataclass
class RequestMetric:
    """请求指标"""
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SystemMetrics:
    """系统指标"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MonitoringService:
    """监控服务"""
    
    def __init__(self):
        # 请求指标存储（内存中，可替换为Redis）
        self._request_metrics: List[RequestMetric] = []
        self._max_metrics = 10000  # 最大存储数量
        
        # 统计缓存
        self._endpoint_stats: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0,
            "total_time": 0,
            "errors": 0,
            "avg_time": 0
        })
        
        # 每日请求统计
        self._daily_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total_requests": 0,
            "unique_users": set(),
            "errors": 0
        })
        
        # 启动时间
        self._start_time = datetime.utcnow()
    
    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> None:
        """
        记录请求指标
        
        Args:
            endpoint: API端点
            method: HTTP方法
            status_code: 状态码
            response_time_ms: 响应时间（毫秒）
            tenant_id: 租户ID
            user_id: 用户ID
        """
        metric = RequestMetric(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        # 添加到列表
        self._request_metrics.append(metric)
        
        # 超过最大数量时清理旧数据
        if len(self._request_metrics) > self._max_metrics:
            self._request_metrics = self._request_metrics[-self._max_metrics:]
        
        # 更新端点统计
        key = f"{method}:{endpoint}"
        stats = self._endpoint_stats[key]
        stats["count"] += 1
        stats["total_time"] += response_time_ms
        stats["avg_time"] = stats["total_time"] / stats["count"]
        if status_code >= 400:
            stats["errors"] += 1
        
        # 更新每日统计
        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily = self._daily_stats[today]
        daily["total_requests"] += 1
        if user_id:
            daily["unique_users"].add(user_id)
        if status_code >= 400:
            daily["errors"] += 1
    
    def get_system_metrics(self) -> SystemMetrics:
        """
        获取系统指标
        
        Returns:
            系统指标数据
        """
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # 内存使用
        memory = psutil.virtual_memory()
        
        # 磁盘使用
        disk = psutil.disk_usage('/')
        
        # 网络IO
        net_io = psutil.net_io_counters()
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            memory_total_mb=memory.total / (1024 * 1024),
            disk_percent=disk.percent,
            disk_used_gb=disk.used / (1024 * 1024 * 1024),
            disk_total_gb=disk.total / (1024 * 1024 * 1024),
            network_bytes_sent=net_io.bytes_sent,
            network_bytes_recv=net_io.bytes_recv
        )
    
    def get_api_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取API统计
        
        Args:
            hours: 统计时间范围（小时）
        
        Returns:
            API统计数据
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # 过滤时间范围内的请求
        recent_metrics = [
            m for m in self._request_metrics
            if m.timestamp >= cutoff
        ]
        
        total_requests = len(recent_metrics)
        if total_requests == 0:
            return {
                "total_requests": 0,
                "avg_response_time_ms": 0,
                "error_rate": 0,
                "requests_per_minute": 0,
                "top_endpoints": [],
                "status_distribution": {}
            }
        
        # 计算统计指标
        total_time = sum(m.response_time_ms for m in recent_metrics)
        errors = sum(1 for m in recent_metrics if m.status_code >= 400)
        
        # 状态码分布
        status_dist = defaultdict(int)
        for m in recent_metrics:
            status_dist[m.status_code] += 1
        
        # 端点排名
        endpoint_counts = defaultdict(int)
        for m in recent_metrics:
            endpoint_counts[f"{m.method}:{m.endpoint}"] += 1
        
        top_endpoints = sorted(
            endpoint_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # 每分钟请求数
        minutes = max(hours * 60, 1)
        rpm = total_requests / minutes
        
        return {
            "total_requests": total_requests,
            "avg_response_time_ms": total_time / total_requests,
            "error_rate": errors / total_requests * 100,
            "requests_per_minute": round(rpm, 2),
            "top_endpoints": [
                {"endpoint": e, "count": c} for e, c in top_endpoints
            ],
            "status_distribution": dict(status_dist)
        }
    
    def get_tenant_stats(self, tenant_id: int, hours: int = 24) -> Dict[str, Any]:
        """
        获取租户统计
        
        Args:
            tenant_id: 租户ID
            hours: 统计时间范围（小时）
        
        Returns:
            租户统计数据
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # 过滤租户请求
        tenant_metrics = [
            m for m in self._request_metrics
            if m.tenant_id == tenant_id and m.timestamp >= cutoff
        ]
        
        return {
            "tenant_id": tenant_id,
            "total_requests": len(tenant_metrics),
            "errors": sum(1 for m in tenant_metrics if m.status_code >= 400),
            "avg_response_time_ms": (
                sum(m.response_time_ms for m in tenant_metrics) / len(tenant_metrics)
                if tenant_metrics else 0
            )
        }
    
    def get_uptime(self) -> Dict[str, Any]:
        """
        获取运行时间
        
        Returns:
            运行时间数据
        """
        now = datetime.utcnow()
        uptime = now - self._start_time
        
        return {
            "start_time": self._start_time.isoformat(),
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_human": str(uptime).split('.')[0]  # 去掉微秒
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态
        """
        metrics = self.get_system_metrics()
        
        # 定义阈值
        cpu_threshold = 90
        memory_threshold = 90
        disk_threshold = 90
        
        issues = []
        if metrics.cpu_percent > cpu_threshold:
            issues.append(f"CPU使用率过高: {metrics.cpu_percent}%")
        if metrics.memory_percent > memory_threshold:
            issues.append(f"内存使用率过高: {metrics.memory_percent}%")
        if metrics.disk_percent > disk_threshold:
            issues.append(f"磁盘使用率过高: {metrics.disk_percent}%")
        
        return {
            "status": "healthy" if not issues else "warning",
            "issues": issues,
            "metrics": {
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "disk_percent": metrics.disk_percent
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def clear_old_metrics(self, days: int = 7) -> int:
        """
        清理旧指标数据
        
        Args:
            days: 保留天数
        
        Returns:
            清理的数量
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        original_count = len(self._request_metrics)
        
        self._request_metrics = [
            m for m in self._request_metrics
            if m.timestamp >= cutoff
        ]
        
        cleared = original_count - len(self._request_metrics)
        if cleared > 0:
            logger.info(f"清理了 {cleared} 条旧指标数据")
        
        return cleared


# 全局监控服务实例
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """获取监控服务实例"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service


# 便捷函数
def record_request(
    endpoint: str,
    method: str,
    status_code: int,
    response_time_ms: float,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> None:
    """记录请求"""
    service = get_monitoring_service()
    service.record_request(endpoint, method, status_code, response_time_ms, tenant_id, user_id)


def get_system_metrics() -> SystemMetrics:
    """获取系统指标"""
    return get_monitoring_service().get_system_metrics()


def get_api_stats(hours: int = 24) -> Dict[str, Any]:
    """获取API统计"""
    return get_monitoring_service().get_api_stats(hours)
