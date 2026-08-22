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
if not defined STOCK_TEST_TOKEN_FILE set "STOCK_TEST_TOKEN_FILE=%PROJECT_ROOT%\data-test\membership_test_tokens.json"
echo Start the service in another window with: python run_waitress.py
echo Active DB_FILE:
"%PYTHON_EXE%" -c "import config; print(config.DB_FILE)"
if errorlevel 1 (
    echo [ERROR] Cannot read DB_FILE from config.
    popd
    exit /b 1
)
echo Test URL: %STOCK_TEST_BASE_URL%
"%PYTHON_EXE%" -m tools.membership_tester --base-url "%STOCK_TEST_BASE_URL%" --token-file "%STOCK_TEST_TOKEN_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"
popd
if not defined STOCK_TEST_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
