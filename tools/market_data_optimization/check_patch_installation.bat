@echo off
setlocal EnableExtensions
pushd "%~dp0..\.." >nul
if errorlevel 1 goto root_failed
set "PROJECT_ROOT=%CD%"
popd >nul
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" goto python_missing
cd /d "%PROJECT_ROOT%"
"%PYTHON_EXE%" "%PROJECT_ROOT%\tools\market_data_optimization\check_patch_installation.py"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" echo SUCCESS: optimized files are installed.
if not "%RESULT%"=="0" echo ERROR: one or more optimized files are not installed.
pause
exit /b %RESULT%
:root_failed
echo ERROR: cannot resolve project root.
pause
exit /b 1
:python_missing
echo ERROR: virtual environment Python not found:
echo %PYTHON_EXE%
pause
exit /b 1
