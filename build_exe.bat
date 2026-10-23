@echo off
setlocal enabledelayedexpansion
rem ============================================================
rem  Quickyee - build the single-file executable (Windows)
rem  Produces: dist\quickyee.exe   (one file, no .py inside)
rem
rem  On start it asks what to ship alongside the binary:
rem    clean - exe only; fresh empty database and no images on first run
rem    keep  - also copy current storage\ (database + images) into dist\
rem
rem  Skip the question:  build_exe.bat clean   or   build_exe.bat keep
rem
rem  Note: this .exe runs on Windows only. For the Ubuntu server
rem  build on Ubuntu with build_exe.sh instead.
rem ============================================================
cd /d "%~dp0"

set "MODE=%~1"
if /i "%MODE%"=="clean" goto mode_ok
if /i "%MODE%"=="keep"  goto mode_ok

echo What should the build include?
echo   [c] Clean  - exe only; fresh empty database and no images on first run
echo   [k] Keep   - also copy current storage\ (database + images) next to the exe
set "ANS="
set /p "ANS=Choose [c/k] (default: c): "
if /i "%ANS%"=="k" ( set "MODE=keep" ) else ( set "MODE=clean" )

:mode_ok
echo ==^> Build mode: %MODE%

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo ==^> .venv not found - creating it with a supported Python ^(3.13+^)
    set "BASEPY="
    for %%V in (3.14 3.13) do (
        if not defined BASEPY (
            py -%%V -c "import sys" >nul 2>&1 && set "BASEPY=py -%%V"
        )
    )
    if not defined BASEPY (
        python -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1 && set "BASEPY=python"
    )
    if not defined BASEPY (
        echo [ERROR] Python 3.13 or newer was not found. Install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo ==^> Using !BASEPY! to create .venv
    !BASEPY! -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create .venv
        pause
        exit /b 1
    )
)

rem Activate the venv (steps below also call "%PY%" directly).
call ".venv\Scripts\activate.bat" 2>nul

echo ==^> Installing build + app dependencies into .venv
"%PY%" -m pip install --quiet --upgrade pip
"%PY%" -m pip install --quiet -r requirements.txt
"%PY%" -m pip install --quiet pyinstaller

echo ==^> Building single-file executable
"%PY%" -m PyInstaller --clean --noconfirm quickyee.spec

rem ---- Decide what data travels with the binary --------------
rem This only touches dist\ - your project's storage\ is never deleted.
if exist "dist\storage" rmdir /S /Q "dist\storage"
if /i "%MODE%"=="keep" (
    if exist "storage" (
        echo ==^> Keeping current data: copying storage\ ^(database + images^) into dist\
        xcopy /E /I /Y "storage" "dist\storage" >nul
    ) else (
        echo ==^> No storage\ found - nothing to copy; the exe will start fresh.
    )
) else (
    echo ==^> Clean build: no database or images shipped; the exe starts fresh.
)

echo.
echo Done. Output folder: dist\
echo   dist\quickyee.exe     ^(the binary^)
if /i "%MODE%"=="keep" echo   dist\storage\         ^(database + images carried over^)
echo Put the exe ^(and storage\ if kept^) plus a .env together, then run quickyee.exe
pause
endlocal
