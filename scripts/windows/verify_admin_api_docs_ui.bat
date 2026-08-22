@echo off
setlocal EnableExtensions

for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"

pushd "%PROJECT_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Cannot enter the project directory.
    echo Project directory: %PROJECT_ROOT%
    exit /b 1
)

set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo ERROR: Project virtualenv Python was not found: %PYTHON_EXE%
    goto :failed
)

if not exist "routes\admin_api_doc_routes.py" (
    echo ERROR: Missing routes\admin_api_doc_routes.py
    goto :failed
)

if not exist "tests\test_admin_api_docs_ui.py" (
    echo ERROR: Missing tests\test_admin_api_docs_ui.py
    goto :failed
)

echo [1/2] Compiling changed Python files...
"%PYTHON_EXE%" -m py_compile "routes\admin_api_doc_routes.py" "tests\test_admin_api_docs_ui.py"
if errorlevel 1 goto :failed

echo.
echo [2/2] Running admin API docs UI tests...
if exist "tests\test_full_api_docs.py" (
    "%PYTHON_EXE%" -m unittest tests.test_admin_api_docs_ui tests.test_full_api_docs -v
) else (
    echo NOTE: tests\test_full_api_docs.py was not found; running the UI tests only.
    "%PYTHON_EXE%" -m unittest tests.test_admin_api_docs_ui -v
)
if errorlevel 1 goto :failed

echo.
echo PASS: Admin API documentation UI verification completed successfully.
popd
pause
exit /b 0

:failed
echo.
echo FAIL: Verification failed. Keep the complete error output for diagnosis.
popd
pause
exit /b 1
