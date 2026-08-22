@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
pushd "%PROJECT_ROOT%" >nul 2>&1
if errorlevel 1 exit /b 1
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] .venv\Scripts\python.exe was not found.
    popd
    exit /b 1
)
"%PYTHON_EXE%" -m pytest tests\test_kaipanla_triple_snapshot_repository.py -v || goto failed
"%PYTHON_EXE%" -m pytest tests\test_kaipanla_triple_snapshot_service.py -v || goto failed
"%PYTHON_EXE%" -m pytest tests\test_kaipanla_triple_snapshot_scheduler.py -v || goto failed
"%PYTHON_EXE%" -m pytest tests\test_feishu_bidding_sync_v2.py -v || goto failed
"%PYTHON_EXE%" -m pytest tests\test_kaipanla_api_doc_contract.py -v || goto failed
echo Kaipanla three-snapshot focused tests passed.
set "EXIT_CODE=0"
goto finished
:failed
set "EXIT_CODE=1"
:finished
popd
if not defined STOCK_TEST_NO_PAUSE pause
endlocal & exit /b %EXIT_CODE%
