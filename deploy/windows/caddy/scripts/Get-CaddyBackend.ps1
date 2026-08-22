param()

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

$BackendFile="C:\caddy\backend\stock_backend.caddy"

Write-Host "=============================="
Write-Host " Current Caddy Backend "
Write-Host "=============================="

if(!(Test-Path $BackendFile)){
    Write-Host "Backend file does not exist."
    Write-Host "Current mode: LEGACY"
    Write-Host "Target: 127.0.0.1:8899"
    exit 0
}

Get-Content $BackendFile
