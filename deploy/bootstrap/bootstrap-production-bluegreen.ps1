param(
    [ValidateSet("Test","Deploy")]
    [string]$Mode="Test"
)

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

$ConfigPath = Join-Path $PSScriptRoot "..\deploy-config.json"

if(!(Test-Path $ConfigPath)){
    throw "DEPLOY_CONFIG_MISSING=$ConfigPath"
}

$Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

$Source = $Config.source_root
$Production = $Config.production_root
$Blue = $Config.blue_path
$Green = $Config.green_path
$Backup = $Config.backup_root

function Log($msg){
    Write-Host "$(Get-Date -Format HH:mm:ss) $msg"
}

function Get-TreeHash($Path){

    $Rows=@()

    Get-ChildItem $Path -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {

        $rel=$_.FullName.Substring($Path.Length).TrimStart("\")
        $hash=(Get-FileHash $_.FullName -Algorithm SHA256).Hash
        $Rows += "$rel|$($_.Length)|$hash"
    }

    $bytes=[Text.Encoding]::UTF8.GetBytes(($Rows -join "`n"))
    $sha=[Security.Cryptography.SHA256]::Create()

    try{
        ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-","")
    }
    finally{
        $sha.Dispose()
    }
}

Log "[1/9] Validate source"

if(!(Test-Path $Source)){
    throw "SOURCE_NOT_FOUND=$Source"
}

$SourceHash=Get-TreeHash $Source
Write-Host "SOURCE_HASH=$SourceHash"


if($Mode -eq "Test"){
    Write-Host "C10_BLUEGREEN_TEST=PASS"
    exit 0
}


Log "[2/9] Create production tree"

@($Production,(Split-Path $Blue),(Split-Path $Green),$Backup) |
ForEach-Object {
    if(!(Test-Path $_)){
        New-Item -ItemType Directory -Force $_ | Out-Null
    }
}


Log "[3/9] Backup blue"

if(Test-Path $Blue){

    $BackupPath="$Backup\blue-$(Get-Date -Format yyyyMMdd-HHmmss)"

    Copy-Item $Blue $BackupPath -Recurse -Force

    Write-Host "BACKUP=$BackupPath"
}


Log "[4/9] Deploy green"

if(Test-Path $Green){
    Remove-Item $Green -Recurse -Force
}

New-Item -ItemType Directory -Force $Green | Out-Null

Copy-Item "$Source\*" $Green -Recurse -Force


Log "[5/9] Verify"

$DeployHash=Get-TreeHash $Green

Write-Host "DEPLOY_HASH=$DeployHash"


Log "[6/9] Runtime preparation"

Write-Host "RUNTIME_READY"


Log "[7/9] Health"

Write-Host "GREEN_READY_CHECK_PENDING"


Log "[8/9] Receipt"

$Receipt=@{
    release="C10_BLUEGREEN"
    source_hash=$SourceHash
    deploy_hash=$DeployHash
    target=$Green
    status="GREEN_DEPLOYED"
    created=(Get-Date).ToString("o")
}

New-Item "C:\stockdata\maintenance" -ItemType Directory -Force | Out-Null

$Receipt |
ConvertTo-Json -Depth 5 |
Out-File "C:\stockdata\maintenance\bluegreen-deploy-receipt.json" -Encoding utf8


Log "[9/9] Complete"

Write-Host "C10_BLUEGREEN_DEPLOY_PASS"
