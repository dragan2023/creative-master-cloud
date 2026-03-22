"""
告警服务
支持QQ、微信、邮件等多种告警方式
"""
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("alerting")
settings = get_settings()


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertMessage:
    """告警消息"""
    title: str
    content: str
    level: AlertLevel = AlertLevel.INFO
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class AlertChannel:
    """告警通道基类"""
    
    async def send(self, message: AlertMessage) -> bool:
        """发送告警"""
        raise NotImplementedError


class QQBotChannel(AlertChannel):
    """QQ机器人告警通道"""
    
    def __init__(self, webhook_url: str, group_id: Optional[str] = None):
        self.webhook_url = webhook_url
        self.group_id = group_id
    
    async def send(self, message: AlertMessage) -> bool:
        """发送QQ消息"""
        if not self.webhook_url:
            logger.warning("QQ机器人webhook未配置")
            return False
        
        # 构建消息
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨"
        }
        
        emoji = level_emoji.get(message.level, "📢")
        
        payload = {
            "message": f"{emoji} [{message.level.value.upper()}] {message.title}\n\n{message.content}\n\n时间: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        }
        
        if self.group_id:
            payload["group_id"] = self.group_id
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"QQ告警发送成功: {message.title}")
                        return True
                    else:
                        logger.error(f"QQ告警发送失败: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"QQ告警发送异常: {e}")
            return False


class WeChatChannel(AlertChannel):
    """微信告警通道（通过Server酱或企业微信）"""
    
    def __init__(
        self,
        serverchan_key: Optional[str] = None,
        wechat_webhook: Optional[str] = None
    ):
        self.serverchan_key = serverchan_key
        self.wechat_webhook = wechat_webhook
    
    async def send(self, message: AlertMessage) -> bool:
        """发送微信消息"""
        # 优先使用企业微信
        if self.wechat_webhook:
            return await self._send_wechat_webhook(message)
        
        # 使用Server酱
        if self.serverchan_key:
            return await self._send_serverchan(message)
        
        logger.warning("微信告警通道未配置")
        return False
    
    async def _send_serverchan(self, message: AlertMessage) -> bool:
        """通过Server酱发送"""
        url = f"https://sctapi.ftqq.com/{self.serverchan_key}.send"
        
        payload = {
            "title": f"[{message.level.value.upper()}] {message.title}",
            "desp": f"**级别**: {message.level.value}\n\n**内容**:\n\n{message.content}\n\n**时间**: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Server酱告警发送成功: {message.title}")
                        return True
                    else:
                        logger.error(f"Server酱告警发送失败: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Server酱告警发送异常: {e}")
            return False
    
    async def _send_wechat_webhook(self, message: AlertMessage) -> bool:
        """通过企业微信机器人发送"""
        level_color = {
            AlertLevel.INFO: "info",
            AlertLevel.WARNING: "warning",
            AlertLevel.ERROR: "warning",
            AlertLevel.CRITICAL: "warning"
        }
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"### [{message.level.value.upper()}] {message.title}\n\n{message.content}\n\n> 时间: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.wechat_webhook,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"企业微信告警发送成功: {message.title}")
                        return True
                    else:
                        logger.error(f"企业微信告警发送失败: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"企业微信告警发送异常: {e}")
            return False


class EmailChannel(AlertChannel):
    """邮件告警通道"""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_addr: str,
        to_addrs: List[str]
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
    
    async def send(self, message: AlertMessage) -> bool:
        """发送邮件"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart()
        msg['From'] = self.from_addr
        msg['To'] = ', '.join(self.to_addrs)
        msg['Subject'] = f"[{message.level.value.upper()}] {message.title}"
        
        body = f"""
级别: {message.level.value}
标题: {message.title}

内容:
{message.content}

时间: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        try:
            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_email_sync,
                msg
            )
            logger.info(f"邮件告警发送成功: {message.title}")
            return True
        except Exception as e:
            logger.error(f"邮件告警发送异常: {e}")
            return False
    
    def _send_email_sync(self, msg):
        """同步发送邮件"""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.from_addr, self.to_addrs, msg.as_string())


class AlertingService:
    """告警服务"""
    
    def __init__(self):
        self._channels: List[AlertChannel] = []
        self._alert_history: List[Dict[str, Any]] = []
        self._max_history = 1000
    
    def add_channel(self, channel: AlertChannel) -> None:
        """添加告警通道"""
        self._channels.append(channel)
    
    def configure_from_settings(self) -> None:
        """从配置加载告警通道"""
        # QQ机器人
        qq_webhook = getattr(settings, 'ALERT_QQ_WEBHOOK', None)
        qq_group = getattr(settings, 'ALERT_QQ_GROUP', None)
        if qq_webhook:
            self.add_channel(QQBotChannel(qq_webhook, qq_group))
        
        # 微信（Server酱）
        serverchan_key = getattr(settings, 'ALERT_SERVERCHAN_KEY', None)
        wechat_webhook = getattr(settings, 'ALERT_WECHAT_WEBHOOK', None)
        if serverchan_key or wechat_webhook:
            self.add_channel(WeChatChannel(serverchan_key, wechat_webhook))
        
        # 邮件
        smtp_host = getattr(settings, 'ALERT_SMTP_HOST', None)
        if smtp_host:
            self.add_channel(EmailChannel(
                smtp_host=smtp_host,
                smtp_port=getattr(settings, 'ALERT_SMTP_PORT', 587),
                smtp_user=getattr(settings, 'ALERT_SMTP_USER', ''),
                smtp_password=getattr(settings, 'ALERT_SMTP_PASSWORD', ''),
                from_addr=getattr(settings, 'ALERT_SMTP_FROM', ''),
                to_addrs=getattr(settings, 'ALERT_SMTP_TO', '').split(',')
            ))
    
    async def send_alert(
        self,
        title: str,
        content: str,
        level: AlertLevel = AlertLevel.INFO
    ) -> Dict[str, bool]:
        """
        发送告警
        
        Args:
            title: 告警标题
            content: 告警内容
            level: 告警级别
        
        Returns:
            各通道发送结果
        """
        message = AlertMessage(title=title, content=content, level=level)
        
        # 记录历史
        self._alert_history.append({
            "title": title,
            "content": content,
            "level": level.value,
            "timestamp": message.timestamp.isoformat()
        })
        
        # 清理历史
        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history:]
        
        # 发送到所有通道
        results = {}
        for channel in self._channels:
            channel_name = channel.__class__.__name__
            try:
                results[channel_name] = await channel.send(message)
            except Exception as e:
                logger.error(f"告警通道 {channel_name} 发送失败: {e}")
                results[channel_name] = False
        
        return results
    
    async def alert_system_error(self, error_msg: str) -> None:
        """系统错误告警"""
        await self.send_alert(
            title="系统错误",
            content=error_msg,
            level=AlertLevel.ERROR
        )
    
    async def alert_high_resource(self, resource_type: str, value: float) -> None:
        """资源使用过高告警"""
        await self.send_alert(
            title=f"{resource_type}使用率过高",
            content=f"当前{resource_type}使用率为 {value:.1f}%，请及时处理。",
            level=AlertLevel.WARNING
        )
    
    async def alert_service_down(self, service_name: str) -> None:
        """服务宕机告警"""
        await self.send_alert(
            title=f"服务宕机: {service_name}",
            content=f"{service_name} 服务已停止响应，请立即检查！",
            level=AlertLevel.CRITICAL
        )
    
    async def alert_anomaly(self, description: str) -> None:
        """异常行为告警"""
        await self.send_alert(
            title="检测到异常行为",
            content=description,
            level=AlertLevel.WARNING
        )
    
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取告警历史"""
        return self._alert_history[-limit:]


# 全局告警服务实例
_alerting_service: Optional[AlertingService] = None


def get_alerting_service() -> AlertingService:
    """获取告警服务实例"""
    global _alerting_service
    if _alerting_service is None:
        _alerting_service = AlertingService()
        _alerting_service.configure_from_settings()
    return _alerting_service


# 便捷函数
async def send_alert(title: str, content: str, level: AlertLevel = AlertLevel.INFO) -> Dict[str, bool]:
    """发送告警"""
    service = get_alerting_service()
    return await service.send_alert(title, content, level)


async def alert_system_error(error_msg: str) -> None:
    """系统错误告警"""
    await get_alerting_service().alert_system_error(error_msg)


async def alert_high_resource(resource_type: str, value: float) -> None:
    """资源使用过高告警"""
    await get_alerting_service().alert_high_resource(resource_type, value)
