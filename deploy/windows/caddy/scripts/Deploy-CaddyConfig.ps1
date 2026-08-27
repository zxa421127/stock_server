[CmdletBinding()]
param(
    [switch]$SkipReload
)


Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"


$CaddyRoot="C:\caddy"

$Template=
"C:\stockdata\stock_server_test\deploy\windows\caddy\templates\Caddyfile.production.template"


$CaddyExe="$CaddyRoot\caddy.exe"

$Current="$CaddyRoot\Caddyfile"

$CandidateDir="$CaddyRoot\candidate"

$Candidate="$CandidateDir\Caddyfile"

$BackupDir="$CaddyRoot\backup"

$ReceiptDir="C:\stockdata\maintenance\caddy"


$Stamp=Get-Date -Format "yyyyMMdd-HHmmss"


function Step($msg){
    Write-Host ""
    Write-Host "================================"
    Write-Host $msg
    Write-Host "================================"
}


function Hash($file){
    (Get-FileHash $file -Algorithm SHA256).Hash
}



try{


Step "Caddy deployment START"



foreach($d in @(
    $CandidateDir,
    $BackupDir,
    $ReceiptDir
)){
    New-Item `
    -ItemType Directory `
    -Force `
    -Path $d |
    Out-Null
}



if(!(Test-Path $Template)){
    throw "TEMPLATE_MISSING"
}


if(!(Test-Path $CaddyExe)){
    throw "CADDY_NOT_FOUND"
}



Step "1. Load secrets"



$ProdSecretFile="$CaddyRoot\secrets\prod-admin-proxy-auth.txt"

$TestSecretFile="$CaddyRoot\secrets\test-admin-proxy-auth.txt"


foreach($f in @(
    $ProdSecretFile,
    $TestSecretFile
)){
    if(!(Test-Path $f)){
        throw "SECRET_MISSING:$f"
    }
}



$ProdSecret=(Get-Content $ProdSecretFile -Raw).Trim()

$TestSecret=(Get-Content $TestSecretFile -Raw).Trim()



if(
[string]::IsNullOrWhiteSpace($ProdSecret) -or
[string]::IsNullOrWhiteSpace($TestSecret)
){
    throw "EMPTY_SECRET"
}



Step "2. Generate candidate Caddyfile"



$content=Get-Content `
$Template `
-Raw



$content=$content.Replace(
"{{PROD_ADMIN_PROXY_AUTH}}",
$ProdSecret
)



$content=$content.Replace(
"{{TEST_ADMIN_PROXY_AUTH}}",
$TestSecret
)



$content |
Set-Content `
$Candidate `
-Encoding UTF8



Step "3. Secret placeholder scan"


$scan=Select-String `
$Candidate `
-Pattern `
"\{\{.*?\}\}"


if($scan){

    $scan | Out-Host

    throw "PLACEHOLDER_SCAN_FAILED"

}



Step "4. Validate candidate"



& $CaddyExe validate `
--config $Candidate `
--adapter caddyfile



if($LASTEXITCODE -ne 0){

    throw "CADDY_VALIDATE_FAILED"

}



Step "5. Backup current"



if(Test-Path $Current){

    Copy-Item `
    $Current `
    "$BackupDir\Caddyfile.$Stamp.bak" `
    -Force

}



Step "6. Atomic replace"



Copy-Item `
$Candidate `
$Current `
-Force



Step "7. Reload"



if(!$SkipReload){

    caddy reload `
    --config $Current `
    --adapter caddyfile


    if($LASTEXITCODE -ne 0){

        Write-Host "Reload failed."

        $backup=
        Get-ChildItem $BackupDir `
        -Filter "Caddyfile.*.bak" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1


        if($backup){

            Copy-Item `
            $backup.FullName `
            $Current `
            -Force

            Write-Host "Rollback completed."

        }


        throw "CADDY_RELOAD_FAILED"

    }

}



Step "8. Listener check"



$https=
Get-NetTCPConnection `
-LocalPort 443 `
-State Listen `
-ErrorAction SilentlyContinue



if(!$https){

    throw "HTTPS_LISTENER_MISSING"

}



Step "9. Receipt"



$Receipt="$ReceiptDir\caddy-deploy-$Stamp.json"


[ordered]@{

    time=(Get-Date).ToString("o")

    template=$Template

    current=$Current

    current_sha256=Hash $Current

    reload=(-not $SkipReload)

    result="PASS"

} |
ConvertTo-Json |
Out-File `
$Receipt `
-Encoding UTF8



Write-Host ""

Write-Host "================================"
Write-Host "CADDY_DEPLOY_PASS"
Write-Host $Receipt
Write-Host "================================"



}

catch{


Write-Host ""

Write-Host "CADDY_DEPLOY_FAIL"

Write-Host $_.Exception.Message


exit 1


}
