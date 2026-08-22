@echo off
setlocal EnableExtensions
pushd "%~dp0..\.." >nul
if errorlevel 1 goto root_failed
set "PROJECT_ROOT=%CD%"
popd >nul
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" goto python_missing
cd /d "%PROJECT_ROOT%"
echo STEP 1/3: organize previous patch files
"%PYTHON_EXE%" "%PROJECT_ROOT%\tools\market_data_optimization\organize_previous_patch_layout.py"
if errorlevel 1 goto failed
echo.
echo STEP 2/3: update .env
"%PYTHON_EXE%" "%PROJECT_ROOT%\tools\market_data_optimization\apply_market_data_optimization_env.py"
if errorlevel 1 goto failed
echo.
echo STEP 3/3: verify installation
"%PYTHON_EXE%" "%PROJECT_ROOT%\tools\market_data_optimization\verify_market_data_optimization.py"
if errorlevel 1 goto failed
echo.
echo SUCCESS: all market data optimization setup steps passed.
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
echo ERROR: setup failed. Please send the full console output.
pause
exit /b 1
