@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title بصمة ZKTeco

set PYTHONHOME=
set PYTHONPATH=

where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher is not installed. Install Python 3.12 and try again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment...
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Could not create the environment. Install Python 3.12 and try again.
    pause
    exit /b 1
  )
)

echo Installing server packages...
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto fail

where npm >nul 2>&1
if errorlevel 1 (
  echo Node.js is not installed.
  pause
  exit /b 1
)

pushd frontend
if not exist "node_modules\" (
  echo Installing interface packages...
  call npm install
  if errorlevel 1 goto fail_front
)
if not exist "dist\" (
  echo Building interface...
  call npm run build
  if errorlevel 1 goto fail_front
)
popd

echo.
echo Open http://127.0.0.1:8000
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000
if errorlevel 1 (
  echo The server did not start. If port 8000 is in use, close the other copy and try again.
  pause
)
exit /b 0

:fail_front
popd
:fail
echo Setup failed.
pause
exit /b 1
