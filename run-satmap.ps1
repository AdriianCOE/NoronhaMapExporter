[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'config.json'),
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$validation = & (Join-Path $PSScriptRoot 'scripts\validate-config.ps1') -ConfigPath $ConfigPath -Mode satmap
if ($ValidateOnly) { Write-Host "SATMAP configuration is valid for world '$($validation.worldName)'."; exit 0 }
$python = if ($validation.config.paths.python) { [string]$validation.config.paths.python } else { 'python' }
if (-not (Get-Command $python -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath $python)) { throw "Python executable was not found: $python" }
$destination = Join-Path $validation.output (Join-Path $validation.worldName 'satmap')
New-Item -ItemType Directory -Force -Path $destination, (Join-Path $validation.output (Join-Path $validation.worldName 'logs')) | Out-Null
$log = Join-Path $validation.output (Join-Path $validation.worldName 'logs\satmap.log')
& $python (Join-Path $PSScriptRoot 'stitcher\export_satmap.py') --source $validation.satmapSource --output (Join-Path $destination 'satmap.png') --manifest (Join-Path $destination 'manifest.json') --world $validation.worldName --world-size $validation.worldSize 2>&1 | Tee-Object -FilePath $log
if ($LASTEXITCODE -ne 0) { throw "SATMAP export failed with exit code $LASTEXITCODE" }
Write-Host "SATMAP written to $destination"
