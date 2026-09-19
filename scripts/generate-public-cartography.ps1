[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$ConfigPath,
    [Parameter(Mandatory)] [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'

function Read-Json([string]$Path) {
    try { return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json } catch { throw "Invalid JSON in ${Path}: $($_.Exception.Message)" }
}

function Get-Property($Object, [string]$Name, $Default = $null) {
    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

function To-Number([double]$Value) {
    return $Value.ToString('0.####', [System.Globalization.CultureInfo]::InvariantCulture)
}

function Parse-HexColor([string]$Value, [string]$Field) {
    if ($Value -notmatch '^#(?<rgb>[0-9A-Fa-f]{6})(?<alpha>[0-9A-Fa-f]{2})?$') { throw "$Field must be #RRGGBB or #RRGGBBAA." }
    $rgb = $Matches.rgb
    $alpha = if ($Matches.alpha) { [Convert]::ToInt32($Matches.alpha, 16) / 255.0 } else { 1.0 }
    return @(
        ([double]([Convert]::ToInt32($rgb.Substring(0, 2), 16)) / 255.0),
        ([double]([Convert]::ToInt32($rgb.Substring(2, 2), 16)) / 255.0),
        ([double]([Convert]::ToInt32($rgb.Substring(4, 2), 16)) / 255.0),
        $alpha
    )
}

function CppColor([string]$Value, [double]$Opacity, [string]$Field) {
    if ($Opacity -lt 0 -or $Opacity -gt 1) { throw "$Field opacity must be between 0 and 1." }
    $rgba = Parse-HexColor $Value $Field
    return '{' + ((To-Number $rgba[0]), (To-Number $rgba[1]), (To-Number $rgba[2]), (To-Number ($rgba[3] * $Opacity)) -join ', ') + '}'
}

function CppTransparent() { return '{0, 0, 0, 0}' }

if (-not (Test-Path -LiteralPath $ConfigPath)) { throw "Configuration not found: $ConfigPath" }
$config = Read-Json $ConfigPath
$cartography = Get-Property $config 'cartography'
if ($null -eq $cartography) { throw 'cartography is required.' }

$colors = Get-Property $cartography 'colors'
$background = Get-Property $colors 'background' '#FFFFFF'
$outside = Get-Property $colors 'outside' '#D7E8EF'
$sea = Get-Property $colors 'sea' '#D7E8EF'
$vegetation = Get-Property $cartography 'vegetation'
$contours = Get-Property $cartography 'contours'
$roads = Get-Property $cartography 'roads'
$tracks = Get-Property $cartography 'tracks'
$buildings = Get-Property $cartography 'buildings'
$vegetationEnabled = [bool](Get-Property $vegetation 'enabled' $true)
$contoursEnabled = [bool](Get-Property $contours 'enabled' $true)
$roadsEnabled = [bool](Get-Property $roads 'enabled' $true)
$tracksEnabled = [bool](Get-Property $tracks 'enabled' $true)
$buildingsEnabled = [bool](Get-Property $buildings 'enabled' $true)
$vegetationColor = Get-Property $vegetation 'color' '#94D96B'
$vegetationOpacity = [double](Get-Property $vegetation 'opacity' 0.75)
$contourColor = Get-Property $contours 'color' '#66513F'
$contourOpacity = [double](Get-Property $contours 'opacity' 0.65)
$mainContourOpacity = [double](Get-Property $contours 'mainOpacity' $contourOpacity)
$gridEnabled = [bool](Get-Property $cartography 'grid' $true)
$gridNumbersEnabled = [bool](Get-Property $cartography 'gridNumbers' $true)
$satmap = Get-Property $config 'satmap'
$satmapMode = [string](Get-Property $satmap 'mode' 'source')
if ($satmapMode -notin @('source', 'engine')) { throw "satmap.mode must be 'source' or 'engine'." }

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('class RscMapControlPublicConfig: MapDefaults')
$lines.Add('{')
if ($satmapMode -eq 'engine') {
    # Keep the terrain-provided satellite imagery visible throughout the export scale range.
    $lines.Add('    maxSatelliteAlpha = 1;')
    $lines.Add('    alphaFadeStartScale = 1;')
    $lines.Add('    alphaFadeEndScale = 1;')
}
$lines.Add("    colorBackground[] = $(CppColor $background 1 'cartography.colors.background');")
$lines.Add("    colorOutside[] = $(CppColor $outside 1 'cartography.colors.outside');")
$lines.Add("    colorSea[] = $(CppColor $sea 1 'cartography.colors.sea');")
$lines.Add("    colorGrid[] = $(if ($gridEnabled) { '{0.2, 0.2, 0.2, 0.25}' } else { CppTransparent });")
$lines.Add("    colorGridMap[] = $(if ($gridNumbersEnabled) { '{0.2, 0.2, 0.2, 0.75}' } else { CppTransparent });")
$lines.Add("    colorForest[] = $(if ($vegetationEnabled) { CppColor $vegetationColor $vegetationOpacity 'cartography.vegetation' } else { CppTransparent });")
$lines.Add("    colorForestBorder[] = $(if ($vegetationEnabled) { CppColor $vegetationColor ($vegetationOpacity * 0.8) 'cartography.vegetation' } else { CppTransparent });")
$lines.Add("    colorCountlines[] = $(if ($contoursEnabled) { CppColor $contourColor $contourOpacity 'cartography.contours' } else { CppTransparent });")
$lines.Add("    colorMainCountlines[] = $(if ($contoursEnabled) { CppColor $contourColor $mainContourOpacity 'cartography.contours' } else { CppTransparent });")
$lines.Add("    colorRoads[] = $(if ($roadsEnabled) { '{0.86, 0.78, 0.62, 0.80}' } else { CppTransparent });")
$lines.Add("    colorMainRoads[] = $(if ($roadsEnabled) { '{0.78, 0.64, 0.42, 0.90}' } else { CppTransparent });")
$lines.Add("    colorTracks[] = $(if ($tracksEnabled) { '{0.62, 0.53, 0.42, 0.52}' } else { CppTransparent });")
$lines.Add("    colorBuildings[] = $(if ($buildingsEnabled) { '{0.43, 0.43, 0.40, 0.90}' } else { CppTransparent });")
$lines.Add('};')

$locationLines = [System.Collections.Generic.List[string]]::new()
$disableLabels = -not [bool](Get-Property $cartography 'locationLabels' $true)
$disableIcons = -not [bool](Get-Property $cartography 'locationIcons' $true)
if ($disableLabels -or $disableIcons) {
    $locationLines.Add('class CfgLocationTypes')
    $locationLines.Add('{')
    if ($disableLabels) {
        foreach ($name in @('Name','Mount','Strategic','StrongpointArea','FlatArea','FlatAreaCity','FlatAreaCitySmall','CityCenter','Airport','NameMarine','NameCityCapital','NameCity','NameVillage','NameLocal','Capital','City','Village','Local','Marine')) {
            $locationLines.Add("    class $name { color[] = {0, 0, 0, 0}; textSize = 0; importance = 0; };")
        }
    }
    if ($disableIcons) {
        foreach ($name in @('Ruin','Camp','Hill','ViewPoint','RockArea','RailroadStation','IndustrialSite','LocalOffice','BorderCrossing','VegetationBroadleaf','VegetationFir','VegetationPalm','VegetationVineyard')) {
            $locationLines.Add("    class $name { texture = `"`"; color[] = {0, 0, 0, 0}; size = 0; textSize = 0; importance = 0; };")
        }
    }
    $locationLines.Add('};')
}

$warnings = @()
if ($cartography.PSObject.Properties['mapObjectIcons'] -and -not [bool]$cartography.mapObjectIcons) {
    $warnings += 'mapObjectIcons cannot be safely disabled in this DayZ build. The option was not applied.'
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$cartographyPath = Join-Path $OutputDirectory 'public-cartography.cpp'
$locationPath = Join-Path $OutputDirectory 'public-location-types.cpp'
[System.IO.File]::WriteAllText($cartographyPath, ($lines -join "`r`n") + "`r`n")
[System.IO.File]::WriteAllText($locationPath, ($locationLines -join "`r`n") + "`r`n")
@{ cartographyOverridePath = $cartographyPath; locationOverridePath = $locationPath; satelliteMode = $satmapMode; warnings = $warnings } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'capabilities.json') -Encoding utf8
foreach ($warning in $warnings) { Write-Warning $warning }
Write-Output (Join-Path $OutputDirectory 'capabilities.json')
