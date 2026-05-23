"""
FastAPI 应用入口
"""
from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .api import finance_router, sentiment_router
from .core import _ensure_stock_names_cache

# 项目根目录 (backend/app/main.py -> backend/ -> 项目根目录)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 前端目录
FRONTEND_DIR = BASE_DIR

# 创建 FastAPI 应用
app = FastAPI(
    title="企业风控系统",
    description="财报风险挖掘 · 舆论风险监控 · 宏观事件追踪",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(finance_router)
app.include_router(sentiment_router)

# 静态文件目录
css_dir = os.path.join(BASE_DIR, "css")
frontend_src = os.path.join(BASE_DIR, "frontend", "src")

# 挂载静态文件
if os.path.exists(css_dir):
    app.mount("/css", StaticFiles(directory=css_dir), name="css")
if os.path.exists(frontend_src):
    app.mount("/src", StaticFiles(directory=frontend_src), name="frontend_src")


@app.on_event("startup")
def startup():
    """应用启动时的初始化"""
    _ensure_stock_names_cache()


@app.get("/")
def index():
    """首页"""
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "企业风控系统 API"}
