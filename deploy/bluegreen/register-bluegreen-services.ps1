param([string]$Mode="Install")

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

$Python="C:\stockdata\stock_server_test\.venv\Scripts\python.exe"
$Blue="C:\stockdata\production\blue\stock_server"
$Green="C:\stockdata\production\green\stock_server"

foreach($p in @($Python,"$Blue\run_waitress.py","$Green\run_waitress.py")){
    if(!(Test-Path $p)){throw "MISSING=$p"}
}

foreach($t in @("StockData-Web-Blue","StockData-Web-Green")){
    schtasks /end /tn "\$t" 2>$null
    Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue
}

$b=New-ScheduledTaskAction -Execute $Python -Argument "`"$Blue\run_waitress.py`" --port 8901" -WorkingDirectory $Blue
$g=New-ScheduledTaskAction -Execute $Python -Argument "`"$Green\run_waitress.py`" --port 8902" -WorkingDirectory $Green
$tr=New-ScheduledTaskTrigger -AtStartup

Register-ScheduledTask -TaskName "StockData-Web-Blue" -Action $b -Trigger $tr -User SYSTEM -RunLevel Highest -Force
Register-ScheduledTask -TaskName "StockData-Web-Green" -Action $g -Trigger $tr -User SYSTEM -RunLevel Highest -Force

Write-Host "BLUEGREEN_SERVICE_INSTALL=PASS"
