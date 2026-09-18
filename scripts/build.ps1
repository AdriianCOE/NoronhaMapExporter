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

if (-not $DayZToolsPath) { throw 'DayZToolsPath is not configured.' }
$addonBuilder = Join-Path $DayZToolsPath 'Bin\AddonBuilder\AddonBuilder.exe'
$cfgConvert = Join-Path $DayZToolsPath 'Bin\CfgConvert\CfgConvert.exe'
$sourceDirectory = Join-Path $repoRoot 'addon'

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot 'build\@NoronhaMapExporter-dev\Addons'
}

if (-not (Test-Path -LiteralPath $addonBuilder)) { throw "AddonBuilder not found: $addonBuilder" }
if (-not (Test-Path -LiteralPath $cfgConvert)) { throw "CfgConvert not found: $cfgConvert" }

& $cfgConvert -test (Join-Path $sourceDirectory 'config.cpp')
if ($LASTEXITCODE -ne 0) { throw "CfgConvert validation failed with exit code $LASTEXITCODE" }

& $cfgConvert -bin -dst (Join-Path $sourceDirectory 'config.bin') (Join-Path $sourceDirectory 'config.cpp')
if ($LASTEXITCODE -ne 0) { throw "CfgConvert binarization failed with exit code $LASTEXITCODE" }

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
& $addonBuilder $sourceDirectory $OutputDirectory '-packonly'
if ($LASTEXITCODE -ne 0) { throw "AddonBuilder failed with exit code $LASTEXITCODE" }

# AddonBuilder derives its PBO name from the local source directory ("addon").
# Keep the runtime-facing package name stable without changing the source layout.
$generatedPbo = Join-Path $OutputDirectory 'addon.pbo'
$namedPbo = Join-Path $OutputDirectory 'NoronhaMapExporter.pbo'
if (-not (Test-Path -LiteralPath $generatedPbo)) { throw "Expected AddonBuilder output was not created: $generatedPbo" }
if (Test-Path -LiteralPath $namedPbo) { Remove-Item -LiteralPath $namedPbo -Force }
Move-Item -LiteralPath $generatedPbo -Destination $namedPbo

$packageRoot = Split-Path -Parent $OutputDirectory
Copy-Item -LiteralPath (Join-Path $sourceDirectory 'mod.cpp') -Destination (Join-Path $packageRoot 'mod.cpp') -Force
Write-Host "Built NoronhaMapExporter in $packageRoot"
