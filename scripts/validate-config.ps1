[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$ConfigPath,
    [ValidateSet('2d', 'satmap')] [string]$Mode = '2d'
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw "CONFIG ERROR: $Message" }
function Require-Property($Object, [string]$Name, [string]$Context) {
    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties[$Name] -or [string]::IsNullOrWhiteSpace([string]$Object.$Name)) { Fail "$Context.$Name is required." }
    return $Object.$Name
}
function Resolve-ConfigPath([string]$Value, [string]$ConfigDirectory) {
    if ([System.IO.Path]::IsPathRooted($Value)) { return [System.IO.Path]::GetFullPath($Value) }
    return [System.IO.Path]::GetFullPath((Join-Path $ConfigDirectory $Value))
}
function Require-Directory([string]$Value, [string]$Name, [string]$ConfigDirectory) {
    $path = Resolve-ConfigPath $Value $ConfigDirectory
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { Fail "$Name was not found at: $path" }
    return $path
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { Fail "config.json was not found at: $ConfigPath" }
try { $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json } catch { Fail "config.json is not valid JSON: $($_.Exception.Message)" }
$configDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($ConfigPath))
if ($null -eq $config.paths -or $null -eq $config.world) { Fail 'paths and world sections are required.' }

$worldName = Require-Property $config.world 'name' 'world'
$worldSize = [double](Require-Property $config.world 'size' 'world')
if ($worldSize -le 0) { Fail 'world.size must be greater than zero.' }
$output = Resolve-ConfigPath (Require-Property $config.paths 'output' 'paths') $configDirectory

if ($Mode -eq '2d') {
    $dayz = Require-Directory (Require-Property $config.paths 'dayz' 'paths') 'paths.dayz' $configDirectory
    if (-not (Test-Path -LiteralPath (Join-Path $dayz 'DayZDiag_x64.exe') -PathType Leaf)) { Fail "DayZDiag_x64.exe was not found at: $dayz" }
    $tools = Require-Directory (Require-Property $config.paths 'dayzTools' 'paths') 'paths.dayzTools' $configDirectory
    $rag = Require-Directory (Require-Property $config.paths 'ragDayZTools' 'paths') 'paths.ragDayZTools' $configDirectory
    if (-not (Test-Path -LiteralPath (Join-Path $rag 'rag_pbo_builder_gui.py') -PathType Leaf)) { Fail "rag_pbo_builder_gui.py was not found at: $rag" }
    $mission = Require-Directory (Require-Property $config.paths 'mission' 'paths') 'paths.mission' $configDirectory
    $profiles = Resolve-ConfigPath (Require-Property $config.paths 'profiles' 'paths') $configDirectory
    $terrain = $config.paths.terrainMod
    if ($terrain) { $terrain = Require-Directory $terrain 'paths.terrainMod' $configDirectory }
    $exports = $config.exports
    if ($null -eq $exports) { Fail 'exports is required for 2d.' }
    $enabled = @($exports.overview, $exports.detail) | Where-Object { $_ -and $_.enabled }
    if ($enabled.Count -eq 0) { Fail 'Enable at least one of exports.overview or exports.detail.' }
    foreach ($export in $enabled) { if ([double]$export.scale -le 0) { Fail 'Each enabled export scale must be greater than zero.' } }
    $satmap = $config.satmap
    $satmapMode = if ($satmap -and $satmap.mode) { [string]$satmap.mode } else { 'source' }
    if ($satmapMode -notin @('source', 'engine')) { Fail "satmap.mode '$satmapMode' must be 'source' or 'engine'." }
    $hillshadePath = $null
    $hillshadeWarning = $null
    if ($config.hillshade -and $config.hillshade.enabled) {
        if ([string]$config.hillshade.mode -ne 'multidirectional-slope-weighted') { Fail "hillshade.mode must be 'multidirectional-slope-weighted'." }
        if ([double]$config.hillshade.opacity -le 0 -or [double]$config.hillshade.opacity -gt 1) { Fail 'hillshade.opacity must be greater than zero and at most one.' }
        if ($null -eq $config.hillshade.seaLevel) { Fail 'hillshade.seaLevel is required when hillshade is enabled.' }
        $candidate = [string]$config.hillshade.heightmap
        if ([string]::IsNullOrWhiteSpace($candidate)) { $hillshadeWarning = 'Hillshade skipped: no heightmap source configured.' }
        else { $hillshadePath = Resolve-ConfigPath $candidate $configDirectory; if (-not (Test-Path -LiteralPath $hillshadePath -PathType Leaf)) { $hillshadeWarning = "Hillshade skipped: heightmap source was not found at: $hillshadePath"; $hillshadePath = $null } }
    }
    $result = [ordered]@{ config = $config; configPath = [System.IO.Path]::GetFullPath($ConfigPath); dayz = $dayz; dayzTools = $tools; ragDayZTools = $rag; mission = $mission; terrainMod = $terrain; profiles = $profiles; output = $output; worldName = $worldName; worldSize = $worldSize; satmapMode = $satmapMode; hillshadePath = $hillshadePath; hillshadeWarning = $hillshadeWarning }
}
else {
    $satmap = $config.satmap
    if ($null -eq $satmap) { Fail 'satmap is required.' }
    $modeValue = if ($satmap.mode) { [string]$satmap.mode } else { 'source' }
    if ($modeValue -ne 'source') { Fail "run-satmap.ps1 accepts satmap.mode 'source' only. Use run-2d.ps1 for the engine composite." }
    $source = Require-Property $satmap 'source' 'satmap'
    $source = Resolve-ConfigPath $source $configDirectory
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { Fail "satmap.source was not found at: $source" }
    $result = [ordered]@{ config = $config; configPath = [System.IO.Path]::GetFullPath($ConfigPath); output = $output; worldName = $worldName; worldSize = $worldSize; satmapSource = $source }
}

[pscustomobject]$result
