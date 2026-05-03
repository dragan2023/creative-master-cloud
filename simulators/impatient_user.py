"""急性子用户模拟器"""
from .base_simulator import BaseUserSimulator

class ImpatientUserSimulator(BaseUserSimulator):
    """操作间隔50-200ms"""
    
    async def simulate(self, scenario: dict):
        steps = scenario.get('steps', [])
        for step in steps:
            if 'navigate' in step:
                await self.page.goto(step['navigate'])
                await self._delay(100)
            elif 'fill_form' in step:
                for selector, value in step['fill_form'].items():
                    await self.fill(selector, str(value), delay_ms=80)
            elif 'click' in step:
                await self.click(step['click'], delay_ms=100)
            elif 'rapid_click' in step:
                cfg = step['rapid_click']
                for _ in range(cfg.get('count', 3)):
                    await self.page.click(cfg['selector'])
                    await self._delay(cfg.get('interval_ms', 100))
            elif 'wait' in step:
                await self.page.wait_for_timeout(step['wait'])
