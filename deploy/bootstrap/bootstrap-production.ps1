<#
C9-01-R1 bootstrap-production.ps1

Purpose:
    stock_server_test is the only source repository.
    This script creates/updates production environment automatically.

Usage:
    powershell -ExecutionPolicy Bypass -File .\bootstrap-production.ps1 -Mode Test
    powershell -ExecutionPolicy Bypass -File .\bootstrap-production.ps1 -Mode Deploy

#>

param(
    [ValidateSet("Test","Deploy")]
    [string]$Mode="Test"
)

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

$Root="C:\stockdata"
$Source="$Root\stock_server_test"
$Production="$Root\stock_server"
$Backup="$Root\backup"

function Log($msg){
    Write-Host "$(Get-Date -Format HH:mm:ss) $msg"
}

function Require-Path($p){
    if(-not (Test-Path $p)){
        throw "MISSING_PATH=$p"
    }
}

function Get-TreeHash($Path){

    $Rows=@()

    Get-ChildItem $Path -Recurse -File |
    Where-Object {
        $_.FullName -notmatch "\\__pycache__\\|\\.venv\\|\\logs\\|\\data\\"
    } |
    Sort-Object FullName |
    ForEach-Object {

        $rel=$_.FullName.Substring($Path.Length).TrimStart("\")
        $hash=(Get-FileHash $_.FullName -Algorithm SHA256).Hash

        $Rows += "$rel|$($_.Length)|$hash"
    }

    $bytes=[Text.Encoding]::UTF8.GetBytes(($Rows -join "`n"))

    $sha=[Security.Cryptography.SHA256]::Create()

    try{
        return ([BitConverter]::ToString(
            $sha.ComputeHash($bytes)
        )).Replace("-","")
    }
    finally{
        $sha.Dispose()
    }
}

Log "[1/7] Verify source"

Require-Path $Source

Require-Path "$Source\run_waitress.py"

Require-Path "$Source\requirements.txt"

Require-Path "$Source\deploy"


$SourceHash=Get-TreeHash $Source

Write-Host "SOURCE_TREE_SHA256=$SourceHash"


if($Mode -eq "Test"){

    Log "TEST MODE PASS"

    Write-Host "SOURCE=$Source"
    Write-Host "C9_BOOTSTRAP_TEST=PASS"

    exit 0
}


Log "[2/7] Prepare production"

if(Test-Path $Production){

    New-Item `
        -ItemType Directory `
        -Force `
        $Backup | Out-Null

    $stamp=Get-Date -Format yyyyMMdd-HHmmss

    Copy-Item `
        $Production `
        "$Backup\stock_server-$stamp" `
        -Recurse `
        -Force
}


New-Item `
    -ItemType Directory `
    -Force `
    $Production | Out-Null


Log "[3/7] Sync source to production"


robocopy `
    $Source `
    $Production `
    /MIR `
    /XD `
    data logs .venv __pycache__ `
    /NFL /NDL /NJH /NJS


if($LASTEXITCODE -gt 7){
    throw "ROBOCOPY_FAILED=$LASTEXITCODE"
}


Log "[4/7] Prepare python environment"


if(-not(Test-Path "$Production\.venv")){

    python -m venv "$Production\.venv"

}


& "$Production\.venv\Scripts\python.exe" `
    -m pip install -r "$Production\requirements.txt"


Log "[5/7] Register service task"


schtasks /create `
 /tn "\StockData-Web" `
 /tr "`"$Production\.venv\Scripts\python.exe`" -X utf8 run_waitress.py" `
 /sc onstart `
 /ru SYSTEM `
 /f


Log "[6/7] Start production"


schtasks /run /tn "\StockData-Web"


Start-Sleep -Seconds 8


Log "[7/7] Health check"


$response=curl.exe `
 http://127.0.0.1:8899/health/ready


if($response -notmatch '"success":true'){
    throw "HEALTH_CHECK_FAILED"
}


$ProductionHash=Get-TreeHash $Production

Write-Host ""
Write-Host "SOURCE_HASH=$SourceHash"
Write-Host "PRODUCTION_HASH=$ProductionHash"
Write-Host "C9_BOOTSTRAP_DEPLOY=PASS"
