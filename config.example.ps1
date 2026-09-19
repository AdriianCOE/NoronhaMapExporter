# Copy this file to config.local.ps1 and replace every placeholder.
# config.local.ps1 is intentionally ignored by Git.

$DayZPath = 'C:\Path\To\DayZ'
$DayZToolsPath = 'C:\Path\To\DayZ Tools'
$RaGDayZToolsPath = 'C:\Path\To\RaG-DayZ-Tools'
$PythonPath = 'python'
$NoronhaModPath = 'D:\DayZMods\@FernandoDeNoronha'

# Add compatible dependencies required by the chosen Noronha build here.
# Example: @('D:\DayZMods\@Noronha_Items')
$AdditionalModPaths = @()

# Keep runtime profiles separate from source and Git.
$ProfileDirectory = Join-Path $PSScriptRoot '.runtime\profiles'
