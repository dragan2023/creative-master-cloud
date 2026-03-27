#!/usr/bin/env python
"""创建默认管理员用户"""
import asyncio
from passlib.context import CryptContext
from sqlalchemy import text
from app.core.database import engine

async def main():
    pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
    hashed = pwd_context.hash('admin123')
    print(f"Generated hash: {hashed}")
    
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET hashed_password = :h WHERE username = 'admin'"),
            {"h": hashed}
        )
        result = await conn.execute(
            text("SELECT username, hashed_password FROM users WHERE username = 'admin'")
        )
        row = result.fetchone()
        print(f"Updated: {row}")

if __name__ == "__main__":
    asyncio.run(main())
