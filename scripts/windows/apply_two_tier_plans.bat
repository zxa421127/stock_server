@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
pushd "%PROJECT_ROOT%" >nul 2>&1
if errorlevel 1 exit /b 1
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] .venv\Scripts\python.exe was not found.
    popd
    exit /b 1
)
"%PYTHON_EXE%" -m tools.db.apply_two_tier_plans
if errorlevel 1 goto failed
"%PYTHON_EXE%" -m tools.check_two_tier_plans
if errorlevel 1 goto failed
echo Six public plans installed and verified.
set "EXIT_CODE=0"
goto finished
:failed
echo [ERROR] Installation or verification failed.
set "EXIT_CODE=1"
:finished
popd
if not defined STOCK_SCRIPT_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
