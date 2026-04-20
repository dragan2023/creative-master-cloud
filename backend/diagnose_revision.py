"""
修订功能诊断脚本
用于测试修订API端点是否正常工作
"""
from app.core.logger import get_logger
from app.core.database import get_db, async_session_maker
import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


logger = get_logger("revision_diagnostic")


async def diagnostic_revision_api():
    """诊断修订API"""
    print("=" * 60)
    print("修订功能诊断工具")
    print("=" * 60)

    # 1. 检查数据库连接
    print("\n[1/5] 检查数据库连接...")
    try:
        async with async_session_maker() as db:
            print("✓ 数据库连接正常")
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return

    # 2. 检查orchestrator导入
    print("\n[2/5] 检查orchestrator导入...")
    try:
        from app.agents.orchestrator import get_agent_orchestrator
        orchestrator = get_agent_orchestrator()
        print("✓ Orchestrator导入成功")
    except Exception as e:
        print(f"✗ Orchestrator导入失败: {e}")
        return

    # 3. 检查generate_revision_diff方法签名
    print("\n[3/5] 检查generate_revision_diff方法...")
    try:
        import inspect
        sig = inspect.signature(orchestrator.generate_revision_diff)
        params = list(sig.parameters.keys())
        print(f"✓ 方法参数: {params}")

        # 检查是否包含user_id参数
        if 'user_id' in params:
            print("✓ user_id参数已添加")
        else:
            print("✗ user_id参数缺失！这是导致问题的关键原因")
    except Exception as e:
        print(f"✗ 检查失败: {e}")

    # 4. 检查API端点
    print("\n[4/5] 检查API端点...")
    try:
        from app.api.v1.endpoints.generate import router
        routes = [route.path for route in router.routes]

        revision_routes = [r for r in routes if 'revision' in r.lower()]
        print(f"✓ 找到修订相关路由: {revision_routes}")

        # 检查是否包含stream端点（可能有前缀）
        stream_endpoint = '/revision/{generation_id}/stream'
        if any(stream_endpoint in r for r in revision_routes):
            print("✓ 修订流式API端点存在")
        else:
            print("✗ 修订流式API端点不存在")
    except Exception as e:
        print(f"✗ 检查失败: {e}")

    # 5. 检查RevisionRequest schema
    print("\n[5/5] 检查RevisionRequest schema...")
    try:
        from app.schemas.generation import RevisionRequest
        fields = RevisionRequest.__fields__
        print(f"✓ RevisionRequest字段: {list(fields.keys())}")

        required_fields = ['generation_id', 'user_feedback', 'current_content',
                           'original_params', 'module', 'round_number']
        missing = [f for f in required_fields if f not in fields]
        if missing:
            print(f"✗ 缺少必需字段: {missing}")
        else:
            print("✓ 所有必需字段都存在")
    except Exception as e:
        print(f"✗ 检查失败: {e}")

    print("\n" + "=" * 60)
    print("诊断完成！")
    print("=" * 60)
    print("\n常见问题排查:")
    print("1. 如果后端无响应，检查LLM配置是否正确")
    print("2. 如果前端显示'正在生成修改指令...'，检查网络请求是否发送")
    print("3. 查看后端日志中是否有'Revision stream started'日志")
    print("4. 检查浏览器开发者工具Network标签中的请求状态")
    print("\n建议的测试步骤:")
    print("1. 启动后端服务: cd backend && python -m uvicorn app.main:app --reload")
    print("2. 启动前端服务: cd frontend && npm run dev")
    print("3. 打开浏览器开发者工具，查看Console和Network标签")
    print("4. 尝试提交修订，观察日志输出")


if __name__ == "__main__":
    asyncio.run(diagnostic_revision_api())
