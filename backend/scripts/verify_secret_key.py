#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证SECRET_KEY更换是否成功

此脚本检查:
1. SECRET_KEY是否已更换（不是默认值）
2. SECRET_KEY长度是否足够（>=32字符）
3. 能否正常生成JWT令牌
4. 能否正常验证JWT令牌
"""

import os
import sys
from pathlib import Path

# 添加项目路径
backend_dir = Path(__file__).parent.parent  # 修改为backend根目录
sys.path.insert(0, str(backend_dir))

def check_secret_key():
    """检查SECRET_KEY配置"""
    from app.core.config import get_settings
    
    settings = get_settings()
    
    print("=" * 60)
    print("SECRET_KEY 验证报告")
    print("=" * 60)
    
    # 检查1: 是否已更换
    if settings.SECRET_KEY == "auto-generated-please-change":
        print("❌ 失败: SECRET_KEY仍是默认值！")
        print("   请立即更换: openssl rand -hex 32")
        return False
    else:
        print("✅ 通过: SECRET_KEY已更换")
    
    # 检查2: 长度是否足够
    key_length = len(settings.SECRET_KEY)
    if key_length < 32:
        print(f"❌ 失败: SECRET_KEY长度({key_length})不足32字符")
        return False
    else:
        print(f"✅ 通过: SECRET_KEY长度({key_length}字符)足够")
    
    # 检查3: 复杂度
    has_upper = any(c.isupper() for c in settings.SECRET_KEY)
    has_lower = any(c.islower() for c in settings.SECRET_KEY)
    has_digit = any(c.isdigit() for c in settings.SECRET_KEY)
    
    if has_upper and has_lower and has_digit:
        print("✅ 通过: SECRET_KEY包含大小写字母和数字")
    else:
        print("⚠️  警告: SECRET_KEY复杂度不够（建议包含大小写字母+数字）")
    
    return True


def check_jwt_token():
    """检查JWT令牌生成和验证"""
    from app.core.security import create_access_token, decode_access_token
    
    print("\n" + "=" * 60)
    print("JWT 令牌测试")
    print("=" * 60)
    
    try:
        # 生成令牌
        test_user_id = 999999  # 使用不存在的ID测试
        token = create_access_token(subject=test_user_id)
        
        if not token:
            print("❌ 失败: 无法生成JWT令牌")
            return False
        
        print(f"✅ 通过: JWT令牌生成成功")
        print(f"   令牌前50字符: {token[:50]}...")
        
        # 验证令牌
        payload = decode_access_token(token)
        
        if not payload:
            print("❌ 失败: JWT令牌验证失败")
            return False
        
        if payload.get("sub") != str(test_user_id):
            print(f"❌ 失败: 令牌用户ID不匹配 (期望:{test_user_id}, 实际:{payload.get('sub')})")
            return False
        
        print(f"✅ 通过: JWT令牌验证成功")
        print(f"   用户ID: {payload.get('sub')}")
        print(f"   过期时间: {payload.get('exp')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 失败: JWT测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_api_key_encryption():
    """检查API Key加密功能"""
    from app.core.security import api_key_encryption
    
    print("\n" + "=" * 60)
    print("API Key 加密测试")
    print("=" * 60)
    
    try:
        # 测试加密
        test_key = "sk-test-api-key-12345"
        encrypted = api_key_encryption.encrypt(test_key)
        
        if not encrypted:
            print("❌ 失败: API Key加密失败")
            return False
        
        print(f"✅ 通过: API Key加密成功")
        print(f"   原始密钥: {test_key}")
        print(f"   加密后(前50字符): {encrypted[:50]}...")
        
        # 测试解密
        decrypted = api_key_encryption.decrypt(encrypted)
        
        if decrypted != test_key:
            print(f"❌ 失败: API Key解密不匹配 (期望:{test_key}, 实际:{decrypted})")
            return False
        
        print(f"✅ 通过: API Key解密成功")
        print(f"   解密后: {decrypted}")
        
        return True
        
    except Exception as e:
        print(f"❌ 失败: API Key加密测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_database_connectivity():
    """检查数据库连接"""
    print("\n" + "=" * 60)
    print("数据库连接测试")
    print("=" * 60)
    
    try:
        import asyncio
        from app.core.database import async_session_maker
        from sqlalchemy import text
        
        async def test_db():
            async with async_session_maker() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar()
        
        result = asyncio.run(test_db())
        
        if result == 1:
            print("✅ 通过: 数据库连接正常")
            return True
        else:
            print("❌ 失败: 数据库连接异常")
            return False
            
    except Exception as e:
        print(f"❌ 失败: 数据库连接测试异常: {e}")
        return False


def main():
    """主函数"""
    print("\n🔍 开始验证SECRET_KEY更换...\n")
    
    # 加载环境变量
    from dotenv import load_dotenv
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ 已加载环境变量: {env_path}")
    else:
        print(f"⚠️  警告: 未找到.env文件: {env_path}")
    
    results = []
    
    # 执行检查
    results.append(("SECRET_KEY配置", check_secret_key()))
    results.append(("JWT令牌功能", check_jwt_token()))
    results.append(("API Key加密", check_api_key_encryption()))
    results.append(("数据库连接", check_database_connectivity()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有检查通过！SECRET_KEY更换成功！")
        print("\n下一步:")
        print("1. 重启后端服务: python -m uvicorn app.main:app --reload")
        print("2. 清除浏览器缓存和localStorage")
        print("3. 重新登录系统")
        print("4. 重新配置API Key")
    else:
        print("⚠️  部分检查未通过，请查看上面的详细信息")
        print("\n建议:")
        print("1. 检查.env文件是否正确修改")
        print("2. 确认SECRET_KEY长度>=32字符")
        print("3. 重新启动后端服务")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
