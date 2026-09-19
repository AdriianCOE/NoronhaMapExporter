[CmdletBinding()]
param(
    [ValidateSet('Chernarus', 'Livonia', 'Custom')] [string]$Target,
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'config.json'),
    [string]$DayZPath,
    [string]$DayZToolsPath,
    [string]$TerrainMod,
    [string]$WorldName,
    [double]$WorldSize,
    [string]$PythonPath = 'python',
    [switch]$Check,
    [switch]$NonInteractive,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Get-SteamRoots {
    $roots = [System.Collections.Generic.List[string]]::new()
    $registry = Get-ItemProperty -Path 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue
    if ($registry -and $registry.SteamPath) { $roots.Add([string]$registry.SteamPath) }
    foreach ($path in @("${env:ProgramFiles(x86)}\Steam", "$env:ProgramFiles\Steam")) {
        if ($path) { $roots.Add($path) }
    }
    foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
        $roots.Add((Join-Path $drive.Root 'SteamLibrary'))
    }
    foreach ($steamRoot in @($roots | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $steamRoot -PathType Container)) { continue }
        $libraryFile = Join-Path $steamRoot 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $libraryFile -PathType Leaf) {
            [regex]::Matches((Get-Content -LiteralPath $libraryFile -Raw), '"path"\s+"(?<path>[^"]+)"') | ForEach-Object {
                $roots.Add($_.Groups['path'].Value.Replace('\\\\', '\\'))
            }
        }
    }
    return @($roots | Select-Object -Unique)
}

function Find-Install([string]$FolderName, [string]$RequiredFile) {
    foreach ($steamRoot in Get-SteamRoots) {
        $candidate = Join-Path $steamRoot ('steamapps\common\' + $FolderName)
        if (Test-Path -LiteralPath (Join-Path $candidate $RequiredFile) -PathType Leaf) { return $candidate }
    }
    return $null
}

function Resolve-SetupPath([string]$Current, [string]$Detected, [string]$Label, [string]$RequiredFile) {
    if ($Current) { return [System.IO.Path]::GetFullPath($Current) }
    if ($Detected) {
        if ($NonInteractive) { return $Detected }
        $answer = Read-Host "Detected ${Label}: $Detected`nUse this path? [Y/n]"
        if ([string]::IsNullOrWhiteSpace($answer) -or $answer -match '^(?i)y(es)?$') { return $Detected }
    }
    if ($NonInteractive) { throw "$Label was not detected. Pass its path explicitly." }
    $manual = Read-Host "Enter $Label folder (contains $RequiredFile)"
    if ([string]::IsNullOrWhiteSpace($manual)) { throw "$Label path is required." }
    return [System.IO.Path]::GetFullPath($manual)
}

function Write-Check([string]$Label, [bool]$Ok, [string]$Detail = '') {
    $state = if ($Ok) { 'OK' } else { 'MISSING' }
    Write-Host ('{0,-18} {1,-8} {2}' -f ($Label + '...'), $state, $Detail)
    return $Ok
}

function Invoke-Preflight([string]$Path) {
    $validation = & (Join-Path $PSScriptRoot 'scripts\validate-config.ps1') -ConfigPath $Path -Mode 2d
    $python = if ($validation.config.paths.python) { [string]$validation.config.paths.python } else { 'python' }
    $pythonOk = $null -ne (Get-Command $python -ErrorAction SilentlyContinue)
    $pythonPackagesOk = $false
    if ($pythonOk) {
        & $python -c 'import PIL, numpy' 2>$null
        $pythonPackagesOk = $LASTEXITCODE -eq 0
    }
    $dotnetSdks = @(& dotnet --list-sdks 2>$null)
    $dotnetOk = $LASTEXITCODE -eq 0 -and ($dotnetSdks | Where-Object { $_ -match '^8\.' }).Count -gt 0
    $allOk = $true
    $allOk = (Write-Check 'DayZ' $true $validation.dayz) -and $allOk
    $allOk = (Write-Check 'DayZDiag' (Test-Path -LiteralPath (Join-Path $validation.dayz 'DayZDiag_x64.exe')) '') -and $allOk
    $allOk = (Write-Check 'DayZ Tools' $true $validation.dayzTools) -and $allOk
    $allOk = (Write-Check 'Python' $pythonOk $python) -and $allOk
    $allOk = (Write-Check 'Pillow + NumPy' $pythonPackagesOk $(if ($pythonPackagesOk) { '' } else { "Run: $python -m pip install -r stitcher/requirements.txt" })) -and $allOk
    $allOk = (Write-Check '.NET 8 SDK' $dotnetOk $(if ($dotnetOk) { ($dotnetSdks | Where-Object { $_ -match '^8\.' } | Select-Object -First 1) } else { 'Install .NET 8 SDK.' })) -and $allOk
    $allOk = (Write-Check 'Mission' (Test-Path -LiteralPath $validation.mission -PathType Container) $validation.mission) -and $allOk
    $allOk = (Write-Check 'World' $true ("{0} ({1} m)" -f $validation.worldName, $validation.worldSize)) -and $allOk
    $allOk = (Write-Check 'Configuration' $true $validation.configPath) -and $allOk
    if (-not $allOk) { throw 'Preflight failed. Fix the MISSING entries above.' }
    Write-Host 'Ready to export.'
}

if ($Check) {
    Invoke-Preflight $ConfigPath
    exit 0
}

if ((Test-Path -LiteralPath $ConfigPath -PathType Leaf) -and -not $Force) {
    throw "Configuration already exists: $ConfigPath`nUse .\\setup.ps1 -Force to replace it, or run .\\setup.ps1 -Check to validate it."
}

$DayZPath = Resolve-SetupPath $DayZPath (Find-Install 'DayZ' 'DayZDiag_x64.exe') 'DayZ' 'DayZDiag_x64.exe'
$DayZToolsPath = Resolve-SetupPath $DayZToolsPath (Find-Install 'DayZ Tools' 'Bin\AddonBuilder\AddonBuilder.exe') 'DayZ Tools' 'Bin\AddonBuilder\AddonBuilder.exe'
. (Join-Path $PSScriptRoot 'scripts\world-presets.ps1')
$presets = @(Get-DayZMapExporterWorldPreset -DayZPath $DayZPath)

if (-not $Target) {
    Write-Host 'NoronhaMapExporter Setup'
    $available = @($presets | Where-Object Installed)
    Write-Host '[1] Chernarus'
    if ($available.Id -contains 'Livonia') { Write-Host '[2] Livonia' }
    Write-Host '[3] Custom terrain'
    $selection = Read-Host 'Select target'
    $Target = switch ($selection) { '1' { 'Chernarus' }; '2' { 'Livonia' }; '3' { 'Custom' }; default { throw 'Choose 1, 2, or 3.' } }
}

$terrainModValue = $null
if ($Target -eq 'Custom') {
    if (-not $TerrainMod -and -not $NonInteractive) { $TerrainMod = Read-Host 'Terrain mod folder' }
    if (-not $WorldName -and -not $NonInteractive) { $WorldName = Read-Host 'World config name' }
    if (-not $WorldSize -and -not $NonInteractive) { $WorldSize = [double](Read-Host 'World size in metres') }
    if (-not $TerrainMod -or -not $WorldName -or -not $WorldSize) { throw 'Custom terrain requires -TerrainMod, -WorldName, and -WorldSize.' }
    if (-not (Test-Path -LiteralPath $TerrainMod -PathType Container)) { throw "Terrain mod folder was not found: $TerrainMod" }
    $terrainModValue = [System.IO.Path]::GetFullPath($TerrainMod)
}
else {
    $preset = $presets | Where-Object Id -eq $Target
    if (-not $preset -or -not $preset.Installed) { throw "$Target is not available in this DayZ installation." }
    $WorldName = $preset.WorldName
    $WorldSize = $preset.WorldSize
}

$missionRelative = './mission/dayzOffline.' + $WorldName
$config = [ordered]@{
    paths = [ordered]@{ dayz = $DayZPath; dayzTools = $DayZToolsPath; python = $PythonPath; terrainMod = $terrainModValue; additionalMods = @(); mission = $missionRelative; profiles = './.runtime/profiles'; output = './output' }
    world = [ordered]@{ name = $WorldName; size = $WorldSize }
    capture = [ordered]@{ overlap = 0.1; stabilizationFrames = 2; timeoutSeconds = 30 }
    exports = [ordered]@{ overview = [ordered]@{ enabled = $true; scale = 0.33 }; detail = [ordered]@{ enabled = $true; scale = 0.15 } }
    cartography = [ordered]@{ grid = $false; gridNumbers = $false; locationLabels = $false; locationIcons = $false; vegetation = [ordered]@{ enabled = $true; opacity = 0.75; color = '#94D96B' }; contours = [ordered]@{ enabled = $true; opacity = 0.65; color = '#66513F'; mainOpacity = 0.75 }; roads = [ordered]@{ enabled = $true }; tracks = [ordered]@{ enabled = $true }; buildings = [ordered]@{ enabled = $true }; colors = [ordered]@{ background = '#FFFFFF'; outside = '#D7E8EF'; sea = '#D7E8EF' } }
    satmap = [ordered]@{ mode = 'source' }
    hillshade = [ordered]@{ enabled = $false }
}
$config | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ConfigPath -Encoding utf8
$missionPath = Join-Path $PSScriptRoot ('mission\dayzOffline.' + $WorldName)
if (-not (Test-Path -LiteralPath $missionPath -PathType Container)) {
    & (Join-Path $PSScriptRoot 'scripts\create-mission.ps1') -ConfigPath $ConfigPath
}
else {
    Write-Host "Using existing exporter mission: $missionPath"
}
Invoke-Preflight $ConfigPath
Write-Host ''
Write-Host 'Next command:'
Write-Host '.\run-2d.ps1'
