@echo off
setlocal enabledelayedexpansion

REM ==============================================================
REM Quickyee - One-Click Deploy Script (Windows to Server)
REM ==============================================================

set SERVER_IP=66.116.235.21
set SERVER_USER=root
set REMOTE_GIT=/root/quickyee.git
set REMOTE_DIR=/root/quickyee

echo ==============================================================
echo       Quickyee Deployment to Server (%SERVER_IP%)
echo ==============================================================
echo.
echo [1] Git Push (Recommended - auto updates /root/quickyee and restarts)
echo [2] Direct SCP File Sync (Upload files without git)
echo.
set /p CHOICE="Choose method [1 or 2, default 1]: "
if "%CHOICE%"=="" set CHOICE=1

if "%CHOICE%"=="1" goto GIT_DEPLOY
if "%CHOICE%"=="2" goto SCP_DEPLOY
goto GIT_DEPLOY

:GIT_DEPLOY
echo.
echo Checking Git remote 'live'...
git remote get-url live >nul 2>&1
if errorlevel 1 (
    echo Adding remote 'live' -> %SERVER_USER%@%SERVER_IP%:%REMOTE_GIT%
    git remote add live %SERVER_USER%@%SERVER_IP%:%REMOTE_GIT%
)

set /p MSG="Enter commit message (press Enter for 'update'): "
if "%MSG%"=="" set MSG=update

echo Staging changes...
git add .
git commit -m "%MSG%" 2>nul

echo Pushing code to server directly into %REMOTE_DIR%...
git push live HEAD:main
if errorlevel 1 (
    echo [ERROR] Git push failed. Please check your SSH connection or credentials.
    pause
    exit /b 1
)
echo.
echo ==============================================================
echo [SUCCESS] Code deployed directly to %REMOTE_DIR% and server restarted!
echo ==============================================================
pause
exit /b 0

:SCP_DEPLOY
echo.
echo Uploading project files directly to %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%...
scp -r app scripts *.py *.sh requirements.txt .env %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
echo Restarting server...
ssh %SERVER_USER%@%SERVER_IP% "cd %REMOTE_DIR% && ./run_on_background.sh restart"
echo.
echo ==============================================================
echo [SUCCESS] Direct file upload completed and server restarted!
echo ==============================================================
pause
exit /b 0
