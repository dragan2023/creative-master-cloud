#!/usr/bin/env python
"""
更新管理员密码脚本

使用方法:
    python scripts/update_admin_password.py --username admin --password newpassword
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
from app.models import User


async def update_password(username: str, new_password: str) -> dict:
    """
    更新用户密码
    
    Args:
        username: 用户名
        new_password: 新密码
    
    Returns:
        更新结果
    """
    async with async_session_maker() as db:
        # 查找用户
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                "success": False,
                "message": f"用户 '{username}' 不存在"
            }
        
        # 更新密码
        user.hashed_password = get_password_hash(new_password)
        await db.commit()
        
        return {
            "success": True,
            "message": f"用户 '{username}' 密码更新成功",
            "user_id": user.id
        }


def main():
    parser = argparse.ArgumentParser(description="更新管理员密码")
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument("--password", required=True, help="新密码")
    args = parser.parse_args()
    
    print(f"\n正在更新密码...")
    print(f"  用户名: {args.username}")
    
    # 执行更新
    result = asyncio.run(update_password(args.username, args.password))
    
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
