@echo off
setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0\..
cd /d %ROOT%
set LOG=%ROOT%\build_health_report_web_windows.log

echo [INFO] Build started > "%LOG%"
echo [INFO] Root: %ROOT% >> "%LOG%"

where py >nul 2>nul
if %errorlevel%==0 (
  set PY_BOOT=py -3
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set PY_BOOT=python
  ) else (
    echo [ERROR] Python not found. Please install Python 3.11+ and retry.>> "%LOG%"
    echo [ERROR] Python not found. Please install Python 3.11+ and retry.
    goto :fail
  )
)

if not exist .venv\Scripts\python.exe (
  echo [INFO] Creating virtualenv .venv ...>> "%LOG%"
  %PY_BOOT% -m venv .venv >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo [ERROR] Failed to create virtualenv .venv.>> "%LOG%"
    goto :fail
  )
)

echo [INFO] Installing dependencies...>> "%LOG%"
.venv\Scripts\python.exe -m pip install -U pip >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

.venv\Scripts\python.exe -m pip install pandas openpyxl pypdf reportlab pillow pyinstaller >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [INFO] Running PyInstaller...>> "%LOG%"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean packaging\pyinstaller\health_report_web.spec
if errorlevel 1 goto :fail

echo build done: %ROOT%\dist\HealthReportWeb
echo [INFO] Build succeeded.>> "%LOG%"
echo [INFO] Log: %LOG%
goto :end

:fail
echo.
echo [ERROR] Build failed. Check log: %LOG%
echo.
:end
if "%CI%"=="" pause
endlocal
