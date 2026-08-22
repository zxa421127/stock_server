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

set "PYTHONPATH=%PROJECT_ROOT%\e2e_tests\core;%PYTHONPATH%"
set "STOCK_SERVER_ROOT=%PROJECT_ROOT%"
if not defined STOCK_TEST_BASE_URL (
    echo [ERROR] STOCK_TEST_BASE_URL must be set explicitly.
    echo [ERROR] Example: set "STOCK_TEST_BASE_URL=http://127.0.0.1:8898"
    popd
    exit /b 2
)
if not defined STOCK_TEST_RESULT_DIR set "STOCK_TEST_RESULT_DIR=%PROJECT_ROOT%\data-test\auto_test_results"
if not defined STOCK_TEST_TOKEN_FILE set "STOCK_TEST_TOKEN_FILE=%PROJECT_ROOT%\data-test\membership_test_tokens.json"

 echo [INFO] Project directory: %PROJECT_ROOT%
 echo [INFO] Test URL: %STOCK_TEST_BASE_URL%
 echo [INFO] Result directory: %STOCK_TEST_RESULT_DIR%
"%PYTHON_EXE%" -m auto_tests.catalog_count_test
set "EXIT_CODE=%ERRORLEVEL%"

popd
if not defined STOCK_TEST_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
