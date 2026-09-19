[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'config.local.ps1'),
    [string]$OutputDirectory,
    [ValidateSet('raw', 'no-grid', 'no-labels', 'no-icons', 'reduced-vegetation', 'soft-contours', 'palette', 'combined-v1')]
    [string]$CartographyStyle = 'raw'
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
$stageSourceDirectory = Join-Path $repoRoot ('.runtime\clean-cartography-stage\' + $CartographyStyle + '\addon')
$styleParents = @{
    'raw' = 'RscMapControlRaw'
    'no-grid' = 'RscMapControlNoGrid'
    'no-labels' = 'RscMapControlNoLabels'
    'no-icons' = 'RscMapControlNoIcons'
    'reduced-vegetation' = 'RscMapControlReducedVegetation'
    'soft-contours' = 'RscMapControlSoftContours'
    'palette' = 'RscMapControlPalette'
    'combined-v1' = 'RscMapControlCombinedV1'
}
$styleParent = $styleParents[$CartographyStyle]

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot 'build\@NoronhaMapExporter-dev\Addons'
}

$packageRoot = Split-Path -Parent $OutputDirectory
if (-not (Test-Path -LiteralPath $ragBuilder)) { throw "RaG PBO Builder source not found: $ragBuilder" }
if (-not (Get-Command $PythonPath -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath $PythonPath)) { throw "Python executable not found: $PythonPath" }
if (-not $styleParent) { throw "Cartography style has no RscMapControl parent: $CartographyStyle" }

# RscMapControl is bound when DayZ creates a MapWidget, so the selected audit
# style is staged into an otherwise unchanged addon before packing. The
# committed source always keeps its active selector on Raw; no test mutates it.
New-Item -ItemType Directory -Force -Path $stageSourceDirectory | Out-Null
Copy-Item -Path (Join-Path $sourceDirectory '*') -Destination $stageSourceDirectory -Recurse -Force
$stageConfig = Join-Path $stageSourceDirectory 'config.cpp'
$rawActiveClass = 'class RscMapControlStyleActive: RscMapControlRaw'
$selectedActiveClass = 'class RscMapControlStyleActive: ' + $styleParent
$stageConfigText = [System.IO.File]::ReadAllText($stageConfig)
if ($stageConfigText.IndexOf($rawActiveClass, [System.StringComparison]::Ordinal) -lt 0) { throw "Raw RscMapControl selector was not found in $stageConfig" }
[System.IO.File]::WriteAllText($stageConfig, $stageConfigText.Replace($rawActiveClass, $selectedActiveClass))

& $PythonPath $ragBuilder build `
    --source $stageSourceDirectory `
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
Write-Host "Built NoronhaMapExporter style '$CartographyStyle' with RaG PBO Builder in $packageRoot"
