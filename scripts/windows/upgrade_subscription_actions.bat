@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
pushd "%PROJECT_ROOT%" >nul 2>&1
if errorlevel 1 exit /b 1
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Project virtualenv Python was not found: %PYTHON_EXE%
    popd
    exit /b 1
)
"%PYTHON_EXE%" -m tools.db.migrate_subscription_actions
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" echo Migration completed.
if not "%EXIT_CODE%"=="0" echo [ERROR] Migration failed.
popd
if not defined STOCK_SCRIPT_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
