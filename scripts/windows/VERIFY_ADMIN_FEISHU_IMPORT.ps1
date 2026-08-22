$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$ErrorActionPreference = "Stop"

$Python = ".\.venv\Scripts\python.exe"

& $Python -m py_compile `
  .\routes\admin_member_routes.py `
  .\tests\test_admin_feishu_registration_import.py

& $Python -m pytest `
  .\tests\test_admin_feishu_registration_import.py `
  .\tests\test_operation_audit.py `
  .\tests\test_admin_user_center.py `
  .\tests\test_app_database_teardown.py `
  -q

if ($LASTEXITCODE -ne 0) {
    throw "管理员飞书新登记入口测试失败"
}

Write-Host "管理员飞书新登记入口验证通过" -ForegroundColor Green
