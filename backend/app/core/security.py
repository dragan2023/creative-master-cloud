"""
安全模块
提供密码加密、JWT Token 生成与验证、API Key 加密等功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
import secrets
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import get_settings


# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[dict] = None
) -> str:
    """
    创建 JWT Token
    
    Args:
        subject: Token 主题（通常是用户ID）
        expires_delta: 过期时间增量
        extra_data: 额外的载荷数据
    
    Returns:
        JWT Token 字符串
    """
    settings = get_settings()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    if extra_data:
        to_encode.update(extra_data)
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码并验证 JWT Token
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        解码后的载荷数据，验证失败返回 None
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def generate_api_key() -> str:
    """
    生成随机 API Key
    
    Returns:
        32字节随机字符串
    """
    return secrets.token_urlsafe(32)


class APIKeyEncryption:
    """
    API Key 加密类
    使用 Fernet 对称加密保护用户存储的 API Key
    """
    
    def __init__(self):
        self._fernet: Optional[Fernet] = None
    
    def _get_fernet(self) -> Fernet:
        """获取 Fernet 实例（延迟初始化）"""
        if self._fernet is None:
            settings = get_settings()
            # 使用 SECRET_KEY 派生加密密钥
            salt = b'creative_master_salt_v1'  # 固定盐值（生产环境应从安全配置读取）
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
            self._fernet = Fernet(key)
        return self._fernet
    
    def encrypt(self, api_key: str) -> str:
        """
        加密 API Key
        
        Args:
            api_key: 原始 API Key
        
        Returns:
            加密后的字符串
        """
        fernet = self._get_fernet()
        encrypted = fernet.encrypt(api_key.encode())
        return encrypted.decode()
    
    def decrypt(self, encrypted_key: str) -> str:
        """
        解密 API Key
        
        Args:
            encrypted_key: 加密的 API Key
        
        Returns:
            原始 API Key
        """
        fernet = self._get_fernet()
        decrypted = fernet.decrypt(encrypted_key.encode())
        return decrypted.decode()


# 全局 API Key 加密实例
api_key_encryption = APIKeyEncryption()


def mask_api_key(api_key: str) -> str:
    """
    遮蔽 API Key 显示
    
    Args:
        api_key: 原始 API Key
    
    Returns:
        遮蔽后的 API Key（如 sk-***abc）
    """
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}***{api_key[-4:]}"
