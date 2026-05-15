"""
FastAPI 主应用
网络交换机配置收集 API
"""

from fastapi import FastAPI, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import sys

# 项目根目录和 backend 目录
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_BACKEND_DIR)
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
sys.path.insert(0, _BACKEND_DIR)

from services.collector_service import collect_device
from services.device_manager import DeviceManager
from utils.settings_loader import load_settings, load_devices
from utils.password import password_manager
from api import devices_router, collector_router, data_router, auth_router

app = FastAPI(
    title="网络交换机配置收集系统",
    description="通过 SSH 从 Cisco 和 Aruba 交换机收集配置文件",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化
device_manager = DeviceManager()
settings = load_settings()
data_root = settings.get("data_root", "./data")

# 挂载数据目录
if os.path.exists(data_root):
    app.mount("/data", StaticFiles(directory=data_root), name="data")

# 注册 API 路由
app.include_router(devices_router, prefix="/api/devices", tags=["devices"])
app.include_router(collector_router, prefix="/api/collect", tags=["collection"])
app.include_router(data_router, prefix="/api/data", tags=["data"])
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])

# ============ 健康检查 ============


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# ============ 前端静态文件（生产模式，必须放在所有路由之后）============
if os.path.exists(FRONTEND_DIST):
    # 静态资源（JS/CSS）
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    # SPA 回退：拦截非 API 路径的 404，返回 index.html
    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            path = request.url.path
            if not path.startswith("/api/") and not path.startswith("/data/"):
                index_path = os.path.join(FRONTEND_DIST, "index.html")
                if os.path.exists(index_path):
                    return FileResponse(index_path)
        return JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code)

    # 根路径直接返回 index.html
    @app.get("/")
    async def root():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
