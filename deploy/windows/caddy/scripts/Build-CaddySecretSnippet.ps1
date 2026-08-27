param(
    [ValidateSet("test","prod")]
    [string]$Environment="prod"
)


Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"


$CaddyRoot="C:\caddy"

$SecretRoot="$CaddyRoot\secrets"
$GeneratedRoot="$CaddyRoot\generated"


New-Item `
-ItemType Directory `
-Force `
-Path $GeneratedRoot |
Out-Null



if($Environment -eq "prod"){

    $SecretFile="$SecretRoot\prod-admin-proxy-auth.txt"

    $Output="$GeneratedRoot\prod-admin-auth.generated.caddy"

}
else{

    $SecretFile="$SecretRoot\test-admin-proxy-auth.txt"

    $Output="$GeneratedRoot\test-admin-auth.generated.caddy"

}



if(!(Test-Path $SecretFile)){

    throw "SECRET_MISSING:$SecretFile"

}



$Secret=
(Get-Content `
$SecretFile `
-Raw).Trim()



if([string]::IsNullOrWhiteSpace($Secret)){

    throw "EMPTY_SECRET"

}



@"
# GENERATED FILE
# DO NOT EDIT

header_up X-Admin-Proxy-Auth "$Secret"

"@ |
Set-Content `
$Output `
-Encoding UTF8



Write-Host ""
Write-Host "Generated Caddy snippet:"
Write-Host $Output


Get-FileHash `
$Output `
-Algorithm SHA256



Write-Host ""
Write-Host "BUILD_CADDY_SECRET_SNIPPET_PASS"
