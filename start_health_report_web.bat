@echo off
setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0
cd /d %ROOT%
set LOG=%ROOT%\start_health_report_web_windows.log

echo [INFO] Start script launched > "%LOG%"
echo [INFO] Root: %ROOT% >> "%LOG%"

where py >nul 2>nul
if %errorlevel%==0 (
  set PY_BOOT=py -3
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set PY_BOOT=python
  ) else (
    echo [ERROR] Python not found. Install Python 3.11+ first.>> "%LOG%"
    echo [ERROR] Python not found. Install Python 3.11+ first.
    goto :fail
  )
)

if not exist .venv\Scripts\python.exe (
  echo [INFO] Creating virtualenv .venv ...>> "%LOG%"
  %PY_BOOT% -m venv .venv >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv >> "%LOG%"
    goto :fail
  )
)

echo [INFO] Installing runtime dependencies...>> "%LOG%"
.venv\Scripts\python.exe -m pip install -U pip >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

.venv\Scripts\python.exe -m pip install pandas openpyxl pypdf reportlab pillow >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [INFO] Starting local server...>> "%LOG%"
echo.
echo ==========================================
echo   Health Report Web is starting...
echo   Keep this terminal open while using it.
echo   Close this window to stop the service.
echo ==========================================
echo.

.venv\Scripts\python.exe run_web_mvp.py --host 127.0.0.1 --port 8765 --open-browser
goto :end

:fail
echo.
echo [ERROR] Start failed. Check log:
echo %LOG%
echo.

:end
if "%CI%"=="" pause
endlocal
