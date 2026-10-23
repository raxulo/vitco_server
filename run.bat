@echo off
setlocal
rem ============================================================
rem  Quickyee - start the server (Windows, development)
rem  HOST / PORT come from .env (defaults 0.0.0.0 : 8600).
rem  Code changes reload automatically; Ctrl+C stops the server.
rem ============================================================

cd /d "%~dp0"

echo ===========================================
echo   Starting Quickyee Server
echo ===========================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Run setup.bat first.
    pause
    exit /b 1
)
if not exist ".env" (
    echo [ERROR] .env not found. Run setup.bat first.
    pause
    exit /b 1
)

set "HOST=0.0.0.0"
set "PORT=8600"
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="HOST" set "HOST=%%B"
    if /i "%%A"=="PORT" set "PORT=%%B"
)

echo Server: http://%HOST%:%PORT%   (Ctrl+C to stop)
".venv\Scripts\python.exe" -m uvicorn app.main:app --host %HOST% --port %PORT% --reload

echo.
echo Server stopped.
pause
endlocal
