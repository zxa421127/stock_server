@echo off
setlocal EnableExtensions

rem Resolve the project root from this script's own location.
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"

pushd "%PROJECT_ROOT%" || (
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

if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"

echo [INFO] Project root: %PROJECT_ROOT%
echo [INFO] Python: %PYTHON_EXE%

"%PYTHON_EXE%" "%PROJECT_ROOT%\run_waitress.py" >> "%PROJECT_ROOT%\logs\startup.log" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

popd
endlocal & exit /b %EXIT_CODE%
