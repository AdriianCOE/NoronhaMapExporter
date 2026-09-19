[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'config.local.ps1'),
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Missing local configuration: $ConfigPath. Copy config.example.ps1 to config.local.ps1 and set DayZToolsPath."
}

. $ConfigPath

if (-not $RaGDayZToolsPath) { throw 'RaGDayZToolsPath is not configured.' }
if (-not $PythonPath) { $PythonPath = 'python' }
$ragBuilder = Join-Path $RaGDayZToolsPath 'rag_pbo_builder_gui.py'
$sourceDirectory = Join-Path $repoRoot 'addon'

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot 'build\@NoronhaMapExporter-dev\Addons'
}

$packageRoot = Split-Path -Parent $OutputDirectory
if (-not (Test-Path -LiteralPath $ragBuilder)) { throw "RaG PBO Builder source not found: $ragBuilder" }
if (-not (Get-Command $PythonPath -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath $PythonPath)) { throw "Python executable not found: $PythonPath" }

& $PythonPath $ragBuilder build `
    --source $sourceDirectory `
    --output $packageRoot `
    --project-root 'P:' `
    --temp (Join-Path $repoRoot '.rag-temp') `
    --pbo-name 'NoronhaMapExporter.pbo' `
    --no-binarize `
    --no-convert-config `
    --no-sign `
    --preflight `
    --force
if ($LASTEXITCODE -ne 0) { throw "RaG PBO Builder failed with exit code $LASTEXITCODE" }

$namedPbo = Join-Path $OutputDirectory 'NoronhaMapExporter.pbo'
if (-not (Test-Path -LiteralPath $namedPbo)) { throw "Expected RaG PBO output was not created: $namedPbo" }
Copy-Item -LiteralPath (Join-Path $sourceDirectory 'mod.cpp') -Destination (Join-Path $packageRoot 'mod.cpp') -Force
Write-Host "Built NoronhaMapExporter with RaG PBO Builder in $packageRoot"
