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
"%PYTHON_EXE%" -m unittest tests.test_subscription_actions tests.test_feishu_subscription_fields -v
set "EXIT_CODE=%ERRORLEVEL%"
popd
if not defined STOCK_TEST_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
