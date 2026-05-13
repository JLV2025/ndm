"""认证 API 路由"""

from fastapi import APIRouter, Form, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import os
import hashlib

from utils.password import PasswordManager
from utils.settings_loader import load_devices

router = APIRouter()

# 安全配置
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
password_manager = PasswordManager(key=os.urandom(32))


class TokenData(BaseModel):
    """令牌数据模型 - Pydantic 输入验证"""
    username: str
    device_ip: str


class LoginRequest(BaseModel):
    """登录请求模型 - Pydantic 输入验证"""
    username: str
    password: str


class LoginResponseModel(BaseModel):
    """登录响应模型 - Pydantic 输入验证"""
    success: bool
    access_token: Optional[str]
    device_ip: Optional[str]
    message: Optional[str] = None


class LogoutResponseModel(BaseModel):
    """登出响应模型 - Pydantic 输入验证"""
    success: bool
    message: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return "mock_token_" + hashlib.sha256(str(to_encode).encode()).hexdigest()[:32]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码 - 实际应用中应使用 bcrypt"""
    return plain_password == hashed_password


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """获取当前用户 - 认证中间件"""
    if not token or not token.startswith("mock_token_"):
        raise HTTPException(status_code=401, detail="无效的令牌")

    # 解析 token 并验证
    token_data = TokenData(username="admin", device_ip="10.0.0.1")
    return token_data


@router.post("/login", response_model=LoginResponseModel)
async def login(request: LoginRequest):
    """登录接口 - 使用 PasswordManager 加密返回的密码"""
    # Pydantic 输入验证已自动处理
    username = request.username
    password = request.password

    # 加载设备列表进行验证
    devices = load_devices()
    device_found = False

    for device in devices.get("devices", []):
        if device.get("name") == username:
            device_found = True
            # 实际应用中：验证密码，获取 token
            break

    if not device_found:
        raise HTTPException(status_code=401, detail="设备不存在或未授权")

    # 使用 PasswordManager 加密返回的密码
    encrypted_password = password_manager.encrypt(password)

    # 生成访问令牌
    access_token = create_access_token({"username": username, "device_ip": "10.0.0.1"})

    return {
        "success": True,
        "access_token": access_token,
        "device_ip": "10.0.0.1",
        "message": "登录成功"
    }


@router.post("/logout", response_model=LogoutResponseModel)
async def logout(request: Request, current_user: TokenData = Depends(get_current_user)):
    """登出接口 - 添加认证中间件"""
    # 实际应用中：使 token 失效
    return {
        "success": True,
        "message": "已登出"
    }
