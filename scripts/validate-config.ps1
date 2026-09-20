[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$ConfigPath,
    [ValidateSet('2d', 'satmap')] [string]$Mode = '2d'
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw "CONFIG ERROR: $Message" }
function Get-Value($Object, [string]$Name, $Default = $null) {
    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties[$Name]) { return $Default }
    return $Object.$Name
}
function Is-Enabled($Object) { return $null -ne $Object -and [bool](Get-Value $Object 'enabled' $false) }
function Assert-HexColor($Object, [string]$Name, [string]$Label) {
    $value = [string](Get-Value $Object $Name '')
    if ($value -notmatch '^#[0-9A-Fa-f]{6}$') { Fail "$Label must be a #RRGGBB color." }
}
function Assert-Range($Object, [string]$Name, [string]$Label, [double]$Minimum, [double]$Maximum) {
    try { $value = [double](Get-Value $Object $Name) } catch { Fail "$Label must be numeric." }
    if ($value -lt $Minimum -or $value -gt $Maximum) { Fail "$Label must be between $Minimum and $Maximum." }
}
function Require-Value($Object, [string]$Name, [string]$Label, [string]$Hint) {
    $value = Get-Value $Object $Name
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) { Fail "$Label is required.`n$Hint" }
    return [string]$value
}
function Resolve-ConfigPath([string]$Value, [string]$ConfigDirectory) {
    if ([System.IO.Path]::IsPathRooted($Value)) { return [System.IO.Path]::GetFullPath($Value) }
    return [System.IO.Path]::GetFullPath((Join-Path $ConfigDirectory $Value))
}
function Assert-NotPlaceholder([string]$Value, [string]$Label, [string]$Hint) {
    if ($Value -match '(?i)(Path[/\\]To|YourWorld|YourTerrain|YourHeightmap)') { Fail "$Label still contains an example value:`n$Value`n$Hint" }
}
function Require-Directory([string]$Value, [string]$Label, [string]$ConfigDirectory, [string]$Hint) {
    Assert-NotPlaceholder $Value $Label $Hint
    $path = Resolve-ConfigPath $Value $ConfigDirectory
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { Fail "$Label was not found:`n$path`n$Hint" }
    return $path
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { Fail "config.json was not found:`n$ConfigPath`nCreate it with: .\\setup.ps1" }
try { $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json }
catch { Fail "config.json is not valid JSON:`n$ConfigPath`n$($_.Exception.Message)" }

$configDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($ConfigPath))
if ($null -eq $config.paths -or $null -eq $config.world) { Fail 'config.json needs both "paths" and "world" sections. Run .\\setup.ps1 or start from config.example.json.' }
$worldName = Require-Value $config.world 'name' 'world.name' 'Use the DayZ config world name, for example: "ChernarusPlus".'
if ($worldName -notmatch '^[A-Za-z0-9_]+$') { Fail "world.name '$worldName' must contain only letters, numbers, or underscores." }
try { $worldSize = [double](Require-Value $config.world 'size' 'world.size' 'Enter the terrain width in metres, for example: 15360.') }
catch { Fail 'world.size must be a positive number of metres.' }
if ($worldSize -le 0) { Fail 'world.size must be greater than zero metres.' }
$output = Resolve-ConfigPath (Require-Value $config.paths 'output' 'paths.output' 'Use a relative output folder such as "./output".') $configDirectory

if ($Mode -eq 'satmap') {
    $satmap = $config.satmap
    if ($null -eq $satmap) { Fail 'satmap is required for run-satmap.ps1.' }
    if ([string](Get-Value $satmap 'mode' 'source') -ne 'source') { Fail "run-satmap.ps1 accepts satmap.mode 'source' only. Use run-2d.ps1 for the engine composite." }
    $source = Require-Value $satmap 'source' 'satmap.source' 'Set it to a standalone satellite raster.'
    Assert-NotPlaceholder $source 'satmap.source' 'Replace the example path with the source raster before running run-satmap.ps1.'
    $source = Resolve-ConfigPath $source $configDirectory
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { Fail "Satellite source image was not found:`n$source" }
    return [pscustomobject]@{ config = $config; configPath = [System.IO.Path]::GetFullPath($ConfigPath); output = $output; worldName = $worldName; worldSize = $worldSize; satmapSource = $source }
}

$dayz = Require-Directory (Require-Value $config.paths 'dayz' 'paths.dayz' 'Set it to the DayZ installation folder.') 'DayZ folder' $configDirectory 'Update paths.dayz in config.json.'
if (-not (Test-Path -LiteralPath (Join-Path $dayz 'DayZDiag_x64.exe') -PathType Leaf)) { Fail "DayZDiag_x64.exe was not found in:`n$dayz" }
$tools = Require-Directory (Require-Value $config.paths 'dayzTools' 'paths.dayzTools' 'Set it to the DayZ Tools installation folder.') 'DayZ Tools folder' $configDirectory 'Update paths.dayzTools in config.json.'
foreach ($tool in @('Bin\AddonBuilder\AddonBuilder.exe', 'Bin\CfgConvert\CfgConvert.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $tools $tool) -PathType Leaf)) { Fail "Required DayZ Tools executable was not found: $(Join-Path $tools $tool)" }
}
$mission = Require-Directory (Require-Value $config.paths 'mission' 'paths.mission' 'Create one with: .\\scripts\\create-mission.ps1 -ConfigPath .\\config.json') 'Mission folder' $configDirectory 'Create one from the included template or update paths.mission in config.json.'
$profiles = Resolve-ConfigPath (Require-Value $config.paths 'profiles' 'paths.profiles' 'Use a relative folder such as "./.runtime/profiles".') $configDirectory

$terrainValue = Get-Value $config.paths 'terrainMod'
$terrain = $null
if ($null -ne $terrainValue -and -not [string]::IsNullOrWhiteSpace([string]$terrainValue)) {
    $terrain = Require-Directory ([string]$terrainValue) 'Terrain mod folder' $configDirectory 'Update paths.terrainMod in config.json or set it to null for an installed DayZ world.'
}
foreach ($additionalMod in @($config.paths.additionalMods)) {
    if ([string]::IsNullOrWhiteSpace([string]$additionalMod)) { continue }
    [void](Require-Directory ([string]$additionalMod) 'An additional mod folder' $configDirectory 'Update paths.additionalMods in config.json or remove the invalid entry.')
}
$exports = $config.exports
if ($null -eq $exports) { Fail 'exports is required. Enable overview, detail, or both in config.json.' }
$enabled = @($exports.overview, $exports.detail) | Where-Object { $_ -and $_.enabled }
if ($enabled.Count -eq 0) { Fail 'No export is enabled. Set exports.overview.enabled or exports.detail.enabled to true.' }
foreach ($export in $enabled) { if ([double]$export.scale -le 0) { Fail 'Each enabled export scale must be greater than zero.' } }
$satmapMode = [string](Get-Value $config.satmap 'mode' 'source')
if ($satmapMode -notin @('source', 'engine')) { Fail "satmap.mode '$satmapMode' must be 'source' or 'engine'." }

$hillshade = $config.hillshade
$ocean = $config.ocean
$slopeMask = $config.slopeMask
$hillshadeEnabled = Is-Enabled $hillshade
$oceanEnabled = Is-Enabled $ocean
$slopeMaskEnabled = Is-Enabled $slopeMask
$touristEnabled = $hillshadeEnabled -or $oceanEnabled -or $slopeMaskEnabled
$hillshadePath = $null
$hillshadeWarning = $null

if ($hillshadeEnabled) {
    $hillshadeMode = [string](Get-Value $hillshade 'mode' 'multidirectional-slope-weighted')
    if ($hillshadeMode -notin @('multidirectional', 'multidirectional-slope-weighted')) { Fail "hillshade.mode must be 'multidirectional' or 'multidirectional-slope-weighted'." }
    if ([string](Get-Value $hillshade 'blend' 'luminance') -ne 'luminance') { Fail "hillshade.blend must be 'luminance'." }
    Assert-Range $hillshade 'opacity' 'hillshade.opacity' 0.0 1.0
    if ([double](Get-Value $hillshade 'opacity' 0) -le 0) { Fail 'hillshade.opacity must be greater than zero.' }
    $slopeStart = [double](Get-Value $hillshade 'slopeStartDeg' (Get-Value $hillshade 'slopeStart' 5))
    $slopeFull = [double](Get-Value $hillshade 'slopeFullDeg' (Get-Value $hillshade 'slopeFull' 30))
    if ($slopeStart -lt 0 -or $slopeStart -ge $slopeFull) { Fail 'hillshade slope thresholds require 0 <= slopeStartDeg < slopeFullDeg.' }
}
if ($oceanEnabled) {
    Assert-HexColor $ocean 'color' 'ocean.color'
    if ($null -ne (Get-Value $ocean 'coastHaloColor')) { Assert-HexColor $ocean 'coastHaloColor' 'ocean.coastHaloColor' }
    if ($null -ne (Get-Value $ocean 'coastStrokeColor')) { Assert-HexColor $ocean 'coastStrokeColor' 'ocean.coastStrokeColor' }
    if ($null -ne (Get-Value $ocean 'coastHaloWidthPx')) { Assert-Range $ocean 'coastHaloWidthPx' 'ocean.coastHaloWidthPx' 0 64 }
    if ($null -ne (Get-Value $ocean 'coastStrokeWidthPx')) { Assert-Range $ocean 'coastStrokeWidthPx' 'ocean.coastStrokeWidthPx' 0 16 }
}
if ($slopeMaskEnabled) {
    Assert-HexColor $slopeMask 'color' 'slopeMask.color'
    Assert-Range $slopeMask 'opacity' 'slopeMask.opacity' 0 1
    $maskStart = [double](Get-Value $slopeMask 'startDeg' 18)
    $maskFull = [double](Get-Value $slopeMask 'fullDeg' 35)
    if ($maskStart -lt 0 -or $maskStart -ge $maskFull) { Fail 'slopeMask thresholds require 0 <= startDeg < fullDeg.' }
}
if ($touristEnabled) {
    if ($null -eq $hillshade) { Fail 'hillshade is required when ocean or slopeMask is enabled because it supplies the authoritative ASC heightmap and sea level.' }
    if ($null -eq (Get-Value $hillshade 'seaLevel')) { Fail 'hillshade.seaLevel is required when tourist composition is enabled.' }
    $candidate = Require-Value $hillshade 'heightmap' 'hillshade.heightmap' 'Set it to the authoritative terrain ASC heightmap.'
    Assert-NotPlaceholder $candidate 'hillshade.heightmap' 'Replace the example path or disable tourist composition.'
    $hillshadePath = Resolve-ConfigPath $candidate $configDirectory
    if (-not (Test-Path -LiteralPath $hillshadePath -PathType Leaf)) { Fail "Hillshade heightmap was not found:`n$hillshadePath" }
}

[pscustomobject]@{ config = $config; configPath = [System.IO.Path]::GetFullPath($ConfigPath); dayz = $dayz; dayzTools = $tools; mission = $mission; terrainMod = $terrain; profiles = $profiles; output = $output; worldName = $worldName; worldSize = $worldSize; satmapMode = $satmapMode; hillshadePath = $hillshadePath; hillshadeWarning = $hillshadeWarning; touristEnabled = $touristEnabled }
