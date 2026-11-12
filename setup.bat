@echo off
setlocal EnableDelayedExpansion
rem ============================================================
rem  Quickyee - one-time setup (Windows)
rem  Creates .venv (Python 3.13+), installs requirements and
rem  prepares .env, storage and logs. Database tables and the
rem  Super Admin are created automatically on the first start.
rem ============================================================

cd /d "%~dp0"

echo ===========================================
echo   Quickyee Project Setup
echo ===========================================

echo.
echo 1. Finding Python 3.13+ ...
set "PY="
for %%V in (3.15 3.14 3.13) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python 3.13 or newer was not found. Install it from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Using: !PY!

echo.
echo 2. Creating Virtual Environment (if not exists)...
if not exist ".venv\Scripts\python.exe" (
    !PY! -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create .venv
        pause
        exit /b 1
    )
    echo Virtual Environment created.
) else (
    echo Virtual Environment already exists.
)

echo.
echo 3. Installing Dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Installing requirements failed.
    pause
    exit /b 1
)

echo.
echo 4. Preparing .env, storage and logs...
".venv\Scripts\python.exe" scripts\init_env.py
if not exist "storage\database" mkdir "storage\database"
if not exist "storage\media" mkdir "storage\media"
if not exist "logs" mkdir "logs"

echo.
echo 5. Checking the application loads...
".venv\Scripts\python.exe" -c "import app.main" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] The app did not load. Check .env ^(SECRET_KEY 32+ chars, ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD^).
) else (
    echo Application loads correctly.
)

echo.
echo ===========================================
echo   Setup Complete!
echo   Start the server with: run.bat
echo   ^(database + Super Admin are created on the first start^)
echo ===========================================
pause
endlocal
