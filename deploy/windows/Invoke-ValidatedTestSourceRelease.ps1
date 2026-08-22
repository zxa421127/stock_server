$ErrorActionPreference = "Stop"
$env:PYTHONUNBUFFERED = "1"

$TestRoot = "C:\stockdata\stock_server_test"
$ExpectedScript = Join-Path `
    $TestRoot `
    "deploy\windows\Invoke-ValidatedTestSourceRelease.ps1"

$ActualScript = $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($ActualScript)) {
    throw "无法确定发布验收脚本路径"
}

if (
    [System.IO.Path]::GetFullPath($ActualScript) -ne
    [System.IO.Path]::GetFullPath($ExpectedScript)
) {
    throw (
        "脚本目录不合规。必须位于：" +
        $ExpectedScript
    )
}

Set-Location $TestRoot

$Py = Join-Path `
    $TestRoot `
    ".venv\Scripts\python.exe"

$GateModule = Join-Path `
    $TestRoot `
    "tools\release\validated_test_source_release.py"

if (-not (
    Test-Path `
        -LiteralPath $Py `
        -PathType Leaf
)) {
    throw "TEST虚拟环境Python不存在"
}

if (-not (
    Test-Path `
        -LiteralPath $GateModule `
        -PathType Leaf
)) {
    throw "validated_test_source_release.py不存在"
}

Write-Host ""
Write-Host "======================================================"
Write-Host "VALIDATED TEST SOURCE RELEASE GATE"
Write-Host "DEPLOY ENTRYPOINT=deploy\windows"
Write-Host "RUNTIME OUTPUT=data-test\release-gates"
Write-Host "NO PRODUCTION WRITE"
Write-Host "======================================================"

& $Py `
    -B `
    -X utf8 `
    -m tools.release.validated_test_source_release

$ExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "C3G_FINAL_RUNNER_EXIT=$ExitCode"

if ($ExitCode -ne 0) {
    throw (
        "Validated Test Source Release Gate失败。" +
        "不要继续C4，把尾部输出发给我。"
    )
}
