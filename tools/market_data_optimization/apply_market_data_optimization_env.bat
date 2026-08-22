@echo off
setlocal EnableExtensions
pushd "%~dp0..\.." >nul
if errorlevel 1 goto root_failed
set "PROJECT_ROOT=%CD%"
popd >nul
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" goto python_missing
cd /d "%PROJECT_ROOT%"
"%PYTHON_EXE%" "%PROJECT_ROOT%\tools\market_data_optimization\apply_market_data_optimization_env.py"
if errorlevel 1 goto failed
echo.
echo SUCCESS: market data optimization settings were written to .env.
echo NEXT: restart the service with python run_waitress.py
pause
exit /b 0
:root_failed
echo ERROR: cannot resolve project root.
pause
exit /b 1
:python_missing
echo ERROR: virtual environment Python not found:
echo %PYTHON_EXE%
pause
exit /b 1
:failed
echo.
echo ERROR: apply_market_data_optimization_env.py failed.
pause
exit /b 1
