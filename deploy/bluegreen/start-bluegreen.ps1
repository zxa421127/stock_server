param(
    [ValidateSet("Test","Start")]
    [string]$Mode="Test"
)

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

function Step($Percent,$Message){
    Write-Host ("[{0,3}%] {1} {2}" -f $Percent,(Get-Date -Format "HH:mm:ss"),$Message)
}

function Health($Port){
    try{
        $Result=curl.exe -s "http://127.0.0.1:$Port/health/ready"
        return ($Result -match '"success":true')
    }
    catch{
        return $false
    }
}

$ConfigPath="C:\stockdata\stock_server_test\deploy\deploy-config.json"

if(!(Test-Path $ConfigPath)){
    throw "CONFIG_MISSING"
}

$Config=Get-Content $ConfigPath -Raw | ConvertFrom-Json

$BlueTask="\StockData-Web-Blue"
$GreenTask="\StockData-Web-Green"

$BluePort=[int]$Config.ports.blue
$GreenPort=[int]$Config.ports.green

Step 0 "Blue/Green startup validation START"

Step 10 "Validate tasks"

$Tasks=(schtasks /query /fo LIST) -join "`n"

if($Tasks -notmatch "StockData-Web-Blue"){
    throw "BLUE_TASK_MISSING"
}

if($Tasks -notmatch "StockData-Web-Green"){
    throw "GREEN_TASK_MISSING"
}

if($Mode -eq "Test"){
    Step 100 "BLUEGREEN_START_TEST=PASS"
    exit 0
}

Step 20 "Start BLUE"
schtasks /run /tn $BlueTask
Start-Sleep -Seconds 10

Step 40 "Check BLUE health"

$BlueHealth=Health $BluePort

if(!$BlueHealth){
    throw "BLUE_HEALTH_FAILED_PORT=$BluePort"
}

Step 50 "Start GREEN"
schtasks /run /tn $GreenTask
Start-Sleep -Seconds 10

Step 70 "Check GREEN health"

$GreenHealth=Health $GreenPort

if(!$GreenHealth){
    throw "GREEN_HEALTH_FAILED_PORT=$GreenPort"
}

$OutDir="C:\stockdata\maintenance\bluegreen"
New-Item -ItemType Directory -Force $OutDir | Out-Null

$Out="$OutDir\startup-$(Get-Date -Format yyyyMMdd-HHmmss).json"

[ordered]@{
    release="bluegreen-runtime-start"
    created=(Get-Date).ToString("o")
    blue_port=$BluePort
    green_port=$GreenPort
    blue_health=$BlueHealth
    green_health=$GreenHealth
    decision="PASS"
} |
ConvertTo-Json -Depth 5 |
Out-File $Out -Encoding utf8

Step 100 "BLUEGREEN_START_PASS"

Write-Host "RECEIPT=$Out"
