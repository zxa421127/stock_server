param()

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

$CaddyExe="C:\caddy\caddy.exe"
$Config="C:\caddy\Caddyfile"


if(!(Test-Path $CaddyExe)){
    throw "CADDY_EXECUTABLE_NOT_FOUND:$CaddyExe"
}


if(!(Test-Path $Config)){
    throw "CADDY_CONFIG_NOT_FOUND:$Config"
}


Write-Host "Running Caddy validation..."

& $CaddyExe validate `
    --config $Config `
    --adapter caddyfile


if($LASTEXITCODE -ne 0){
    throw "CADDY_VALIDATE_FAILED"
}


Write-Host "CADDY_VALIDATE_PASS"
