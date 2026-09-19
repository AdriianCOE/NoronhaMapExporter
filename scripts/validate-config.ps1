[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$ConfigPath,
    [ValidateSet('2d', 'satmap')] [string]$Mode = '2d'
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw "CONFIG ERROR: $Message" }

function Require-Value($Object, [string]$Name, [string]$Label, [string]$Hint) {
    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties[$Name] -or [string]::IsNullOrWhiteSpace([string]$Object.$Name)) {
        Fail "$Label is required.`n$Hint"
    }
    return [string]$Object.$Name
}

function Resolve-ConfigPath([string]$Value, [string]$ConfigDirectory) {
    if ([System.IO.Path]::IsPathRooted($Value)) { return [System.IO.Path]::GetFullPath($Value) }
    return [System.IO.Path]::GetFullPath((Join-Path $ConfigDirectory $Value))
}

function Assert-NotPlaceholder([string]$Value, [string]$Label, [string]$Hint) {
    if ($Value -match '(?i)(Path[/\\]To|YourWorld|YourTerrain|YourHeightmap)') {
        Fail "$Label still contains an example value:`n$Value`n$Hint"
    }
}

function Require-Directory([string]$Value, [string]$Label, [string]$ConfigDirectory, [string]$Hint) {
    Assert-NotPlaceholder $Value $Label $Hint
    $path = Resolve-ConfigPath $Value $ConfigDirectory
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        Fail "$Label was not found:`n$path`n$Hint"
    }
    return $path
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    Fail "config.json was not found:`n$ConfigPath`nCreate it with: Copy-Item .\config.example.json .\config.json"
}
try { $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json }
catch { Fail "config.json is not valid JSON:`n$ConfigPath`n$($_.Exception.Message)" }

$configDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($ConfigPath))
if ($null -eq $config.paths -or $null -eq $config.world) { Fail 'config.json needs both "paths" and "world" sections. Start from config.example.json.' }

$worldName = Require-Value $config.world 'name' 'world.name' 'Use the DayZ config world name, for example: "MyTerrain".'
if ($worldName -eq 'YourWorld') { Fail 'World name is still "YourWorld". Replace it with the DayZ config world name for your terrain.' }
if ($worldName -notmatch '^[A-Za-z0-9_]+$') { Fail "world.name '$worldName' must contain only letters, numbers, or underscores." }
try { $worldSize = [double](Require-Value $config.world 'size' 'world.size' 'Enter the terrain width in metres, for example: 8192, 10240, 15360, or 20480.') }
catch { Fail 'world.size must be a positive number of metres, for example: 10240.' }
if ($worldSize -le 0) { Fail 'world.size must be greater than zero metres. Example: 10240 means 10240 m × 10240 m, not pixels.' }

$output = Resolve-ConfigPath (Require-Value $config.paths 'output' 'paths.output' 'Use a relative output folder such as "./output".') $configDirectory

if ($Mode -eq '2d') {
    $dayz = Require-Directory (Require-Value $config.paths 'dayz' 'paths.dayz' 'Set it to the DayZ installation folder.') 'DayZ folder' $configDirectory 'Update paths.dayz in config.json. Example: C:/Games/DayZ'
    if (-not (Test-Path -LiteralPath (Join-Path $dayz 'DayZDiag_x64.exe') -PathType Leaf)) {
        Fail "DayZDiag_x64.exe was not found in:`n$dayz`nUpdate paths.dayz to the folder containing DayZDiag_x64.exe."
    }
    $tools = Require-Directory (Require-Value $config.paths 'dayzTools' 'paths.dayzTools' 'Set it to the DayZ Tools installation folder.') 'DayZ Tools folder' $configDirectory 'Update paths.dayzTools in config.json. Example: C:/Games/DayZ Tools'
    $rag = Require-Directory (Require-Value $config.paths 'ragDayZTools' 'paths.ragDayZTools' 'Set it to your RaG DayZ Tools checkout.') 'RaG DayZ Tools folder' $configDirectory 'Update paths.ragDayZTools in config.json. RaG is required while this command rebuilds the addon.'
    if (-not (Test-Path -LiteralPath (Join-Path $rag 'rag_pbo_builder_gui.py') -PathType Leaf)) {
        Fail "RaG PBO builder was not found in:`n$rag`nSet paths.ragDayZTools to the RaG DayZ Tools checkout."
    }
    $mission = Require-Directory (Require-Value $config.paths 'mission' 'paths.mission' 'Create one with: .\scripts\create-mission.ps1 -ConfigPath .\config.json') 'Mission folder' $configDirectory 'Create one from the included template or update paths.mission in config.json.'
    $profiles = Resolve-ConfigPath (Require-Value $config.paths 'profiles' 'paths.profiles' 'Use a relative folder such as "./.runtime/profiles".') $configDirectory
    $terrain = Require-Directory (Require-Value $config.paths 'terrainMod' 'paths.terrainMod' 'Set it to the terrain mod folder.') 'Terrain mod folder' $configDirectory 'Update paths.terrainMod in config.json. Example: D:/DayZMods/@YourTerrain'
    foreach ($additionalMod in @($config.paths.additionalMods)) {
        if ([string]::IsNullOrWhiteSpace([string]$additionalMod)) { continue }
        [void](Require-Directory ([string]$additionalMod) 'An additional mod folder' $configDirectory 'Update paths.additionalMods in config.json or remove the invalid entry.')
    }
    $exports = $config.exports
    if ($null -eq $exports) { Fail 'exports is required. Enable overview, detail, or both in config.json.' }
    $enabled = @($exports.overview, $exports.detail) | Where-Object { $_ -and $_.enabled }
    if ($enabled.Count -eq 0) { Fail 'No export is enabled. Set exports.overview.enabled or exports.detail.enabled to true.' }
    foreach ($export in $enabled) {
        if ([double]$export.scale -le 0) { Fail 'Each enabled export scale must be greater than zero. Example: 0.33 for overview or 0.15 for detail.' }
    }
    $satmap = $config.satmap
    $satmapMode = if ($satmap -and $satmap.mode) { [string]$satmap.mode } else { 'source' }
    if ($satmapMode -notin @('source', 'engine')) { Fail "satmap.mode '$satmapMode' must be 'source' or 'engine'." }
    $hillshadePath = $null
    $hillshadeWarning = $null
    if ($config.hillshade -and $config.hillshade.enabled) {
        if ([string]$config.hillshade.mode -ne 'multidirectional-slope-weighted') { Fail "hillshade.mode must be 'multidirectional-slope-weighted'." }
        if ([double]$config.hillshade.opacity -le 0 -or [double]$config.hillshade.opacity -gt 1) { Fail 'hillshade.opacity must be greater than zero and at most one.' }
        if ($null -eq $config.hillshade.seaLevel) { Fail 'hillshade.seaLevel is required when hillshade.enabled is true.' }
        $candidate = Require-Value $config.hillshade 'heightmap' 'hillshade.heightmap' 'Set it to the authoritative terrain ASC heightmap.'
        Assert-NotPlaceholder $candidate 'hillshade.heightmap' 'Replace the example path with the authoritative terrain ASC heightmap.'
        $hillshadePath = Resolve-ConfigPath $candidate $configDirectory
        if (-not (Test-Path -LiteralPath $hillshadePath -PathType Leaf)) { Fail "Hillshade heightmap was not found:`n$hillshadePath`nUpdate hillshade.heightmap or set hillshade.enabled to false." }
    }
    $result = [ordered]@{ config = $config; configPath = [System.IO.Path]::GetFullPath($ConfigPath); dayz = $dayz; dayzTools = $tools; ragDayZTools = $rag; mission = $mission; terrainMod = $terrain; profiles = $profiles; output = $output; worldName = $worldName; worldSize = $worldSize; satmapMode = $satmapMode; hillshadePath = $hillshadePath; hillshadeWarning = $hillshadeWarning }
}
else {
    $satmap = $config.satmap
    if ($null -eq $satmap) { Fail 'satmap is required for run-satmap.ps1.' }
    $modeValue = if ($satmap.mode) { [string]$satmap.mode } else { 'source' }
    if ($modeValue -ne 'source') { Fail "run-satmap.ps1 accepts satmap.mode 'source' only. Use run-2d.ps1 for the engine composite." }
    $source = Require-Value $satmap 'source' 'satmap.source' 'Set it to a standalone satellite raster, for example: C:/Maps/YourSatmap.png.'
    Assert-NotPlaceholder $source 'satmap.source' 'Replace the example path with your satellite raster before running run-satmap.ps1.'
    $source = Resolve-ConfigPath $source $configDirectory
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { Fail "Satellite source image was not found:`n$source`nUpdate satmap.source in config.json." }
    $result = [ordered]@{ config = $config; configPath = [System.IO.Path]::GetFullPath($ConfigPath); output = $output; worldName = $worldName; worldSize = $worldSize; satmapSource = $source }
}

[pscustomobject]$result
