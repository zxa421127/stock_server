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
if not defined STOCK_TEST_BASE_URL (
    echo [ERROR] STOCK_TEST_BASE_URL must be set explicitly.
    echo [ERROR] Example: set "STOCK_TEST_BASE_URL=http://127.0.0.1:8898"
    popd
    exit /b 2
)
if not defined STOCK_INTERFACE_TEST_TOKEN_FILE set "STOCK_INTERFACE_TEST_TOKEN_FILE=%PROJECT_ROOT%\data-test\interface_test_token.txt"
if not defined STOCK_INTERFACE_TEST_RESULT_DIR set "STOCK_INTERFACE_TEST_RESULT_DIR=%PROJECT_ROOT%\data-test\interface_test_results"
echo Start the service in another window with: python run_waitress.py
echo Test URL: %STOCK_TEST_BASE_URL%
"%PYTHON_EXE%" -m tools.interface_tester
set "EXIT_CODE=%ERRORLEVEL%"
popd
if not defined STOCK_TEST_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
