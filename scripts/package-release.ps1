[CmdletBinding()]
param(
    [string]$Version = '1.0.0',
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'release')
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$packageName = 'NoronhaMapExporter-v' + $Version
$stagingRoot = Join-Path $OutputDirectory ($packageName + '-staging')
$packageRoot = Join-Path $stagingRoot $packageName
$archivePath = Join-Path $OutputDirectory ($packageName + '.zip')

if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

function Copy-ReleaseFile([string]$RelativePath) {
    $source = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Required release file is missing: $RelativePath" }
    $destination = Join-Path $packageRoot $RelativePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

function Copy-ReleaseDirectory([string]$RelativePath) {
    $source = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Required release directory is missing: $RelativePath" }
    $destination = Join-Path $packageRoot $RelativePath
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force
}

@(
    'setup.ps1',
    'run-2d.ps1',
    'run-satmap.ps1',
    'config.example.json',
    'README.md',
    'LICENSE',
    'mission/README.md',
    'stitcher/README.md',
    'scripts/build.ps1',
    'scripts/create-mission.ps1',
    'scripts/generate-public-cartography.ps1',
    'scripts/validate-config.ps1',
    'scripts/world-presets.ps1',
    'stitcher/apply_hillshade.py',
    'stitcher/export_satmap.py',
    'stitcher/requirements.txt',
    'stitcher/stitch_map.py'
) | ForEach-Object { Copy-ReleaseFile $_ }

Copy-ReleaseDirectory 'addon'
Copy-ReleaseDirectory 'capture-helper'
Copy-ReleaseDirectory 'mission/template'

Get-ChildItem -LiteralPath (Join-Path $packageRoot 'addon') -File -Recurse -Force |
    Where-Object { $_.Name -eq 'config.bin' -or $_.Extension -in @('.pbo', '.bisign', '.bikey') } |
    Remove-Item -Force

Get-ChildItem -LiteralPath (Join-Path $packageRoot 'capture-helper') -Directory -Recurse -Force |
    Where-Object { $_.Name -in @('bin', 'obj') } |
    Remove-Item -Recurse -Force

Compress-Archive -LiteralPath $packageRoot -DestinationPath $archivePath -CompressionLevel Optimal

$hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
$archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
$entryCount = $archive.Entries.Count
$archive.Dispose()

Write-Host "Created $archivePath"
Write-Host "SHA-256: $hash"
Write-Host "Files: $entryCount"
