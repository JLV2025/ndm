@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title NDM - Network Device Manager

cd /d %~dp0

set "PORT=8002"
set "TMPFILE=%TEMP%\ndm_portcheck.txt"

echo ========================================
echo   NDM - Network Device Manager v2.7.13
echo   SQLite + AI Log Analysis
echo ========================================
echo(

REM ============================================================
REM 1. Port conflict detection (prevents duplicate startup)
REM ============================================================
call :CHECK_PORT
if defined OCCUPIED_PID (
    set "MSG=[WARN] Port %PORT% already in use (PID: !OCCUPIED_PID!)."
    echo(!MSG!
    echo(       NDM may already be running in another window.
    echo(
    choice /C YN /M "Kill occupying process and restart"
    if errorlevel 2 (
        echo Aborted.
        pause
        exit /b 1
    )
    taskkill /PID !OCCUPIED_PID! /F >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo([FAIL] Cannot kill PID !OCCUPIED_PID!. Run as Administrator.
        pause
        exit /b 1
    )
    echo([OK] Process killed. Waiting for port release...
    timeout /t 2 /nobreak >nul

    call :CHECK_PORT
    if defined OCCUPIED_PID (
        echo([FAIL] Port %PORT% still occupied by PID !OCCUPIED_PID!.
        pause
        exit /b 1
    )
)

REM ============================================================
REM 2. Environment checks
REM ============================================================
where python >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo([ERROR] Python not found. Install Python 3.10+ and retry.
    pause
    exit /b 1
)

where npm >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo([ERROR] npm not found. Install Node.js 18+ and retry.
    pause
    exit /b 1
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo([0/2] Virtual environment activated
)

REM ============================================================
REM 3. Frontend build
REM ============================================================
if not exist "frontend" (
    echo([ERROR] frontend/ directory missing.
    pause
    exit /b 1
)
echo([1/2] Building frontend...

if not exist "frontend\node_modules" (
    echo(  Installing frontend dependencies...
    pushd frontend
    call npm install
    if !ERRORLEVEL! neq 0 (
        echo([ERROR] npm install failed.
        popd
        pause
        exit /b 1
    )
    popd
)

pushd frontend
call npm run build
if !ERRORLEVEL! neq 0 (
    echo([ERROR] Build failed.
    popd
    pause
    exit /b 1
)
popd

if not exist "frontend\dist\index.html" (
    echo([ERROR] dist/index.html not generated after build.
    pause
    exit /b 1
)
echo(  Build OK

REM ============================================================
REM 4. Start backend
REM ============================================================
echo([2/2] Starting backend on port %PORT%...
echo(
echo ========================================
echo   Frontend : http://localhost:%PORT%
echo   API Docs : http://localhost:%PORT%/docs
echo   Health   : http://localhost:%PORT%/health
echo ========================================
echo   Press Ctrl+C to stop
echo ========================================
echo(

python backend\main.py

echo(
echo([OK] NDM server stopped.
pause
exit /b 0

REM ============================================================
REM Subroutine: check if PORT is listening, set OCCUPIED_PID
REM ============================================================
:CHECK_PORT
set "OCCUPIED_PID="
netstat -ano 2>nul | findstr /C:":%PORT%" | findstr /C:"LISTENING" > "%TMPFILE%"
for /f "usebackq tokens=5" %%a in ("%TMPFILE%") do (
    set "OCCUPIED_PID=%%a"
    goto :EOF
)
goto :EOF
