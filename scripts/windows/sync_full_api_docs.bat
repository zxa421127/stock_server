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
"%PYTHON_EXE%" -m tools.sync_full_api_docs
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" echo Full API documentation installed and verified.
if not "%EXIT_CODE%"=="0" echo [ERROR] API documentation synchronization failed.
popd
if not defined STOCK_SCRIPT_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
