param(
    [ValidateSet("Test","Prepare")]
    [string]$Mode="Test"
)

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

function Step($Percent,$Message){
    Write-Host ("[{0,3}%] {1} {2}" -f $Percent,(Get-Date -Format "HH:mm:ss"),$Message)
}

function Get-Hash($Path){
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpper()
}

function Get-TreeHash($Root,$ExcludeNames){

    $Rows = New-Object System.Collections.ArrayList

    $Files = Get-ChildItem -LiteralPath $Root -Recurse -File -Force

    foreach($File in $Files){

        $Relative = $File.FullName.Substring($Root.Length).TrimStart("\")

        $Top = ($Relative -split "\\")[0]

        if($ExcludeNames -contains $Top){
            continue
        }

        $Hash = Get-Hash $File.FullName

        [void]$Rows.Add(
            "$Relative|$($File.Length)|$Hash"
        )
    }

    $Sorted = $Rows | Sort-Object

    $Bytes = [Text.Encoding]::UTF8.GetBytes(
        ($Sorted -join "`n")
    )

    $SHA=[Security.Cryptography.SHA256]::Create()

    try{
        return (
            [BitConverter]::ToString(
                $SHA.ComputeHash($Bytes)
            )
        ).Replace("-","")
    }
    finally{
        $SHA.Dispose()
    }
}

Step 0 "C10 Blue/Green foundation START"

$DeployRoot = Split-Path $PSScriptRoot -Parent
$ConfigPath = Join-Path $DeployRoot "deploy-config.json"

if(!(Test-Path $ConfigPath)){
    throw "CONFIG_MISSING=$ConfigPath"
}

$Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

$Source = [string]$Config.source_root
$Blue = [string]$Config.blue_path
$Green = [string]$Config.green_path

$Exclude=@(
    ".venv",
    ".git",
    "__pycache__",
    "data",
    "logs",
    "security",
    "backup",
    "maintenance",
    "production"
)

Step 5 "Validate source/config"

foreach($Required in @(
    $Source,
    (Join-Path $Source "run_waitress.py"),
    (Join-Path $Source "requirements.txt")
)){
    if(!(Test-Path $Required)){
        throw "MISSING=$Required"
    }
}

Step 10 "Enumerate managed source"

$Files=Get-ChildItem -LiteralPath $Source -Recurse -File -Force

$Managed=@()

foreach($File in $Files){

    $Relative=$File.FullName.Substring($Source.Length).TrimStart("\")

    $Top=($Relative -split "\\")[0]

    if($Exclude -contains $Top){
        continue
    }

    $Managed += $File
}

Write-Host "MANAGED_FILES=$($Managed.Count)"

$SourceTree=Get-TreeHash $Source $Exclude

Write-Host "SOURCE_TREE_SHA256=$SourceTree"

if($Mode -eq "Test"){

    Write-Host "C10_BLUEGREEN_PREPARE_TEST=PASS"
    exit 0
}


Step 20 "Create directories"

foreach($Dir in @(
    $Blue,
    $Green
)){
    if(!(Test-Path $Dir)){
        New-Item -ItemType Directory -Force $Dir | Out-Null
    }
}


function Sync-Code($Destination,$Name){

    Step 25 "Sync $Name"

    $Changed=0
    $Skipped=0

    foreach($File in $Managed){

        $Relative=$File.FullName.Substring($Source.Length).TrimStart("\")

        $Target=Join-Path $Destination $Relative

        $Parent=Split-Path $Target -Parent

        if(!(Test-Path $Parent)){
            New-Item -ItemType Directory -Force $Parent | Out-Null
        }

        $NeedCopy=$true

        if(Test-Path $Target){

            if((Get-Hash $File.FullName) -eq (Get-Hash $Target)){
                $NeedCopy=$false
            }
        }

        if($NeedCopy){

            Copy-Item $File.FullName $Target -Force
            $Changed++

        }
        else{

            $Skipped++

        }
    }

    Write-Host "$Name changed=$Changed skipped=$Skipped"
}


Sync-Code $Blue "BLUE"

Sync-Code $Green "GREEN"


Step 90 "Verify"

$BlueHash=Get-TreeHash $Blue $Exclude
$GreenHash=Get-TreeHash $Green $Exclude


$OutDir="C:\stockdata\maintenance\bluegreen"

New-Item -ItemType Directory -Force $OutDir | Out-Null

$Out="$OutDir\C10-bluegreen-foundation-$(Get-Date -Format yyyyMMdd-HHmmss).json"


[ordered]@{
    release="C10"
    source=$Source
    source_tree_sha256=$SourceTree
    blue=$Blue
    blue_hash=$BlueHash
    green=$Green
    green_hash=$GreenHash
    managed_files=$Managed.Count
    decision="PASS"
    created=(Get-Date).ToString("o")
} |
ConvertTo-Json -Depth 6 |
Out-File $Out -Encoding utf8


Step 100 "C10_BLUEGREEN_FOUNDATION_PREPARE=PASS"

Write-Host "RECEIPT=$Out"
Write-Host "RECEIPT_SHA256=$(Get-Hash $Out)"
