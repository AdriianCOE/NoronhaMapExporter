# Local evidence: the DayZ installation on which this was validated contains
# these PBOs, whose converted configs declare ChernarusPlus and Enoch. The
# sizes are the corresponding world extents used by the DayZ map grid.
function Get-DayZMapExporterWorldPreset {
    param([Parameter(Mandatory)] [string]$DayZPath)

    $definitions = @(
        [pscustomobject]@{ Id = 'Chernarus'; DisplayName = 'Chernarus'; WorldName = 'ChernarusPlus'; WorldSize = 15360; Package = 'worlds_chernarusplus.pbo' },
        [pscustomobject]@{ Id = 'Livonia'; DisplayName = 'Livonia'; WorldName = 'Enoch'; WorldSize = 12800; Package = 'worlds_enoch.pbo' }
    )
    foreach ($preset in $definitions) {
        $preset | Add-Member -NotePropertyName Installed -NotePropertyValue (Test-Path -LiteralPath (Join-Path $DayZPath ('Addons\' + $preset.Package)) -PathType Leaf)
    }
    return $definitions
}
