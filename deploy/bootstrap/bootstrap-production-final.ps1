# C9-R3 Production Bootstrap
# stock_server_test is the single source of truth

param(
    [ValidateSet("Test","Deploy")]
    [string]$Mode="Test"
)

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

$SourceRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$StockRoot="C:\stockdata"
$Production="$StockRoot\stock_server"
$BackupRoot="$StockRoot\backup"
$Receipt="$StockRoot\maintenance\deploy-receipt.json"

function Log($m){
    Write-Host "$(Get-Date -Format HH:mm:ss) $m"
}

function ManagedFiles($Root){
    Get-ChildItem $Root -Recurse -File |
    Where-Object {
        $_.FullName -notmatch "\\.venv\\|\\logs\\|\\data\\|\\cache\\|__pycache__"
    }
}

function FileHash($p){
    (Get-FileHash $p -Algorithm SHA256).Hash
}

function Backup-Code {
    if(!(Test-Path $Production)){return ""}

    New-Item -ItemType Directory -Force $BackupRoot | Out-Null
    $dir="$BackupRoot\stock_server-$(Get-Date -Format yyyyMMdd-HHmmss)"
    New-Item -ItemType Directory -Force $dir | Out-Null

    foreach($f in ManagedFiles $Production){
        $rel=$f.FullName.Substring($Production.Length).TrimStart("\")
        $dst=Join-Path $dir $rel
        New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
        Copy-Item $f.FullName $dst -Force
    }

    return $dir
}

function Sync-Code {
    $changed=0
    $skipped=0

    foreach($f in ManagedFiles $SourceRoot){
        $rel=$f.FullName.Substring($SourceRoot.Length).TrimStart("\")
        $dst=Join-Path $Production $rel

        New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null

        if(Test-Path $dst){
            if((FileHash $f.FullName) -eq (FileHash $dst)){
                $skipped++
                continue
            }
        }

        Copy-Item $f.FullName $dst -Force
        $changed++
    }

    return @{
        changed=$changed
        skipped=$skipped
    }
}

function Health {
    Start-Sleep -Seconds 5
    $h=curl.exe -s http://127.0.0.1:8899/health/ready
    return $h
}

Log "[1/8] Validate source"

if(!(Test-Path "$SourceRoot\run_waitress.py")){
    throw "SOURCE_INVALID"
}

$SourceHash=FileHash "$SourceRoot\run_waitress.py"

Write-Host "SOURCE_HASH=$SourceHash"

if($Mode -eq "Test"){
    Write-Host "C9-R3_BOOTSTRAP_TEST=PASS"
    exit 0
}

Log "[2/8] Prepare production"
New-Item -ItemType Directory -Force $Production | Out-Null

Log "[3/8] Backup"
$Backup=Backup-Code
Write-Host "BACKUP=$Backup"

Log "[4/8] Sync"
$Sync=Sync-Code

Write-Host "SYNC_CHANGED=$($Sync.changed)"
Write-Host "SYNC_SKIPPED=$($Sync.skipped)"

Log "[5/8] Restart service"

schtasks /End /TN "\StockData-Web" 2>$null
Start-Sleep -Seconds 3
schtasks /Run /TN "\StockData-Web"

Log "[6/8] Health check"

$Health=Health
Write-Host $Health

if($Health -notmatch '"success":true'){
    throw "HEALTH_CHECK_FAILED"
}

Log "[7/8] Write receipt"

New-Item -ItemType Directory -Force (Split-Path $Receipt) | Out-Null

[ordered]@{
    time=(Get-Date).ToString("o")
    source_hash=$SourceHash
    backup=$Backup
    sync_changed=$Sync.changed
    sync_skipped=$Sync.skipped
    health="PASS"
    result="DEPLOY_PASS"
} |
ConvertTo-Json -Depth 5 |
Out-File $Receipt -Encoding utf8

Log "[8/8] Complete"

Write-Host "RECEIPT=$Receipt"
Write-Host "C9-R3_DEPLOY_PASS"
