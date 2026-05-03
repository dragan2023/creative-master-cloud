"""质量保证主引擎 v2.0"""
import os
import asyncio
import json
from datetime import datetime
from pathlib import Path

from core.config_loader import ProjectConfigLoader
from core.service_manager import ServiceManager
from core.browser_engine import BrowserEngine
from core.models import Issue, FixRecord

# 新增组件
from loggers import BackendLogger, FrontendLogger, ConsoleLogger, BehaviorLogger
from simulators import ImpatientUserSimulator, HesitantUserSimulator
from detectors import (DuplicateSubmitDetector, InputValidationDetector,
                      ErrorHandlingDetector, PerformanceMonitor, UXFlowDetector)
from fix_strategies import DuplicateSubmitFix, ErrorMessageFix

class QualityAssuranceEngineV2:
    """增强版QA引擎"""
    
    def __init__(self, project_name: str, headless: bool = True, auto_fix: bool = True):
        self.project_name = project_name
        self.headless = headless  
        self.auto_fix = auto_fix
        
        # 基础组件
        self.config = ProjectConfigLoader(project_name)
        self.service_mgr = ServiceManager(self.config)
        self.browser = BrowserEngine(self.config)
        
        # 日志组件
        backend_log_path = self.config.config.get('logging', {}).get(
            'backend_log_path', 'backend/logs')
        self.backend_logger = BackendLogger(backend_log_path)
        self.frontend_logger = FrontendLogger()
        self.console_logger = ConsoleLogger()
        self.behavior_logger = BehaviorLogger()
        
        # 检测器
        self.detectors = {
            'duplicate': DuplicateSubmitDetector(),
            'input': InputValidationDetector(),
            'error': ErrorHandlingDetector(),
            'performance': PerformanceMonitor(),
            'ux': UXFlowDetector()
        }
        
        # 修复策略
        self.fix_strategies = [
            DuplicateSubmitFix(),
            ErrorMessageFix()
        ]
        
        self.all_issues = []
        self.all_fixes = []
        
    async def run_full_test(self):
        """执行全量测试"""
        print("=" * 70)
        print(f"开始全量测试: {self.config.config['project']['name']}")
        print("=" * 70)
        
        try:
            # 1. 启动服务
            print("\n[1/7] 服务检查...")
            if not getattr(self, 'skip_services', False):
                await self.service_mgr.start_all_services()
            
            # 2. 初始化浏览器+日志拦截
            print("\n[2/7] 初始化浏览器...")
            await self.browser.initialize(headless=self.headless)
            self.frontend_logger.setup(self.browser.page)
            self.console_logger.setup(self.browser.page)
            
            # 3. 登录
            print("\n[3/7] 登录...")
            username = os.getenv('TEST_USERNAME', 'admin')
            password = os.getenv('TEST_PASSWORD', '123456')
            await self.browser.login(username, password)
            
            # 4. 执行测试场景
            print("\n[4/7] 执行测试场景...")
            await self._run_scenarios()
            
            # 5. 运行检测器
            print("\n[5/7] 运行检测器...")
            await self._run_detectors()
            
            # 6. 自动修复
            print("\n[6/7] 自动修复...")
            if self.auto_fix:
                await self._apply_fixes()
            
            # 7. 生成报告
            print("\n[7/7] 生成报告...")
            report_path = await self._generate_report()
            
            # 8. 保存日志
            await self._save_logs()
            
            print("\n" + "=" * 70)
            print(f"✅ 测试完成! 发现 {len(self.all_issues)} 个问题")
            print(f"📄 报告: {report_path}")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.browser.close()
    
    async def _run_scenarios(self):
        """执行测试场景"""
        # 简化版: 遍历配置的模块
        for module in self.config.get_test_modules():
            print(f"  → {module['name']}")
            await self.browser.navigate_to_module(module['path'])
            await asyncio.sleep(2)
            self.behavior_logger.log('navigate', url=module['path'])
    
    async def _run_detectors(self):
        """运行所有检测器"""
        # 防重复提交
        issues = await self.detectors['duplicate'].detect(
            self.browser.page,
            self.behavior_logger.actions,
            self.frontend_logger.requests
        )
        self.all_issues.extend(issues)
        
        # 性能检测
        issues = await self.detectors['performance'].detect(self.browser.page)
        self.all_issues.extend(issues)
        
        # 错误处理
        issues = await self.detectors['error'].detect(
            self.browser.page,
            self.console_logger.errors,
            self.frontend_logger.failed
        )
        self.all_issues.extend(issues)
        
        print(f"  发现 {len(self.all_issues)} 个问题")
    
    async def _apply_fixes(self):
        """应用修复策略"""
        for issue in self.all_issues:
            for strategy in self.fix_strategies:
                if strategy.can_fix(issue):
                    fix = await strategy.apply(issue)
                    self.all_fixes.append(fix)
                    break
        
        print(f"  已处理 {len(self.all_fixes)} 个修复")
    
    async def _generate_report(self):
        """生成HTML报告"""
        from jinja2 import Template
        
        stats = {
            'total': len(self.all_issues),
            'critical': len([i for i in self.all_issues if i.severity == 'critical']),
            'high': len([i for i in self.all_issues if i.severity == 'high']),
            'medium': len([i for i in self.all_issues if i.severity == 'medium'])
        }
        
        template_path = Path(__file__).parent.parent / 'templates/enhanced_report.html'
        if template_path.exists():
            template = Template(template_path.read_text(encoding='utf-8'))
        else:
            template = Template("<h1>报告模板缺失</h1>")
        
        html = template.render(
            project_name=self.project_name,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'),
            issues=self.all_issues,
            fixes=self.all_fixes,
            stats=stats
        )
        
        reports_dir = Path(__file__).parent.parent / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"测试报告_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
        filepath = reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return str(filepath)
    
    async def _save_logs(self):
        """保存日志文件"""
        logs_dir = Path(__file__).parent.parent / 'reports/logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存行为日志
        behavior_file = logs_dir / f"behavior_{datetime.now().strftime('%Y%m%d')}.json"
        with open(behavior_file, 'w', encoding='utf-8') as f:
            json.dump(self.behavior_logger.export_json(), f, ensure_ascii=False, indent=2)
        
        print(f"  日志已保存至 {logs_dir}")
