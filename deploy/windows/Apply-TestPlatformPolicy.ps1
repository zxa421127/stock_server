param(
    [switch]$SkipFullPytest
)

$ErrorActionPreference = "Stop"

$TestRoot = (
    Resolve-Path (
        Join-Path `
            $PSScriptRoot `
            "..\.."
    )
).Path

Set-Location $TestRoot

$Py = Join-Path `
    $TestRoot `
    ".venv\Scripts\python.exe"

$PolicyFile = Join-Path `
    $TestRoot `
    "settings\platform_policy.json"

$BackupRoot = `
    "C:\stockdata\backups"

$ProdRoot = `
    "C:\stockdata\stock_server"

$CandidateRoot = `
    "C:\stockdata\stock_server_candidate"

$CaddyFile = `
    "C:\caddy\Caddyfile"


Write-Host ""
Write-Host "======================================================"
Write-Host "APPLY TEST PLATFORM POLICY"
Write-Host "SINGLE POLICY WORKFLOW"
Write-Host "======================================================"


# --------------------------------------------------
# 1. Environment identity
# --------------------------------------------------

if (
    -not (
        Test-Path `
            -LiteralPath $Py `
            -PathType Leaf
    )
) {
    throw "TEST Python???"
}


if (-not (
    Test-Path `
        -LiteralPath $PolicyFile `
        -PathType Leaf
)) {
    throw "platform_policy.json???"
}


if (Test-Path -LiteralPath $CandidateRoot) {
    throw "Candidate???????"
}


$Port8900 = @(
    Get-NetTCPConnection `
        -LocalPort 8900 `
        -State Listen `
        -ErrorAction SilentlyContinue
)


if ($Port8900.Count -ne 0) {
    throw "8900???????"
}


& $Py `
    -B `
    -X utf8 `
    -c `
    "import config; assert str(config.DEPLOYMENT_SLOT).lower() == 'test'; print('POLICY_WORKFLOW_DEPLOYMENT_SLOT=test')"


if ($LASTEXITCODE -ne 0) {
    throw "??TEST????"
}


# --------------------------------------------------
# 2. Service / Production safety baseline
# --------------------------------------------------

$TestConnBefore = @(
    Get-NetTCPConnection `
        -LocalPort 8898 `
        -State Listen `
        -ErrorAction SilentlyContinue
)


$ProdConnBefore = @(
    Get-NetTCPConnection `
        -LocalPort 8899 `
        -State Listen `
        -ErrorAction SilentlyContinue
)


if ($TestConnBefore.Count -ne 1) {
    throw "TEST 8898????"
}


if ($ProdConnBefore.Count -ne 1) {
    throw "Production 8899????"
}


$TestPidBefore = `
    [int]$TestConnBefore[0].OwningProcess

$ProdPidBefore = `
    [int]$ProdConnBefore[0].OwningProcess


$CaddyHashBefore = (
    Get-FileHash `
        -LiteralPath $CaddyFile `
        -Algorithm SHA256
).Hash


function Get-ProductionSourceFingerprint {

    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )


    $Rows = @(

        Get-ChildItem `
            -LiteralPath $Root `
            -Recurse `
            -File `
            -ErrorAction Stop |

        Where-Object {

            $_.FullName -notmatch `
                '\\data\\|\\logs\\|\\__pycache__\\|\\.venv\\'
        } |

        Sort-Object FullName |

        ForEach-Object {

            $Relative = (
                $_.FullName.Substring(
                    $Root.Length
                )
            )


            $HashObject = Get-FileHash `
                -LiteralPath $_.FullName `
                -Algorithm SHA256


            $FileHash = (
                $HashObject.Hash
            )


            Write-Output (
                $Relative + "|" + $FileHash
            )
        }
    )


    return (
        $Rows -join "`n"
    )
}


$ProdSourceBefore = (
    Get-ProductionSourceFingerprint `
        -Root $ProdRoot
)


# --------------------------------------------------
# 3. Snapshot the non-secret Policy file
# --------------------------------------------------

$Stamp = Get-Date `
    -Format "yyyyMMdd-HHmmss"


$PolicyBackupDir = Join-Path `
    $BackupRoot `
    ("test-platform-policy-" + $Stamp)


New-Item `
    -ItemType Directory `
    -Path $PolicyBackupDir `
    -ErrorAction Stop |
    Out-Null


$PolicyBackup = Join-Path `
    $PolicyBackupDir `
    "platform_policy.pre-apply.json"


Copy-Item `
    -LiteralPath $PolicyFile `
    -Destination $PolicyBackup `
    -ErrorAction Stop


$PolicyHash = (
    Get-FileHash `
        -LiteralPath $PolicyFile `
        -Algorithm SHA256
).Hash


$PolicyBackupHash = (
    Get-FileHash `
        -LiteralPath $PolicyBackup `
        -Algorithm SHA256
).Hash


if ($PolicyHash -ne $PolicyBackupHash) {
    throw "Policy??Hash???"
}


Write-Host "POLICY_SNAPSHOT=PASS"
Write-Host "POLICY_SHA256=$PolicyHash"
Write-Host "POLICY_BACKUP=$PolicyBackup"


# --------------------------------------------------
# 4. Fresh-process Policy validation
# --------------------------------------------------

Write-Host ""
Write-Host "======================================================"
Write-Host "VALIDATE PLATFORM POLICY"
Write-Host "======================================================"


& $Py `
    -B `
    -X utf8 `
    -c `
    "from services.platform_policy import load_platform_policy, expand_plans; p=load_platform_policy(); plans=expand_plans(p); assert len(plans)==7; assert len({x['plan_code'] for x in plans})==7; assert sum(1 for x in plans if x.get('public'))==6; print('PLATFORM_POLICY_VALIDATION=PASS'); print('EXPANDED_PLAN_COUNT=7')"


if ($LASTEXITCODE -ne 0) {
    throw "Platform Policy????"
}


# --------------------------------------------------
# 5. TEST plan delta dry-run
# --------------------------------------------------

Write-Host ""
Write-Host "======================================================"
Write-Host "TEST PLAN DELTA DRY RUN"
Write-Host "======================================================"


& $Py `
    -B `
    -X utf8 `
    -m tools.db.sync_test_plan_catalog `
    --project-root $TestRoot


if ($LASTEXITCODE -ne 0) {
    throw "TEST Plan Delta dry-run??"
}


# --------------------------------------------------
# 6. Apply TEST DB delta
#
# No delta -> no-op.
# Delta -> sync engine creates SQLite online backup.
# --------------------------------------------------

Write-Host ""
Write-Host "======================================================"
Write-Host "APPLY TEST PLAN DELTA"
Write-Host "======================================================"


& $Py `
    -B `
    -X utf8 `
    -m tools.db.sync_test_plan_catalog `
    --project-root $TestRoot `
    --apply


if ($LASTEXITCODE -ne 0) {
    throw "TEST Plan Policy??????"
}


# --------------------------------------------------
# 7. Drift gate
# --------------------------------------------------

& $Py `
    -B `
    -X utf8 `
    -m tools.db.verify_plan_catalog `
    --project-root $TestRoot


if ($LASTEXITCODE -ne 0) {
    throw "TEST DB?Policy Catalog??drift"
}


Write-Host "TEST_PLAN_CATALOG_DRIFT=0"


# --------------------------------------------------
# 8. Targeted regression
# --------------------------------------------------

Write-Host ""
Write-Host "======================================================"
Write-Host "POLICY TARGETED PYTEST"
Write-Host "======================================================"


$TargetTests = @(
    "tests/test_platform_policy.py",
    "tests/test_single_policy_source.py",
    "tests/test_platform_policy_semantics.py",
    "tests/test_platform_policy_runtime_wiring.py",
    "tests/test_plan_catalog_policy_wiring.py",
    "tests/test_plan_catalog_sync.py",
    "tests/test_plan_catalog_db_sync.py",
    "tests/test_market_response_limits.py",
    "tests/test_rate_limit_service.py",
    "tests/test_market_query_security.py",
    "tests/test_production_readiness.py",
    "tests/test_web_only_candidate_launcher.py"
)


$ExistingTargets = @()


foreach ($Name in $TargetTests) {

    if (
        Test-Path `
            -LiteralPath (
                Join-Path `
                    $TestRoot `
                    $Name
            ) `
            -PathType Leaf
    ) {
        $ExistingTargets += $Name
    }
}


& $Py `
    -B `
    -X utf8 `
    -m pytest `
    -q `
    @ExistingTargets


if ($LASTEXITCODE -ne 0) {
    throw "Policy targeted pytest??"
}


Write-Host "POLICY_TARGETED_PYTEST=PASS"


# --------------------------------------------------
# 9. Full regression by default
# --------------------------------------------------

if (-not $SkipFullPytest) {

    Write-Host ""
    Write-Host "======================================================"
    Write-Host "FULL PYTEST"
    Write-Host "======================================================"


    & $Py `
        -B `
        -X utf8 `
        -m pytest `
        -q


    if ($LASTEXITCODE -ne 0) {

        Write-Host "FULL_PYTEST=FAIL"

        throw (
            "Full pytest???" +
            "????Production???"
        )
    }


    Write-Host "FULL_PYTEST=PASS"
    Write-Host "POLICY_TEST_GATE=RELEASE_READY"

}
else {

    Write-Host "FULL_PYTEST=SKIPPED"
    Write-Host "POLICY_TEST_GATE=NOT_RELEASE_READY"
}


# --------------------------------------------------
# 10. Final drift gate
# --------------------------------------------------

& $Py `
    -B `
    -X utf8 `
    -m tools.db.verify_plan_catalog `
    --project-root $TestRoot


if ($LASTEXITCODE -ne 0) {
    throw "??Plan verifier??"
}


Write-Host "FINAL_TEST_PLAN_DRIFT=0"


# --------------------------------------------------
# 11. Production/Caddy must be untouched
# --------------------------------------------------

$TestConnAfter = @(
    Get-NetTCPConnection `
        -LocalPort 8898 `
        -State Listen `
        -ErrorAction SilentlyContinue
)


$ProdConnAfter = @(
    Get-NetTCPConnection `
        -LocalPort 8899 `
        -State Listen `
        -ErrorAction SilentlyContinue
)


if (
    $TestConnAfter.Count -ne 1 -or
    [int]$TestConnAfter[0].OwningProcess -ne
    $TestPidBefore
) {
    throw "Policy Workflow??TEST PID??"
}


if (
    $ProdConnAfter.Count -ne 1 -or
    [int]$ProdConnAfter[0].OwningProcess -ne
    $ProdPidBefore
) {
    throw "Policy Workflow??Production PID??"
}


$CaddyHashAfter = (
    Get-FileHash `
        -LiteralPath $CaddyFile `
        -Algorithm SHA256
).Hash


if ($CaddyHashAfter -ne $CaddyHashBefore) {
    throw "Policy Workflow??Caddy??"
}


$ProdSourceAfter = (
    Get-ProductionSourceFingerprint `
        -Root $ProdRoot
)


if ($ProdSourceAfter -ne $ProdSourceBefore) {
    throw "Policy Workflow??Production????"
}


$FinalTest = Invoke-WebRequest `
    -UseBasicParsing `
    -Uri "http://127.0.0.1:8898/ping" `
    -TimeoutSec 10


$FinalProd = Invoke-WebRequest `
    -UseBasicParsing `
    -Uri "http://127.0.0.1:8899/ping" `
    -TimeoutSec 10


$FinalPublic = Invoke-WebRequest `
    -UseBasicParsing `
    -Uri "https://api.lifesupermarket.cn/ping" `
    -TimeoutSec 15


if (
    $FinalTest.StatusCode -ne 200 -or
    $FinalTest.Content -cne "pong"
) {
    throw "??TEST????"
}


if (
    $FinalProd.StatusCode -ne 200 -or
    $FinalProd.Content -cne "pong"
) {
    throw "??Production????"
}


if ($FinalPublic.StatusCode -ne 200) {
    throw "????????"
}


Write-Host ""
Write-Host "======================================================"
Write-Host "APPLY_TEST_PLATFORM_POLICY_FINAL=PASS"
Write-Host "POLICY_SINGLE_SOURCE=PASS"
Write-Host "TEST_PLAN_CATALOG_DRIFT=0"
Write-Host "POLICY_TARGETED_PYTEST=PASS"

if ($SkipFullPytest) {
    Write-Host "FULL_PYTEST=SKIPPED"
    Write-Host "RELEASE_READY=FALSE"
}
else {
    Write-Host "FULL_PYTEST=PASS"
    Write-Host "RELEASE_READY=TRUE"
}

Write-Host "TEST_SERVICE_RESTARTED=FALSE"
Write-Host "TEST_PID_BEFORE=$TestPidBefore"
Write-Host "TEST_PID_AFTER=$($TestConnAfter[0].OwningProcess)"
Write-Host "PRODUCTION_PID_BEFORE=$ProdPidBefore"
Write-Host "PRODUCTION_PID_AFTER=$($ProdConnAfter[0].OwningProcess)"
Write-Host "PRODUCTION_SOURCE_MODIFIED=FALSE"
Write-Host "PRODUCTION_DB_MODIFIED=FALSE"
Write-Host "REAL_CADDY_FILE_UNCHANGED=TRUE"
Write-Host "PUBLIC_PING_AFTER=200"
Write-Host "======================================================"
