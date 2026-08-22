param(
    [switch]$RunPrepare
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DeployRoot = "C:\stockdata\stock_server_test\deploy"
$BlueGreenDir = Join-Path $DeployRoot "bluegreen"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempRoot = Join-Path $env:TEMP "C10-BlueGreen-Foundation-$Stamp"
$ZipPath = Join-Path $TempRoot "package.zip"
$ExtractRoot = Join-Path $TempRoot "extract"

function Step {
    param([int]$Percent,[string]$Message)
    Write-Host ("[{0,3}%] {1} {2}" -f $Percent,(Get-Date -Format "HH:mm:ss"),$Message)
}

function SHA256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

try {
    Step 0 "C10 Blue/Green foundation installer START"

    if(-not (Test-Path -LiteralPath "C:\stockdata\stock_server_test" -PathType Container)){
        throw "SOURCE_ROOT_MISSING:C:\stockdata\stock_server_test"
    }

    New-Item -ItemType Directory -Force -Path $TempRoot,$ExtractRoot,$BlueGreenDir | Out-Null

    Step 10 "Materialize verified package"
    $B64 = @'
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
'@
    [IO.File]::WriteAllBytes($ZipPath,[Convert]::FromBase64String(($B64 -replace "\s","")))

    $ZipSHA = SHA256 $ZipPath
    if($ZipSHA -ne "4BB68665991DD6643CD5E2891775FE4EE7250CC5F8D3797EA2F4709A45501F01"){
        throw "PACKAGE_SHA_MISMATCH:$ZipSHA"
    }

    Step 25 "Extract package"
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractRoot -Force

    $SrcConfig = Join-Path $ExtractRoot "deploy-config.json"
    $SrcScript = Join-Path $ExtractRoot "bluegreen\prepare-bluegreen-foundation.ps1"
    if(-not (Test-Path $SrcConfig -PathType Leaf)){ throw "PACKAGE_CONFIG_MISSING" }
    if(-not (Test-Path $SrcScript -PathType Leaf)){ throw "PACKAGE_SCRIPT_MISSING" }

    if((SHA256 $SrcConfig) -ne "8AC1DE81C207CD5A8B14B6A3AE311A53A1B94405647E3EF89AA540BF9F895CD3"){ throw "CONFIG_SHA_MISMATCH" }
    if((SHA256 $SrcScript) -ne "14D504FD01FE3BA0BD6157C908875793A493B9AFC3C837EDC8D52A6FA5273969"){ throw "SCRIPT_SHA_MISMATCH" }

    Step 40 "Backup previous deploy files if present"
    $DstConfig = Join-Path $DeployRoot "deploy-config.json"
    $DstScript = Join-Path $BlueGreenDir "prepare-bluegreen-foundation.ps1"

    if(Test-Path $DstConfig -PathType Leaf){
        Copy-Item -LiteralPath $DstConfig -Destination "$DstConfig.backup-$Stamp" -Force
    }
    if(Test-Path $DstScript -PathType Leaf){
        Copy-Item -LiteralPath $DstScript -Destination "$DstScript.backup-$Stamp" -Force
    }

    Step 55 "Install corrected Blue/Green config and foundation script"
    Copy-Item -LiteralPath $SrcConfig -Destination $DstConfig -Force
    Copy-Item -LiteralPath $SrcScript -Destination $DstScript -Force

    if((SHA256 $DstConfig) -ne "8AC1DE81C207CD5A8B14B6A3AE311A53A1B94405647E3EF89AA540BF9F895CD3"){ throw "INSTALLED_CONFIG_SHA_MISMATCH" }
    if((SHA256 $DstScript) -ne "14D504FD01FE3BA0BD6157C908875793A493B9AFC3C837EDC8D52A6FA5273969"){ throw "INSTALLED_SCRIPT_SHA_MISMATCH" }

    Step 70 "Installed files verified"
    Write-Host "CONFIG=$DstConfig"
    Write-Host "CONFIG_SHA256=$(SHA256 $DstConfig)"
    Write-Host "SCRIPT=$DstScript"
    Write-Host "SCRIPT_SHA256=$(SHA256 $DstScript)"
    Write-Host "TEST_PORT=8898"
    Write-Host "PUBLIC_PORT=8899"
    Write-Host "BLUE_BACKEND_PORT=8901"
    Write-Host "GREEN_BACKEND_PORT=8902"

    if($RunPrepare){
        Step 75 "Run foundation TEST"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $DstScript -Mode Test
        if($LASTEXITCODE -ne 0){ throw "FOUNDATION_TEST_FAILED:RC=$LASTEXITCODE" }

        Step 80 "Prepare disposable BLUE/GREEN code slots"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $DstScript -Mode Prepare
        if($LASTEXITCODE -ne 0){ throw "FOUNDATION_PREPARE_FAILED:RC=$LASTEXITCODE" }
    }

    Step 100 "C10_BLUEGREEN_FOUNDATION_INSTALL=PASS"
}
catch {
    Write-Host ""
    Write-Host "C10_BLUEGREEN_FOUNDATION_INSTALL=FAIL"
    Write-Host "ERROR=$($_.Exception.Message)"
    exit 1
}
finally {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
