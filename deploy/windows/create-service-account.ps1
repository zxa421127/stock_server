[CmdletBinding()]
param(
    [string]$ServiceAccount = "StockServerSvc"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$rightsHelper = Join-Path $PSScriptRoot "service-account-rights.ps1"
if (-not (Test-Path $rightsHelper -PathType Leaf)) { throw "服务账号权限辅助脚本不存在：$rightsHelper" }
. $rightsHelper
$current = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "请使用管理员PowerShell运行本脚本"
}

if (-not (Get-LocalUser -Name $ServiceAccount -ErrorAction SilentlyContinue)) {
    Write-Host "服务账号密码硬性要求：16-32位；至少包含1个大写英文字母、1个小写英文字母、1个数字、1个英文半角特殊符号；禁止空格、Tab、换行、中文、全角字符及其他非ASCII字符。"
    $first = Read-Host "请输入${ServiceAccount}服务账号密码" -AsSecureString
    $second = Read-Host "请再次输入同一服务账号密码" -AsSecureString
    $firstPtr = [IntPtr]::Zero
    $secondPtr = [IntPtr]::Zero
    $firstText = $null
    $secondText = $null
    $firstPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($first)
    $secondPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($second)
    try {
        $firstText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($firstPtr)
        $secondText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secondPtr)

        if ($firstText -cne $secondText) { throw "两次输入的服务账号密码不一致，已取消创建服务账号" }
        if ($firstText.Length -lt 16 -or $firstText.Length -gt 32) { throw "服务账号密码必须为16-32位" }
        if ($firstText -match '\s') { throw "服务账号密码禁止包含空格、Tab或换行" }
        if ($firstText.ToCharArray() | Where-Object { ([int][char]$_ -lt 33) -or ([int][char]$_ -gt 126) }) {
            throw "服务账号密码只能使用ASCII英文半角可见字符，禁止中文、全角字符或其他非ASCII字符"
        }
        if ($firstText -cnotmatch '[A-Z]') { throw "服务账号密码必须至少包含1个大写英文字母" }
        if ($firstText -cnotmatch '[a-z]') { throw "服务账号密码必须至少包含1个小写英文字母" }
        if ($firstText -notmatch '[0-9]') { throw "服务账号密码必须至少包含1个数字" }
        if ($firstText -notmatch '[^A-Za-z0-9]') { throw "服务账号密码必须至少包含1个英文半角特殊符号" }
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($firstPtr)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secondPtr)
        $firstText = $null
        $secondText = $null
    }
    New-LocalUser `
        -Name $ServiceAccount `
        -Password $first `
        -Description "StockData application service account" `
        -PasswordNeverExpires | Out-Null
}

Add-LocalGroupMember -Group "Users" -Member $ServiceAccount -ErrorAction SilentlyContinue

$serviceUser = Get-LocalUser -Name $ServiceAccount
if (-not $serviceUser.Enabled) { throw "服务账号${ServiceAccount}当前已禁用，不能用于Windows计划任务" }

$adminGroup = Get-LocalGroup -SID "S-1-5-32-544" -ErrorAction Stop
$adminMember = Get-LocalGroupMember -Group $adminGroup.Name -ErrorAction Stop |
    Where-Object { $_.SID.Value -eq $serviceUser.SID.Value }
if ($adminMember) { throw "服务账号${ServiceAccount}属于Administrators，违反最小权限原则" }

$identity = "$env:COMPUTERNAME\$ServiceAccount"
Ensure-ServiceAccountBatchLogonRight -AccountName $identity

Get-LocalUser -Name $ServiceAccount | Select-Object Name, Enabled, PasswordExpires
Write-Host "PASS：服务账号已准备完成（非管理员、具备SeBatchLogonRight）"
