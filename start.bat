@echo off
chcp 65001 >nul
title NDM - Network Device Manager

cd /d %~dp0

echo ========================================
echo   NDM - Network Device Manager
echo ========================================
echo.

REM Check Node.js
where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm not found. Please install Node.js 18+ and retry.
    pause
    exit /b 1
)

REM Activate virtual environment if present
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [0/2] Virtual environment activated
)

REM Check if frontend is already built
if not exist "frontend\dist\index.html" (
    if not exist "frontend" (
        echo [ERROR] frontend directory not found. Please verify the deployment package.
        pause
        exit /b 1
    )
    echo [1/2] Building frontend...

    REM Install frontend dependencies if missing
    if not exist "frontend\node_modules" (
        echo   Installing frontend dependencies...
        pushd frontend
        call npm install
        if %ERRORLEVEL% neq 0 (
            echo [ERROR] Frontend dependency install failed. Check Node.js version and network.
            popd
            pause
            exit /b 1
        )
        popd
    )

    pushd frontend
    call npm run build
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Frontend build failed. Check error messages above.
        popd
        pause
        exit /b 1
    )
    popd

    if not exist "frontend\dist\index.html" (
        echo [ERROR] Build completed but dist/index.html not generated. Check build output.
        pause
        exit /b 1
    )
    echo   Frontend build successful
) else (
    echo [1/2] Frontend already built, skipping
)

echo [2/2] Starting backend service...
echo.
echo   URL: http://localhost:8002
echo   Press Ctrl+C to stop
echo.

python backend\main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Backend failed to start. Please run: pip install -r backend/requirements.txt
    pause
    exit /b 1
)

pause
