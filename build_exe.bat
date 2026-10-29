@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Build ZKT-Basma

set PYTHONHOME=
set PYTHONPATH=

if not exist ".venv\Scripts\python.exe" (
  echo Python environment is missing. Run start.bat once, or install Python 3.12.
  py -3.12 -m venv .venv
  if errorlevel 1 goto fail
)

echo Installing build tools...
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt pyinstaller
if errorlevel 1 goto fail

where npm >nul 2>&1
if errorlevel 1 (
  echo Node.js is required to build the interface.
  pause
  exit /b 1
)

pushd frontend
if not exist "node_modules\" call npm install
if errorlevel 1 goto fail_front
echo Building interface...
call npm run build
if errorlevel 1 goto fail_front
popd

echo Creating ZKT-Basma.exe ...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean ZKT-Basma.spec
if errorlevel 1 goto fail

echo.
echo Ready: dist\ZKT-Basma.exe
echo Copy that file to any Windows PC. Python is not required there.
pause
exit /b 0

:fail_front
popd
:fail
echo Build failed.
pause
exit /b 1
