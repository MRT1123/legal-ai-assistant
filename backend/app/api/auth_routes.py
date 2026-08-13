"""
认证路由

提供用户注册、登录、验证码、忘记密码、重置密码 5 个 API 接口。
所有接口统一使用 /auth 前缀。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.database import get_db_instance
from app.services.auth_service import (
    hash_password, verify_password,
    create_access_token
)
from app.services.email_service import email_service

# 创建路由
router = APIRouter(prefix="/auth", tags=["认证"])


# ==================== 请求/响应模型 ====================

class SendCodeRequest(BaseModel):
    """发送验证码请求"""
    email: str                    # 接收验证码的邮箱
    purpose: str = "register"     # 用途：register（注册）或 reset（重置密码）


class RegisterRequest(BaseModel):
    """注册请求"""
    email: str        # 邮箱
    password: str     # 密码
    code: str         # 验证码


class LoginRequest(BaseModel):
    """登录请求"""
    email: str        # 邮箱
    password: str     # 密码


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求（发送重置验证码）"""
    email: str        # 注册邮箱


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    email: str        # 邮箱
    code: str         # 验证码
    new_password: str # 新密码


class TokenResponse(BaseModel):
    """登录成功返回的 Token"""
    access_token: str   # JWT Token
    token_type: str = "bearer"
    email: str          # 用户邮箱


# ==================== API 接口 ====================

@router.post("/send-code")
async def send_verification_code(request: SendCodeRequest):
    """
    发送验证码到邮箱
    
    流程：
    1. 验证邮箱格式
    2. 验证 purpose 参数合法
    3. 如果是注册，检查邮箱是否已存在
    4. 如果是重置密码，检查邮箱是否未注册
    5. 生成 6 位数字验证码
    6. 保存到数据库（有效期 5 分钟）
    7. 发送邮件（开发模式打印到控制台）
    """
    # 验证用途参数
    if request.purpose not in ("register", "reset"):
        raise HTTPException(status_code=400, detail="无效的验证码用途，仅支持 register 或 reset")
    
    db = get_db_instance()
    
    # 如果是注册，检查邮箱是否已存在
    if request.purpose == "register":
        existing_user = db.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="该邮箱已被注册")
    
    # 如果是重置密码，检查邮箱是否存在
    if request.purpose == "reset":
        existing_user = db.get_user_by_email(request.email)
        if not existing_user:
            raise HTTPException(status_code=400, detail="该邮箱未注册")
    
    # 生成验证码并保存
    code = email_service.generate_code()
    db.save_verification_code(request.email, code, request.purpose)
    
    # 发送邮件
    success = email_service.send_verification_code(request.email, code, request.purpose)
    
    if not success:
        raise HTTPException(status_code=500, detail="验证码发送失败，请稍后重试")
    
    return {"message": "验证码已发送，请查收邮箱", "email": request.email}


@router.post("/register")
async def register(request: RegisterRequest):
    """
    用户注册
    
    流程：
    1. 验证密码长度（至少 6 位）
    2. 验证验证码是否正确且未过期
    3. 对密码进行 bcrypt 加密
    4. 写入用户表
    5. 标记验证码已使用
    """
    # 验证密码长度
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于 6 位")
    
    db = get_db_instance()
    
    # 验证验证码
    stored_code = db.get_latest_code(request.email, "register")
    if not stored_code:
        raise HTTPException(status_code=400, detail="验证码无效或已过期，请重新获取")
    
    if stored_code["code"] != request.code:
        raise HTTPException(status_code=400, detail="验证码错误")
    
    # 加密密码并创建用户
    hashed_pw = hash_password(request.password)
    success = db.create_user(request.email, hashed_pw)
    
    if not success:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")
    
    # 标记验证码已使用
    db.mark_code_used(request.email, request.code, "register")
    
    return {"message": "注册成功", "email": request.email}


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    用户登录
    
    流程：
    1. 根据邮箱查找用户
    2. 验证密码是否匹配
    3. 生成 JWT Token 并返回
    """
    db = get_db_instance()
    
    # 查找用户
    user = db.get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    # 验证密码
    if not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    # 生成 Token
    token = create_access_token(user["id"], user["email"])
    
    return TokenResponse(
        access_token=token,
        email=user["email"]
    )


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    忘记密码 - 发送重置验证码
    
    流程：
    1. 检查邮箱是否已注册
    2. 生成重置验证码
    3. 发送到邮箱
    """
    db = get_db_instance()
    
    # 检查邮箱是否已注册
    user = db.get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=400, detail="该邮箱未注册")
    
    # 生成验证码并发送
    code = email_service.generate_code()
    db.save_verification_code(request.email, code, "reset")
    
    success = email_service.send_verification_code(request.email, code, "reset")
    
    if not success:
        raise HTTPException(status_code=500, detail="验证码发送失败，请稍后重试")
    
    return {"message": "重置验证码已发送，请查收邮箱", "email": request.email}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """
    重置密码
    
    流程：
    1. 验证密码长度（至少 6 位）
    2. 验证验证码是否正确且未过期
    3. 更新密码为新的加密密码
    4. 标记验证码已使用
    """
    # 验证密码长度
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于 6 位")
    
    db = get_db_instance()
    
    # 验证验证码
    stored_code = db.get_latest_code(request.email, "reset")
    if not stored_code:
        raise HTTPException(status_code=400, detail="验证码无效或已过期，请重新获取")
    
    if stored_code["code"] != request.code:
        raise HTTPException(status_code=400, detail="验证码错误")
    
    # 更新密码
    new_hashed_pw = hash_password(request.new_password)
    success = db.update_user_password(request.email, new_hashed_pw)
    
    if not success:
        raise HTTPException(status_code=400, detail="密码重置失败，用户不存在")
    
    # 标记验证码已使用
    db.mark_code_used(request.email, request.code, "reset")
    
    return {"message": "密码重置成功，请使用新密码登录"}
