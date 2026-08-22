param(
    [ValidateSet(
        "blue",
        "green",
        "legacy"
    )]
    [string]$Backend
)


Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"


$BackendDir="C:\caddy\backend"
$BackendFile="$BackendDir\stock_backend.caddy"

$BackupRoot="C:\stockdata\maintenance\caddy"

New-Item `
    -ItemType Directory `
    -Force `
    -Path $BackendDir,$BackupRoot |
    Out-Null


$Stamp=Get-Date -Format "yyyyMMdd-HHmmss"


if(Test-Path $BackendFile){

    Copy-Item `
        $BackendFile `
        "$BackupRoot\stock_backend.caddy.$Stamp.bak" `
        -Force

}


switch($Backend){

    "blue" {

@"
reverse_proxy 127.0.0.1:8901
"@

    }

    "green" {

@"
reverse_proxy 127.0.0.1:8902
"@

    }


    "legacy" {

@"
reverse_proxy 127.0.0.1:8899
"@

    }

} |
Set-Content `
    $BackendFile `
    -Encoding UTF8


Write-Host ""
Write-Host "Backend prepared:"
Write-Host $Backend
Write-Host ""

Write-Host "Backend file:"
Write-Host $BackendFile

Write-Host ""
Write-Host "NOTE:"
Write-Host "Caddy reload has NOT been executed."
