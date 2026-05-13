"""
FastAPI 主应用
网络交换机配置收集 API
"""

from fastapi import FastAPI, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
