[CmdletBinding()]
param(
    [string]$ProjectRoot = "C:\stockdata\stock_server",
    [string]$IndexUrl = "https://pypi.org/simple",
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if (-not (Test-Path $ProjectRoot)) { throw "项目目录不存在：$ProjectRoot" }
$venvDir = Join-Path $ProjectRoot ".venv"
$python = Join-Path $venvDir "Scripts\python.exe"
$requirements = Join-Path $ProjectRoot "requirements.txt"
if (-not (Test-Path $requirements)) { throw "requirements.txt不存在：$requirements" }

if (-not (Test-Path $python)) {
    $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        & $pyLauncher.Source "-$PythonVersion" -m venv $venvDir
    }
    else {
        $systemPython = Get-Command "python.exe" -ErrorAction SilentlyContinue
        if (-not $systemPython) { throw "未找到Python $PythonVersion，请先安装64位Python" }
        $systemVersion = (& $systemPython.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
        if ($LASTEXITCODE -ne 0 -or $systemVersion -ne $PythonVersion) {
            throw "系统python.exe版本为$systemVersion，要求Python $PythonVersion"
        }
        & $systemPython.Source -m venv $venvDir
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $python)) { throw "创建虚拟环境失败" }
}

$venvVersion = (& $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($LASTEXITCODE -ne 0 -or $venvVersion -ne $PythonVersion) {
    throw "虚拟环境Python版本为$venvVersion，要求Python $PythonVersion。请删除.venv后重新运行。"
}

Write-Host "升级pip并从指定索引安装依赖：$IndexUrl"
& $python -m pip install --index-url $IndexUrl --upgrade pip wheel
if ($LASTEXITCODE -ne 0) { throw "pip升级失败" }

& $python -m pip install --index-url $IndexUrl -r $requirements
if ($LASTEXITCODE -ne 0) { throw "项目依赖安装失败" }

& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw "pip依赖一致性检查失败" }

& $python -c "import flask, redis, PIL, cryptography; print('核心依赖导入正常')"
if ($LASTEXITCODE -ne 0) { throw "核心依赖导入失败" }

Write-Host "PASS：依赖安装和导入检查完成，Python $venvVersion"
