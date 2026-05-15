@echo off
chcp 65001 >nul
title NDM 网络设备配置管理系统

cd /d %~dp0

echo ========================================
echo   NDM - 网络设备配置管理系统
echo ========================================
echo.

REM 检查前端是否已构建
if not exist "frontend\dist\index.html" (
    echo [1/2] 正在构建前端...
    cd frontend
    call npm run build
    cd ..
) else (
    echo [1/2] 前端已构建，跳过
)

echo [2/2] 启动后端服务...
echo.
echo   访问地址: http://localhost:8002
echo   按 Ctrl+C 停止服务
echo.

python backend\main.py

pause
