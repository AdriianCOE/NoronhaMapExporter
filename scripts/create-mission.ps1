[CmdletBinding(DefaultParameterSetName = 'Config')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Config')]
    [string]$ConfigPath,
    [Parameter(Mandatory, ParameterSetName = 'World')]
    [string]$WorldName,
    [string]$DestinationRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'mission')
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Read-WorldName([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Configuration was not found: $Path`nCreate it with: Copy-Item .\config.example.json .\config.json"
    }
    try { $config = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
    catch { throw "Configuration is not valid JSON: $Path`n$($_.Exception.Message)" }
    if ($null -eq $config.world -or [string]::IsNullOrWhiteSpace([string]$config.world.name)) {
        throw 'world.name is required in config.json. Example: "MyTerrain".'
    }
    return [string]$config.world.name
}

if ($PSCmdlet.ParameterSetName -eq 'Config') { $WorldName = Read-WorldName $ConfigPath }
if ($WorldName -eq 'YourWorld') { throw 'World name is still "YourWorld". Replace it in config.json or pass -WorldName MyTerrain.' }
if ($WorldName -notmatch '^[A-Za-z0-9_]+$') { throw "World name '$WorldName' must contain only letters, numbers, or underscores for a dayzOffline.<WorldName> folder." }

$template = Join-Path $repoRoot 'mission\template\dayzOffline.YourWorld'
if (-not (Test-Path -LiteralPath $template -PathType Container)) { throw "Included mission template was not found: $template" }
$destinationRootPath = [System.IO.Path]::GetFullPath($DestinationRoot)
$destination = Join-Path $destinationRootPath ('dayzOffline.' + $WorldName)
if (Test-Path -LiteralPath $destination) {
    throw "Exporter mission already exists and was not changed:`n$destination`nChoose another world name or update paths.mission in config.json."
}

New-Item -ItemType Directory -Force -Path $destinationRootPath | Out-Null
Copy-Item -LiteralPath $template -Destination $destination -Recurse -ErrorAction Stop

Write-Host "Created exporter mission:`n$destination"
if ($PSCmdlet.ParameterSetName -eq 'Config') {
    $configDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($ConfigPath))
    $configuredMission = [string]((Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json).paths.mission)
    if (-not [System.IO.Path]::IsPathRooted($configuredMission)) { $configuredMission = Join-Path $configDirectory $configuredMission }
    if (-not [System.StringComparer]::OrdinalIgnoreCase.Equals([System.IO.Path]::GetFullPath($configuredMission), $destination)) {
        $relative = [System.IO.Path]::GetRelativePath($configDirectory, $destination).Replace('\', '/')
        Write-Host "Update config.json:`n  `"mission`": `"./$relative`""
    }
    else { Write-Host 'paths.mission already points to the created exporter mission.' }
}
Write-Host 'Some custom terrains require their own mission files or additional mods. Use the terrain-provided mission when required.'
