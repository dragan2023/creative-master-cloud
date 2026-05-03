#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速验证SECRET_KEY配置（无需依赖）
"""

import os
from pathlib import Path
from dotenv import load_dotenv

def main():
    print("=" * 60)
    print("SECRET_KEY 快速验证")
    print("=" * 60)
    
    # 加载.env文件
    backend_dir = Path(__file__).parent.parent  # scripts的父目录是backend
    env_path = backend_dir / ".env"
    
    if not env_path.exists():
        print(f"❌ 错误: 未找到.env文件: {env_path}")
        return 1
    
    load_dotenv(env_path)
    print(f"✅ 已加载: {env_path}\n")
    
    # 获取SECRET_KEY
    secret_key = os.getenv("SECRET_KEY")
    
    if not secret_key:
        print("❌ 错误: SECRET_KEY未设置")
        return 1
    
    # 检查1: 是否默认值
    if secret_key == "auto-generated-please-change":
        print("❌ 失败: SECRET_KEY仍是默认值！")
        print("   请立即更换")
        return 1
    else:
        print("✅ 通过: SECRET_KEY已更换")
    
    # 检查2: 长度
    key_length = len(secret_key)
    if key_length < 32:
        print(f"❌ 失败: SECRET_KEY长度({key_length})不足32字符")
        return 1
    else:
        print(f"✅ 通过: SECRET_KEY长度({key_length}字符)")
    
    # 检查3: 复杂度
    has_upper = any(c.isupper() for c in secret_key)
    has_lower = any(c.islower() for c in secret_key)
    has_digit = any(c.isdigit() for c in secret_key)
    
    complexity_score = sum([has_upper, has_lower, has_digit])
    
    if complexity_score == 3:
        print("✅ 通过: 包含大小写字母和数字")
    elif complexity_score >= 2:
        print("⚠️  警告: 复杂度一般（建议包含大小写字母+数字）")
    else:
        print("❌ 警告: 复杂度过低")
    
    # 显示密钥（脱敏）
    print(f"\n📝 密钥信息:")
    print(f"   前10字符: {secret_key[:10]}...")
    print(f"   后10字符: ...{secret_key[-10:]}")
    print(f"   总长度: {key_length}字符")
    print(f"   熵值估算: {key_length * 6} bits")
    
    print("\n" + "=" * 60)
    print("✅ SECRET_KEY配置验证通过！")
    print("=" * 60)
    
    print("\n下一步操作:")
    print("1. 重启后端服务:")
    print("   cd backend")
    print("   python -m uvicorn app.main:app --reload")
    print()
    print("2. 清除浏览器缓存:")
    print("   - F12 → Application → Local Storage → Clear")
    print("   - 或 Ctrl+Shift+R 强制刷新")
    print()
    print("3. 重新登录系统")
    print()
    print("4. 重新配置API Key（旧加密数据已失效）")
    
    print("\n⚠️  重要提醒:")
    print("   - 所有现有用户需要重新登录")
    print("   - 所有已配置的API Key需要重新添加")
    print("   - 建议在用户低峰期执行（凌晨2-4点）")
    
    return 0

if __name__ == "__main__":
    exit(main())
