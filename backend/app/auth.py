"""
用户认证模块 — 注册 / 登录 / JWT 中间件
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from jose import jwt, JWTError

from . import db

# JWT 配置
SECRET_KEY = os.getenv("JWT_SECRET", "fengkong-jwt-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


# ── 密码工具（用 hashlib 替代 passlib/bcrypt，避免兼容问题）──

def hash_password(password: str) -> str:
    """返回 salt$hash 格式"""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception:
        return False
ACCESS_TOKEN_EXPIRE_DAYS = 30

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── 请求/响应模型 ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    username: str
    user_id: int


# ── 工具函数 ─────────────────────────────────────────────────────

def create_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(authorization: str = Header(None)) -> dict:
    """从 Authorization header 解析当前用户，供依赖注入使用"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("无效的认证方案")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.get_user_by_id(payload["user_id"])
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    except (ValueError, JWTError):
        raise HTTPException(status_code=401, detail="无效的认证令牌")


# ── 可选认证（未登录也能访问，但 user 为 None）───────────────────

def get_optional_user(authorization: str = Header(None)):
    """不强制登录，有 token 就解析，没有就返回 None"""
    if not authorization:
        return None
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return db.get_user_by_id(payload["user_id"])
    except Exception:
        return None


# ── API 接口 ─────────────────────────────────────────────────────

@router.post("/register")
def register(req: RegisterRequest):
    if len(req.username) < 2 or len(req.password) < 4:
        raise HTTPException(status_code=400, detail="用户名至少2位，密码至少4位")
    password_hash = hash_password(req.password)
    result = db.create_user(req.username, password_hash)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["msg"])
    token = create_token(result["user_id"], req.username)
    return TokenResponse(token=token, username=req.username, user_id=result["user_id"])


@router.post("/login")
def login(req: LoginRequest):
    user = db.get_user_by_username(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user["id"], user["username"])
    return TokenResponse(token=token, username=user["username"], user_id=user["id"])


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"user_id": user["id"], "username": user["username"], "created_at": user["created_at"]}
