"""犹豫型用户模拟器"""
from .base_simulator import BaseUserSimulator

class HesitantUserSimulator(BaseUserSimulator):
    """操作间隔2-8秒"""
    
    async def simulate(self, scenario: dict):
        steps = scenario.get('steps', [])
        for step in steps:
            if 'navigate' in step:
                await self.page.goto(step['navigate'])
                await self._delay(3000)
            elif 'fill_form' in step:
                for selector, value in step['fill_form'].items():
                    await self.fill(selector, str(value), delay_ms=2000)
            elif 'click' in step:
                await self.click(step['click'], delay_ms=4000)
            elif 'wait' in step:
                await self.page.wait_for_timeout(step['wait'])
