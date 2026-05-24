"""
FastAPI 应用入口
"""
from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 加载 .env（本地开发用）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"), override=True, encoding="utf-8")
except ImportError:
    pass

from .api import finance_router, sentiment_router, watchlist_router, mouse_agent_router, macro_router
from .auth import router as auth_router
from .core import _ensure_stock_names_cache, cache_mgr
from . import db as watchlist_db

# 项目根目录 (backend/app/main.py -> backend/ -> 项目根目录)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 前端目录
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

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
app.include_router(watchlist_router)
app.include_router(mouse_agent_router)
app.include_router(macro_router)
app.include_router(auth_router)

# 静态文件目录
frontend_src = os.path.join(FRONTEND_DIR, "src")

# 挂载静态文件
if os.path.exists(frontend_src):
    app.mount("/src", StaticFiles(directory=frontend_src), name="frontend_src")

@app.on_event("startup")
def startup():
    """应用启动时的初始化"""
    _ensure_stock_names_cache()
    watchlist_db.init_db()
    cache_mgr.cleanup_cache()


@app.get("/")
def landing():
    """着陆页"""
    timeline_path = os.path.join(FRONTEND_DIR, "timeline.html")
    if os.path.exists(timeline_path):
        return FileResponse(timeline_path)
    return {"message": "Landing page not found"}


@app.get("/app")
def app_index():
    """平台主界面"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        return FileResponse(index_path, headers=headers)
    return {"message": "企业风控系统 API"}
