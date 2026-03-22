#!/usr/bin/env python
"""
超级管理员初始化脚本

用于创建超级管理员账号，支持命令行参数和交互式输入。

使用方法:
    # 交互式创建
    python scripts/init_super_admin.py
    
    # 命令行参数创建
    python scripts/init_super_admin.py --username admin --password yourpassword --email admin@example.com
    
    # 使用环境变量
    export ADMIN_USERNAME=admin
    export ADMIN_PASSWORD=yourpassword
    export ADMIN_EMAIL=admin@example.com
    python scripts/init_super_admin.py
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.models import User, UserRole


async def create_super_admin(username: str, password: str, email: str) -> dict:
    """
    创建超级管理员账号
    
    Args:
        username: 用户名
        password: 密码
        email: 邮箱
    
    Returns:
        创建结果
    """
    async with async_session_maker() as db:
        # 检查用户名是否已存在
        result = await db.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            if existing_user.role == UserRole.SUPER_ADMIN:
                return {
                    "success": False,
                    "message": f"超级管理员 '{username}' 已存在",
                    "user_id": existing_user.id
                }
            else:
                # 升级为超级管理员
                existing_user.role = UserRole.SUPER_ADMIN
                existing_user.is_active = True
                await db.commit()
                return {
                    "success": True,
                    "message": f"用户 '{username}' 已升级为超级管理员",
                    "user_id": existing_user.id
                }
        
        # 检查邮箱是否已存在
        result = await db.execute(
            select(User).where(User.email == email)
        )
        if result.scalar_one_or_none():
            return {
                "success": False,
                "message": f"邮箱 '{email}' 已被使用"
            }
        
        # 创建新的超级管理员
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
            tenant_id=None  # 超级管理员不属于任何租户
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return {
            "success": True,
            "message": f"超级管理员 '{username}' 创建成功",
            "user_id": user.id
        }


def main():
    parser = argparse.ArgumentParser(description="创建超级管理员账号")
    parser.add_argument("--username", help="管理员用户名")
    parser.add_argument("--password", help="管理员密码")
    parser.add_argument("--email", help="管理员邮箱")
    args = parser.parse_args()
    
    # 从参数或环境变量获取
    username = args.username or os.environ.get("ADMIN_USERNAME")
    password = args.password or os.environ.get("ADMIN_PASSWORD")
    email = args.email or os.environ.get("ADMIN_EMAIL")
    
    # 交互式输入
    if not username:
        username = input("请输入管理员用户名 [admin]: ").strip() or "admin"
    
    if not password:
        import getpass
        password = getpass.getpass("请输入管理员密码: ").strip()
        if not password:
            print("错误: 密码不能为空")
            sys.exit(1)
        confirm = getpass.getpass("请确认密码: ").strip()
        if password != confirm:
            print("错误: 两次密码输入不一致")
            sys.exit(1)
    
    if not email:
        email = input("请输入管理员邮箱 [admin@localhost]: ").strip() or "admin@localhost"
    
    print(f"\n正在创建超级管理员...")
    print(f"  用户名: {username}")
    print(f"  邮箱: {email}")
    
    # 执行创建
    result = asyncio.run(create_super_admin(username, password, email))
    
    print(f"\n{'='*50}")
    if result["success"]:
        print(f"✓ {result['message']}")
        print(f"  用户ID: {result['user_id']}")
    else:
        print(f"✗ {result['message']}")
    print(f"{'='*50}")
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
