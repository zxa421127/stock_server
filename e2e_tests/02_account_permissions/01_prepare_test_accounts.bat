@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
pushd "%PROJECT_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot enter project directory: %PROJECT_ROOT%
    exit /b 1
)

set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Project virtualenv Python was not found: %PYTHON_EXE%
    echo [ERROR] Run deploy\windows\install-dependencies.ps1 first.
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

echo [INFO] Project directory: %PROJECT_ROOT%
echo [INFO] Active DB_FILE:
"%PYTHON_EXE%" -c "import config; print(config.DB_FILE)"
if errorlevel 1 (
    echo [ERROR] Cannot read DB_FILE from config.
    popd
    exit /b 1
)
echo [INFO] Test URL: %STOCK_TEST_BASE_URL%
echo [INFO] Token output: %STOCK_TEST_TOKEN_FILE%
echo [WARNING] This test creates or replaces reserved __MEMBERSHIP_TEST_ accounts in the active DB_FILE.

if /I not "%STOCK_TEST_AUTO_CONFIRM%"=="YES" (
    choice /C YN /M "Continue"
    if errorlevel 2 (
        popd
        endlocal & exit /b 0
    )
)

"%PYTHON_EXE%" -m tools.membership_tester --base-url "%STOCK_TEST_BASE_URL%" --token-file "%STOCK_TEST_TOKEN_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"

popd
if not defined STOCK_TEST_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
