@echo off
chcp 65001 >nul
title NDM 网络设备配置管理系统

cd /d %~dp0

echo ========================================
echo   NDM - 网络设备配置管理系统
echo ========================================
echo.

REM 检查 Node.js
where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 npm。请安装 Node.js 18+ 后重试。
    pause
    exit /b 1
)

REM 尝试激活虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [0/2] 已激活虚拟环境
)

REM 检查前端是否已构建
if not exist "frontend\dist\index.html" (
    echo [1/2] 正在构建前端...

    REM 检查前端依赖是否安装
    if not exist "frontend\node_modules" (
        echo   正在安装前端依赖...
        cd frontend
        call npm install
        if %ERRORLEVEL% neq 0 (
            echo [错误] 前端依赖安装失败。请检查 Node.js 版本和网络连接。
            cd ..
            pause
            exit /b 1
        )
        cd ..
    )

    cd frontend
    call npm run build
    if %ERRORLEVEL% neq 0 (
        echo [错误] 前端构建失败。请检查上方错误信息。
        cd ..
        pause
        exit /b 1
    )
    cd ..

    if not exist "frontend\dist\index.html" (
        echo [错误] 前端构建完成但未生成 dist/index.html，请检查构建输出。
        pause
        exit /b 1
    )
    echo   前端构建成功
) else (
    echo [1/2] 前端已构建，跳过
)

echo [2/2] 启动后端服务...
echo.
echo   访问地址: http://localhost:8002
echo   按 Ctrl+C 停止服务
echo.

python backend\main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [错误] 后端启动失败。请确认已运行 pip install -r backend/requirements.txt
    pause
    exit /b 1
)

pause
