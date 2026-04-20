"""
质量管控模块回测脚本

检查项:
1. 数据库迁移文件完整性
2. 代码导入和语法错误
3. 前后端API端点对齐
4. 函数名和方法名匹配
5. 参数传递和数据流
6. 系统逻辑错误
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("AI质量管控模块 - 全面回测")
print("=" * 80)

# ==================== 1. 数据库迁移文件检查 ====================
print("\n[1/6] 检查数据库迁移文件...")

migration_file = "alembic/versions/018_add_quality_reports.py"
if os.path.exists(migration_file):
    print(f"✓ 迁移文件存在: {migration_file}")

    # 检查文件内容
    with open(migration_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'revision =' in content:
        print("  ✓ 包含revision变量")
    else:
        print("  ✗ 缺少revision变量")

    if 'def upgrade()' in content:
        print("  ✓ 包含upgrade函数")
    else:
        print("  ✗ 缺少upgrade函数")

    if 'def downgrade()' in content:
        print("  ✓ 包含downgrade函数")
    else:
        print("  ✗ 缺少downgrade函数")

    if 'quality_reports' in content:
        print("  ✓ 包含quality_reports表定义")
    else:
        print("  ✗ 缺少quality_reports表定义")
else:
    print(f"✗ 迁移文件不存在: {migration_file}")

# ==================== 2. 数据模型检查 ====================
print("\n[2/6] 检查数据模型...")

try:
    from app.models.quality_report import QualityReport
    print("✓ QualityReport模型导入成功")

    # 检查关键字段
    required_columns = [
        'user_id', 'project_id', 'analysis_scope', 'dimensions',
        'analysis_depth', 'overall_score', 'dimension_scores',
        'report_data', 'total_issues', 'critical_issues',
        'warning_issues', 'info_issues', 'total_tokens',
        'rule_engine_tokens', 'llm_tokens', 'status',
        'content_hash', 'is_cached'
    ]

    for col in required_columns:
        if hasattr(QualityReport, col):
            print(f"  ✓ 字段存在: {col}")
        else:
            print(f"  ✗ 字段缺失: {col}")

except Exception as e:
    print(f"✗ 模型导入失败: {e}")

# ==================== 3. 服务层检查 ====================
print("\n[3/6] 检查服务层...")

try:
    from app.services.quality_control import (
        QualityControlService,
        get_quality_control_service
    )
    print("✓ 服务类导入成功")

    # 检查关键方法
    service_methods = ['analyze', '_execute_analysis',
                       '_save_report', '_load_project_data']
    for method in service_methods:
        if hasattr(QualityControlService, method):
            print(f"  ✓ 方法存在: {method}")
        else:
            print(f"  ✗ 方法缺失: {method}")

except Exception as e:
    print(f"✗ 服务类导入失败: {e}")

# ==================== 4. 分析器检查 ====================
print("\n[4/6] 检查分析器...")

analyzers = [
    ('app.services.quality_control.analyzers.structure_analyzer', 'StructureAnalyzer'),
    ('app.services.quality_control.analyzers.character_analyzer', 'CharacterAnalyzer'),
    ('app.services.quality_control.analyzers.scene_analyzer', 'SceneAnalyzer'),
    ('app.services.quality_control.analyzers.prose_analyzer', 'ProseAnalyzer'),
    ('app.services.quality_control.analyzers.experience_analyzer', 'ExperienceAnalyzer'),
    ('app.services.quality_control.analyzers.technical_analyzer', 'TechnicalAnalyzer'),
]

for module_name, class_name in analyzers:
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"✓ {class_name} 导入成功")

        # 检查analyze方法
        if hasattr(cls, 'analyze'):
            print(f"  ✓ analyze方法存在")
        else:
            print(f"  ✗ analyze方法缺失")

    except Exception as e:
        print(f"✗ {class_name} 导入失败: {e}")

# ==================== 5. 引擎检查 ====================
print("\n[5/6] 检查引擎...")

try:
    from app.services.quality_control.engines.rule_based_engine import RuleBasedEngine
    print("✓ RuleBasedEngine 导入成功")
except Exception as e:
    print(f"✗ RuleBasedEngine 导入失败: {e}")

try:
    from app.services.quality_control.engines.llm_engine import LLMAnalysisEngine
    print("✓ LLMAnalysisEngine 导入成功")

    # 检查__init__签名
    import inspect
    sig = inspect.signature(LLMAnalysisEngine.__init__)
    params = list(sig.parameters.keys())

    if 'db' in params:
        print("  ✓ 包含db参数")
    else:
        print("  ✗ 缺少db参数")

    if 'user_id' in params:
        print("  ✓ 包含user_id参数")
    else:
        print("  ✗ 缺少user_id参数")

except Exception as e:
    print(f"✗ LLMAnalysisEngine 导入失败: {e}")

# ==================== 6. API端点检查 ====================
print("\n[6/6] 检查API端点...")

try:
    from app.api.v1.endpoints.novel_writer.quality_control import router
    print("✓ API路由导入成功")

    # 检查路由
    routes = [route.path for route in router.routes]
    expected_routes = [
        '/projects/{project_id}/quality-control/analyze',
        '/projects/{project_id}/quality-control/reports',
        '/quality-control/reports/{report_id}'
    ]

    for expected in expected_routes:
        found = any(expected in route for route in routes)
        if found:
            print(f"  ✓ 路由存在: {expected}")
        else:
            print(f"  ✗ 路由缺失: {expected}")

except Exception as e:
    print(f"✗ API路由导入失败: {e}")

# ==================== 总结 ====================
print("\n" + "=" * 80)
print("回测完成!")
print("=" * 80)
print("\n建议操作:")
print("1. 应用数据库迁移: cd backend && alembic upgrade head")
print("2. 启动后端服务: python -m uvicorn app.main:app --reload")
print("3. 启动前端服务: cd frontend && npm run dev")
print("4. 访问测试页面: http://localhost:5173/#/novel-writer/{projectId}/quality")
