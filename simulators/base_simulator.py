"""基础模拟器"""
import asyncio
import random
from abc import ABC, abstractmethod

class BaseUserSimulator(ABC):
    """用户模拟器基类"""
    
    def __init__(self, browser, config):
        self.browser = browser
        self.config = config
        self.page = browser.page
        self.action_log = []
        
    @abstractmethod
    async def simulate(self, scenario: dict):
        pass
    
    async def click(self, selector: str, delay_ms: int = 100):
        """点击并延迟"""
        await self.page.click(selector)
        await self._delay(delay_ms)
        
    async def fill(self, selector: str, text: str, delay_ms: int = 150):
        """输入并延迟"""
        await self.page.fill(selector, text)
        await self._delay(delay_ms)
    
    async def _delay(self, base_ms: int, variance: float = 0.3):
        """随机延迟"""
        delay = base_ms * (1 + random.uniform(-variance, variance))
        await asyncio.sleep(max(10, delay) / 1000)
