[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'config.local.ps1'),
    [string]$OutputDirectory,
    [string]$RaGDayZToolsPath,
    [string]$PythonPath,
    [string]$CartographyOverridePath,
    [string]$LocationOverridePath,
    [ValidateSet('raw', 'no-grid', 'no-labels', 'no-icons', 'reduced-vegetation', 'soft-contours', 'palette', 'combined-v1', 'no-location-text', 'no-location-icons', 'engine-clean-detail-audit', 'engine-clean-overview-audit', 'engine-clean-detail', 'engine-clean-overview', 'satellite-forced', 'satellite-isolated', 'public-config')]
    [string]$CartographyStyle = 'raw'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if ((-not $RaGDayZToolsPath) -and -not (Test-Path -LiteralPath $ConfigPath)) {
    throw "RaGDayZToolsPath is required. Pass it directly or use run-2d.ps1 with config.json."
}

if (-not $RaGDayZToolsPath -and (Test-Path -LiteralPath $ConfigPath)) { . $ConfigPath }

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
    'no-location-text' = 'RscMapControlCombinedV1'
    'no-location-icons' = 'RscMapControlCombinedV1'
    'engine-clean-detail-audit' = 'RscMapControlEngineCleanDetailAudit'
    'engine-clean-overview-audit' = 'RscMapControlEngineCleanOverviewAudit'
    'engine-clean-detail' = 'RscMapControlEngineCleanDetail'
    'engine-clean-overview' = 'RscMapControlEngineCleanOverview'
    'satellite-forced' = 'RscMapControlSatelliteForced'
    'satellite-isolated' = 'RscMapControlSatelliteIsolated'
    'public-config' = 'RscMapControlPublicConfig'
}
$styleParent = $styleParents[$CartographyStyle]
$locationOverrideMarker = '// CLEAN_LOCATION_OVERRIDE_PLACEHOLDER'
$publicCartographyMarker = '// PUBLIC_CARTOGRAPHY_OVERRIDE_PLACEHOLDER'
$locationOverrides = @{
    'no-location-text' = @'
class CfgLocationTypes
{
	class Name { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Mount { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Strategic { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class StrongpointArea { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class FlatArea { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class FlatAreaCity { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class FlatAreaCitySmall { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class CityCenter { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Airport { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameMarine { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameCityCapital { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameCity { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameVillage { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameLocal { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Capital { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class City { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Village { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Local { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Marine { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
};
'@
    'no-location-icons' = @'
class CfgLocationTypes
{
	class Ruin { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class Camp { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class Hill { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class ViewPoint { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class RockArea { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class RailroadStation { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class IndustrialSite { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class LocalOffice { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class BorderCrossing { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class VegetationBroadleaf { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class VegetationFir { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class VegetationPalm { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class VegetationVineyard { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
};
'@
}
$engineCleanLocationOverride = @'
class CfgLocationTypes
{
	class Name { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Mount { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Strategic { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class StrongpointArea { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class FlatArea { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class FlatAreaCity { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class FlatAreaCitySmall { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class CityCenter { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Airport { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameMarine { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameCityCapital { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameCity { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameVillage { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class NameLocal { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Capital { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class City { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Village { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Local { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Marine { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };
	class Ruin { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class Camp { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class Hill { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class ViewPoint { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class RockArea { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class RailroadStation { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class IndustrialSite { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class LocalOffice { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class BorderCrossing { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class VegetationBroadleaf { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class VegetationFir { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class VegetationPalm { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
	class VegetationVineyard { texture = ""; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };
};
'@
$locationOverrides['engine-clean-detail-audit'] = $engineCleanLocationOverride
$locationOverrides['engine-clean-overview-audit'] = $engineCleanLocationOverride
$locationOverrides['engine-clean-detail'] = $engineCleanLocationOverride
$locationOverrides['engine-clean-overview'] = $engineCleanLocationOverride
$locationOverrides['satellite-isolated'] = $engineCleanLocationOverride
$locationOverride = $locationOverrides[$CartographyStyle]
if (-not $locationOverride) { $locationOverride = '' }
if ($LocationOverridePath) {
    if (-not (Test-Path -LiteralPath $LocationOverridePath)) { throw "Location override file not found: $LocationOverridePath" }
    $locationOverride = [System.IO.File]::ReadAllText($LocationOverridePath)
}
$publicCartographyOverride = ''
if ($CartographyOverridePath) {
    if (-not (Test-Path -LiteralPath $CartographyOverridePath)) { throw "Cartography override file not found: $CartographyOverridePath" }
    $publicCartographyOverride = [System.IO.File]::ReadAllText($CartographyOverridePath)
}
if ($CartographyStyle -eq 'public-config' -and -not $publicCartographyOverride) { throw 'public-config requires -CartographyOverridePath.' }

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot 'build\@DayZMapExporter\Addons'
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
if ($stageConfigText.IndexOf($locationOverrideMarker, [System.StringComparison]::Ordinal) -lt 0) { throw "Location override marker was not found in $stageConfig" }
if ($stageConfigText.IndexOf($publicCartographyMarker, [System.StringComparison]::Ordinal) -lt 0) { throw "Public cartography marker was not found in $stageConfig" }
$stageConfigText = $stageConfigText.Replace($rawActiveClass, $selectedActiveClass)
$stageConfigText = $stageConfigText.Replace($locationOverrideMarker, $locationOverride)
[System.IO.File]::WriteAllText($stageConfig, $stageConfigText.Replace($publicCartographyMarker, $publicCartographyOverride))

& $PythonPath $ragBuilder build `
    --source $stageSourceDirectory `
    --output $packageRoot `
    --project-root $repoRoot `
    --temp (Join-Path $repoRoot '.rag-temp') `
    --pbo-name 'DayZMapExporter.pbo' `
    --no-binarize `
    --no-convert-config `
    --no-sign `
    --preflight `
    --force
if ($LASTEXITCODE -ne 0) { throw "RaG PBO Builder failed with exit code $LASTEXITCODE" }

$namedPbo = Join-Path $OutputDirectory 'DayZMapExporter.pbo'
if (-not (Test-Path -LiteralPath $namedPbo)) { throw "Expected RaG PBO output was not created: $namedPbo" }
Copy-Item -LiteralPath (Join-Path $sourceDirectory 'mod.cpp') -Destination (Join-Path $packageRoot 'mod.cpp') -Force
Write-Host "Built DayZMapExporter style '$CartographyStyle' with RaG PBO Builder in $packageRoot"
