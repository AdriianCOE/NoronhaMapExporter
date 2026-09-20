[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'config.json'),
    [string]$DayZToolsPath,
    [string]$OutputDirectory,
    [string]$CartographyOverridePath,
    [string]$LocationOverridePath,
    [ValidateSet('raw', 'public-config')]
    [string]$CartographyStyle = 'raw'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceDirectory = Join-Path $repoRoot 'addon'

if (-not $DayZToolsPath) {
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "DayZToolsPath is required. Pass it directly or configure paths.dayzTools in $ConfigPath."
    }
    $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    $DayZToolsPath = [string]$config.paths.dayzTools
}

$addonBuilder = Join-Path $DayZToolsPath 'Bin\AddonBuilder\AddonBuilder.exe'
$cfgConvert = Join-Path $DayZToolsPath 'Bin\CfgConvert\CfgConvert.exe'
if (-not (Test-Path -LiteralPath $addonBuilder -PathType Leaf)) { throw "AddonBuilder was not found: $addonBuilder" }
if (-not (Test-Path -LiteralPath $cfgConvert -PathType Leaf)) { throw "CfgConvert was not found: $cfgConvert" }
if ($CartographyStyle -eq 'public-config' -and -not $CartographyOverridePath) { throw 'public-config requires -CartographyOverridePath.' }
if ($CartographyOverridePath -and -not (Test-Path -LiteralPath $CartographyOverridePath -PathType Leaf)) { throw "Cartography override was not found: $CartographyOverridePath" }
if ($LocationOverridePath -and -not (Test-Path -LiteralPath $LocationOverridePath -PathType Leaf)) { throw "Location override was not found: $LocationOverridePath" }

if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repoRoot 'build\@NoronhaMapExporter\Addons' }
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$packageRoot = Split-Path -Parent $OutputDirectory
# AddonBuilder derives the PBO prefix from the source directory name when
# packing without a project file. Keep that name aligned with CfgMods' script
# path; otherwise the config loads but mission scripts are not discoverable.
$stageSourceDirectory = Join-Path $repoRoot ('.runtime\addon-stage\' + $CartographyStyle + '\DayZMapExporter')
New-Item -ItemType Directory -Force -Path $stageSourceDirectory, $OutputDirectory | Out-Null
Copy-Item -Path (Join-Path $sourceDirectory '*') -Destination $stageSourceDirectory -Recurse -Force

$stageConfig = Join-Path $stageSourceDirectory 'config.cpp'
$stageConfigText = [System.IO.File]::ReadAllText($stageConfig)
$styleParent = if ($CartographyStyle -eq 'public-config') { 'RscMapControlPublicConfig' } else { 'RscMapControlRaw' }
$stageConfigText = $stageConfigText.Replace('class RscMapControlStyleActive: RscMapControlRaw', ('class RscMapControlStyleActive: ' + $styleParent))
$cartographyOverride = if ($CartographyOverridePath) { [System.IO.File]::ReadAllText($CartographyOverridePath) } else { '' }
$locationOverride = if ($LocationOverridePath) { [System.IO.File]::ReadAllText($LocationOverridePath) } else { '' }
$stageConfigText = $stageConfigText.Replace('// PUBLIC_CARTOGRAPHY_OVERRIDE_PLACEHOLDER', $cartographyOverride)
$stageConfigText = $stageConfigText.Replace('// CLEAN_LOCATION_OVERRIDE_PLACEHOLDER', $locationOverride)
[System.IO.File]::WriteAllText($stageConfig, $stageConfigText)

& $cfgConvert -test $stageConfig
if ($LASTEXITCODE -ne 0) { throw "CfgConvert validation failed with exit code $LASTEXITCODE" }
& $cfgConvert -bin -dst (Join-Path $stageSourceDirectory 'config.bin') $stageConfig
if ($LASTEXITCODE -ne 0) { throw "CfgConvert binarization failed with exit code $LASTEXITCODE" }
& $addonBuilder $stageSourceDirectory $OutputDirectory '-packonly'
if ($LASTEXITCODE -ne 0) { throw "AddonBuilder failed with exit code $LASTEXITCODE" }

$generatedPbo = Join-Path $OutputDirectory 'DayZMapExporter.pbo'
$namedPbo = Join-Path $OutputDirectory 'NoronhaMapExporter.pbo'
if (-not (Test-Path -LiteralPath $generatedPbo -PathType Leaf)) { throw "Expected AddonBuilder output was not created: $generatedPbo" }
if (Test-Path -LiteralPath $namedPbo -PathType Leaf) { Remove-Item -LiteralPath $namedPbo -Force }
Move-Item -LiteralPath $generatedPbo -Destination $namedPbo
Copy-Item -LiteralPath (Join-Path $sourceDirectory 'mod.cpp') -Destination (Join-Path $packageRoot 'mod.cpp') -Force
Write-Host "Built NoronhaMapExporter style '$CartographyStyle' with official DayZ Tools in $packageRoot"
