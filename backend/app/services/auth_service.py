"""
认证服务

负责：
- 密码加密与验证（bcrypt）
- JWT Token 生成与解析
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from passlib.context import CryptContext
from jose import jwt, JWTError

# ==================== 配置 ====================

# JWT 密钥（生产环境应使用环境变量，不要硬编码在代码里）
import os
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "legal-assistant-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # Token 有效期 24 小时

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==================== 密码处理 ====================

def hash_password(password: str) -> str:
    """
    对明文密码进行哈希加密
    
    参数：
        password - 用户输入的明文密码
    
    返回：加密后的密码字符串
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否与加密密码匹配
    
    参数：
        plain_password  - 用户输入的明文密码
        hashed_password - 数据库中存储的加密密码
    
    返回：匹配返回 True，不匹配返回 False
    """
    return pwd_context.verify(plain_password, hashed_password)


# ==================== JWT Token ====================

def create_access_token(user_id: int, email: str) -> str:
    """
    生成 JWT Access Token
    
    参数：
        user_id - 用户 ID
        email   - 用户邮箱
    
    返回：JWT token 字符串
    """
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user_id),        # 主题：用户 ID
        "email": email,             # 邮箱
        "exp": expire,              # 过期时间
        "iat": datetime.utcnow()    # 签发时间
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[Dict]:
    """
    解析 JWT Token
    
    参数：
        token - JWT token 字符串
    
    返回：解析成功返回 payload 字典，失败或过期返回 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user_from_token(token: str) -> Optional[Dict]:
    """
    从 Token 中提取当前用户信息
    
    参数：
        token - JWT token 字符串
    
    返回：{"user_id": int, "email": str}，失败返回 None
    """
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    email = payload.get("email")
    
    if not user_id or not email:
        return None
    
    return {
        "user_id": int(user_id),
        "email": email
    }
