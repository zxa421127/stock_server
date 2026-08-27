param(
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"


$CaddyRoot="C:\caddy"

$Template=
"C:\stockdata\stock_server_test\deploy\windows\caddy\templates\Caddyfile.production.template"


$SecretRoot="$CaddyRoot\secrets"

$Output="$CaddyRoot\Caddyfile"


$Backup="$CaddyRoot\backup\Caddyfile.before-generate-$(Get-Date -Format yyyyMMdd-HHmmss).bak"



if(!(Test-Path $Template)){
    throw "TEMPLATE_MISSING"
}


foreach($f in @(
"$SecretRoot\prod-admin-proxy-auth.txt",
"$SecretRoot\test-admin-proxy-auth.txt"
)){
    if(!(Test-Path $f)){
        throw "SECRET_MISSING:$f"
    }
}


$content=
Get-Content `
$Template `
-Raw



$ProdSecret=
(Get-Content `
"$SecretRoot\prod-admin-proxy-auth.txt" `
-Raw).Trim()


$TestSecret=
(Get-Content `
"$SecretRoot\test-admin-proxy-auth.txt" `
-Raw).Trim()



# 当前模板替换

$content=
$content.Replace(
'{{PROD_ADMIN_PROXY_AUTH}}',
$ProdSecret
)


$content=
$content.Replace(
'{{TEST_ADMIN_PROXY_AUTH}}',
$TestSecret
)



if($DryRun){

    Write-Host "DRY RUN ONLY"

    Write-Host (
        $content.Substring(0,[Math]::Min(500,$content.Length))
    )

    exit 0
}



Copy-Item `
$Output `
$Backup `
-Force `
-ErrorAction SilentlyContinue



$content |
Set-Content `
$Output `
-Encoding UTF8



Write-Host "Generated Caddyfile"

& "$CaddyRoot\caddy.exe" validate `
--config $Output `
--adapter caddyfile


if($LASTEXITCODE -ne 0){

    if(Test-Path $Backup){
        Copy-Item `
        $Backup `
        $Output `
        -Force
    }

    throw "VALIDATE_FAILED_ROLLBACK"

}


Write-Host ""
Write-Host "BUILD_CADDY_CONFIG_PASS"
