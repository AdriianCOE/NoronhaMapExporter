[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'config.local.ps1')
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Missing local configuration: $ConfigPath. Copy config.example.ps1 to config.local.ps1 first."
}

. $ConfigPath

$dayZDiag = Join-Path $DayZPath 'DayZDiag_x64.exe'
$mission = Join-Path $repoRoot 'mission\dayzOffline.Noronha'
$exporterPackage = Join-Path $repoRoot 'build\@NoronhaMapExporter-dev'
$exporterPbo = Join-Path $exporterPackage 'Addons\NoronhaMapExporter.pbo'

if (-not (Test-Path -LiteralPath $dayZDiag)) { throw "DayZDiag_x64.exe not found: $dayZDiag" }
if (-not (Test-Path -LiteralPath $NoronhaModPath)) { throw "NoronhaModPath not found: $NoronhaModPath" }
if (-not (Test-Path -LiteralPath $mission)) { throw "Mission not found: $mission" }
if (-not (Test-Path -LiteralPath $exporterPbo)) { throw "Exporter build not found: $exporterPbo. Run .\scripts\build.ps1 first." }

New-Item -ItemType Directory -Force -Path $ProfileDirectory | Out-Null
$exporterRuntimeDirectory = Join-Path $ProfileDirectory 'DayZMapExporter'
$exporterConfig = Join-Path $exporterRuntimeDirectory 'exporter-config.json'
if (-not (Test-Path -LiteralPath $exporterConfig)) {
    New-Item -ItemType Directory -Force -Path $exporterRuntimeDirectory | Out-Null
    Copy-Item -LiteralPath (Join-Path $repoRoot 'exporter-config.example.json') -Destination $exporterConfig
    Write-Warning "Created $exporterConfig. Set the terrain world bounds/worldSize before opening the exporter."
}
$mods = @($NoronhaModPath) + @($AdditionalModPaths) + @($exporterPackage)
$mods = @($mods | Where-Object { $_ })
foreach ($mod in $mods) {
    if (-not (Test-Path -LiteralPath $mod)) { throw "Mod path not found: $mod" }
}

$launchArguments = @(
    ('-mod=' + ($mods -join ';')),
    ('-mission=' + $mission),
    ('-profiles=' + $ProfileDirectory),
    '-filePatching',
    '-window',
    '-nopause',
    '-dologs',
    '-scriptDebug=true'
)

Start-Process -FilePath $dayZDiag -WorkingDirectory $DayZPath -ArgumentList $launchArguments
Write-Host "Started DayZDiag with profile directory: $ProfileDirectory"
