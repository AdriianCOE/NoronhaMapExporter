[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'config.json'),
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'

function Write-ExporterConfig($Validation, $Scale) {
    $capture = $Validation.config.capture
    $runtime = Join-Path $Validation.profiles 'DayZMapExporter'
    New-Item -ItemType Directory -Force -Path $runtime | Out-Null
    $payload = [ordered]@{
        WorldName = $Validation.worldName
        WorldSize = $Validation.worldSize
        WorldMinX = 0
        WorldMaxX = $Validation.worldSize
        WorldMinZ = 0
        WorldMaxZ = $Validation.worldSize
        ExportScale = [double]$Scale
        OverlapFraction = [double]$capture.overlap
        OutputPrefix = 'map'
        AutoCaptureEnabled = $true
        StabilizationFrames = if ($capture.stabilizationFrames) { [int]$capture.stabilizationFrames } else { 2 }
        StabilizationTolerance = 0.01
        CaptureTimeoutSeconds = if ($capture.timeoutSeconds) { [int]$capture.timeoutSeconds } else { 30 }
        DetailAudit = [ordered]@{ Enabled = $false; CenterX = 0; CenterZ = 0; Scales = @([double]$Scale) }
    }
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runtime 'exporter-config.json') -Encoding utf8
}

function Find-CompletedSession($SessionsRoot, [datetime]$StartedAt, [double]$Scale) {
    $candidates = Get-ChildItem -LiteralPath $SessionsRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.CreationTime -ge $StartedAt.AddSeconds(-3) } |
        Sort-Object CreationTime -Descending
    foreach ($candidate in $candidates) {
        $manifestPath = Join-Path $candidate.FullName 'manifest.json'
        if (-not (Test-Path -LiteralPath $manifestPath)) { continue }
        try { $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json } catch { continue }
        if ($manifest.captureComplete -and $manifest.valid -and [Math]::Abs([double]$manifest.exportScale - $Scale) -lt 0.001) { return $candidate.FullName }
    }
    return $null
}

function Stop-ExistingCaptureHelpers([string]$HelperDll) {
    $escapedDll = [regex]::Escape($HelperDll)
    $matches = Get-CimInstance Win32_Process -Filter "Name = 'dotnet.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $escapedDll }
    foreach ($match in $matches) {
        Write-Host "Stopping existing DayZMapCapture helper process $($match.ProcessId)."
        Stop-Process -Id $match.ProcessId -Force -ErrorAction Stop
    }
}

function Resolve-ConfiguredPath([string]$Value, [string]$ConfigPath) {
    if ([System.IO.Path]::IsPathRooted($Value)) { return [System.IO.Path]::GetFullPath($Value) }
    return [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $ConfigPath) $Value))
}

function Assert-DayZDiagClosed([string]$DayZDirectory) {
    $expected = [System.IO.Path]::GetFullPath((Join-Path $DayZDirectory 'DayZDiag_x64.exe'))
    $running = Get-Process DayZDiag_x64 -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and [System.StringComparer]::OrdinalIgnoreCase.Equals($_.Path, $expected) }
    if ($running) { throw 'Close the running DayZDiag client before starting a new 2D export.' }
}

$validation = & (Join-Path $PSScriptRoot 'scripts\validate-config.ps1') -ConfigPath $ConfigPath -Mode 2d
if ($ValidateOnly) { Write-Host "2D configuration is valid for world '$($validation.worldName)'."; exit 0 }
Assert-DayZDiagClosed $validation.dayz

$python = if ($validation.config.paths.python) { [string]$validation.config.paths.python } else { 'python' }
if (-not (Get-Command $python -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath $python)) { throw "Python executable was not found: $python" }
$output2d = Join-Path $validation.output (Join-Path $validation.worldName '2d')
$previewOutput = Join-Path $output2d 'previews'
$touristOutput = Join-Path $validation.output (Join-Path $validation.worldName 'tourist')
$logs = Join-Path $validation.output (Join-Path $validation.worldName 'logs')
New-Item -ItemType Directory -Force -Path $output2d, $previewOutput, $logs | Out-Null
if ($validation.config.hillshade -and $validation.config.hillshade.enabled) { New-Item -ItemType Directory -Force -Path $touristOutput | Out-Null }

$generation = Join-Path $PSScriptRoot ('.runtime\public-config\' + $validation.worldName)
& (Join-Path $PSScriptRoot 'scripts\generate-public-cartography.ps1') -ConfigPath $validation.configPath -OutputDirectory $generation | Out-Host
$capabilities = Get-Content -LiteralPath (Join-Path $generation 'capabilities.json') -Raw | ConvertFrom-Json

$helperDll = Join-Path $PSScriptRoot 'capture-helper\bin\Release\net8.0-windows\DayZMapCapture.dll'
Stop-ExistingCaptureHelpers $helperDll
& dotnet build (Join-Path $PSScriptRoot 'capture-helper\DayZMapCapture.csproj') -c Release | Tee-Object -FilePath (Join-Path $logs 'helper-build.log')
if ($LASTEXITCODE -ne 0) { throw "Capture helper build failed with exit code $LASTEXITCODE" }
& (Join-Path $PSScriptRoot 'scripts\build.ps1') -CartographyStyle public-config -CartographyOverridePath $capabilities.cartographyOverridePath -LocationOverridePath $capabilities.locationOverridePath -RaGDayZToolsPath $validation.ragDayZTools -PythonPath $python | Tee-Object -FilePath (Join-Path $logs 'addon-build.log')
if ($LASTEXITCODE -ne 0) { throw "Exporter addon build failed with exit code $LASTEXITCODE" }

$sessionsRoot = Join-Path $validation.profiles 'DayZMapExporter\map-exports'
New-Item -ItemType Directory -Force -Path $sessionsRoot | Out-Null
$helper = Start-Process dotnet -ArgumentList @($helperDll, '--sessions-root', $sessionsRoot) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'capture-helper.log') -RedirectStandardError (Join-Path $logs 'capture-helper.error.log') -PassThru

$exports = @()
if ($validation.config.exports.overview.enabled) { $exports += [pscustomobject]@{ Name = 'overview'; Scale = [double]$validation.config.exports.overview.scale } }
if ($validation.config.exports.detail.enabled) { $exports += [pscustomobject]@{ Name = 'detail'; Scale = [double]$validation.config.exports.detail.scale } }
$package = Join-Path $PSScriptRoot 'build\@DayZMapExporter'
$mods = @()
if ($validation.terrainMod) { $mods += $validation.terrainMod }
$mods += @($validation.config.paths.additionalMods | ForEach-Object { if ($_){ Resolve-ConfiguredPath ([string]$_) $validation.configPath } })
$mods += $package
$finalExports = @()
$touristExports = @()
$dayz = $null
if ($validation.hillshadeWarning) { Write-Warning $validation.hillshadeWarning }
try {
    foreach ($export in $exports) {
        Write-ExporterConfig $validation $export.Scale
        $launchArgs = @('-mod=' + ($mods -join ';'), '-mission=' + $validation.mission, '-profiles=' + $validation.profiles, '-filePatching', '-window', '-nopause', '-dologs', '-scriptDebug=true')
        $startedAt = Get-Date
        $dayz = Start-Process -FilePath (Join-Path $validation.dayz 'DayZDiag_x64.exe') -WorkingDirectory $validation.dayz -ArgumentList $launchArgs -PassThru
        Write-Host "[$($export.Name)] In DayZ: enter the mission, press Ctrl+F8, then F8 once. Wait for completion."
        Read-Host "Press Enter here only after the automatic export has completed" | Out-Null
        $session = Find-CompletedSession $sessionsRoot $startedAt $export.Scale
        if (-not $session) { throw "No valid completed $($export.Name) session was found after this launch. Its output was not copied." }
        & $python (Join-Path $PSScriptRoot 'stitcher\stitch_map.py') $session | Tee-Object -FilePath (Join-Path $logs ($export.Name + '-stitch.log'))
        if ($LASTEXITCODE -ne 0) { throw "Stitch failed for $($export.Name)." }
        $master = Join-Path $session 'output\map_master.png'
        $preview = Join-Path $session 'output\map_preview.jpg'
        Copy-Item -LiteralPath $master -Destination (Join-Path $output2d ($export.Name + '.png')) -Force
        Copy-Item -LiteralPath $preview -Destination (Join-Path $previewOutput ($export.Name + '.jpg')) -Force
        $manifest = Get-Content -LiteralPath (Join-Path $session 'manifest.json') -Raw | ConvertFrom-Json
        $finalExports += [ordered]@{ name = $export.Name; scale = $export.Scale; sourceSession = $session; dimensions = @{ width = $manifest.stitch.width; height = $manifest.stitch.height }; metersPerPixel = $manifest.stitch.metersPerPixel; sha256 = (Get-FileHash -LiteralPath $master -Algorithm SHA256).Hash.ToLowerInvariant() }
        if ($validation.hillshadePath) {
            $hillshade = $validation.config.hillshade
            $touristMaster = Join-Path $touristOutput ($export.Name + '_hillshade.png')
            $touristManifest = Join-Path $touristOutput ($export.Name + '_hillshade.manifest.json')
            & $python (Join-Path $PSScriptRoot 'stitcher\apply_hillshade.py') --heightmap $validation.hillshadePath --master (Join-Path $output2d ($export.Name + '.png')) --output $touristMaster --manifest $touristManifest --world-size $validation.worldSize --sea-level $hillshade.seaLevel --opacity $hillshade.opacity --elevation $(if ($hillshade.elevation) { $hillshade.elevation } else { 40 }) --slope-start $(if ($hillshade.slopeStart) { $hillshade.slopeStart } else { 5 }) --slope-full $(if ($hillshade.slopeFull) { $hillshade.slopeFull } else { 30 }) 2>&1 | Tee-Object -FilePath (Join-Path $logs ($export.Name + '-hillshade.log'))
            if ($LASTEXITCODE -eq 0) { $touristExports += Get-Content -LiteralPath $touristManifest -Raw | ConvertFrom-Json }
            else { Write-Warning "Hillshade failed for $($export.Name); the clean 2D output was preserved." }
        }
        if (-not $dayz.HasExited) { Stop-Process -Id $dayz.Id -Force }
        $dayz = $null
    }
}
finally {
    if ($dayz -and -not $dayz.HasExited) { Stop-Process -Id $dayz.Id -Force }
    if (-not $helper.HasExited) { Stop-Process -Id $helper.Id -Force }
}
[ordered]@{ version = 1; world = $validation.worldName; worldSize = $validation.worldSize; cartography = $validation.config.cartography; satelliteMode = $validation.satmapMode; capabilities = $capabilities; exports = $finalExports } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $output2d 'manifest.json') -Encoding utf8
if ($validation.hillshadePath) { [ordered]@{ version = 1; world = $validation.worldName; exports = $touristExports } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $touristOutput 'manifest.json') -Encoding utf8 }
Write-Host "2D output written to $output2d"
