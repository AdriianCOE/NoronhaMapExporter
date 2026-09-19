# Configuration

Copy `config.example.json` to `config.json`. The local `config.json` is ignored
by Git.

## Paths

| Field | Meaning |
| --- | --- |
| `paths.dayz` | Folder containing `DayZDiag_x64.exe`. |
| `paths.dayzTools` | Your DayZ Tools installation folder. |
| `paths.ragDayZTools` | RaG DayZ Tools checkout used to rebuild the addon. |
| `paths.python` | Python executable, normally `python`. |
| `paths.terrainMod` | Target terrain mod folder. |
| `paths.additionalMods` | Optional terrain dependencies. |
| `paths.mission` | Compatible offline mission folder. |
| `paths.profiles` | Local DayZ profile folder. Relative paths are resolved from `config.json`. |
| `paths.output` | Export destination. Relative paths are resolved from `config.json`. |

Create the included minimal mission with:

```powershell
.\scripts\create-mission.ps1 -ConfigPath .\config.json
```

## World and capture

`world.name` must be the DayZ world/config name. `world.size` is the world
width in metres. For example, `10240` means a `10240 m × 10240 m` world, not a
pixel dimension. Plausible examples include `8192`, `10240`, `15360`, and
`20480`; use the actual size of your terrain.

`capture.overlap` is the fractional overlap between adjacent captures.
`exports.overview` and `exports.detail` independently enable an export and
choose its MapWidget scale.

## Cartography

The example disables grid, location labels, and location icons while keeping
vegetation, contours, roads, tracks, and building footprints visible. Adjust
the corresponding `cartography` fields only when you want a different visual
result. Colours accept `#RRGGBB` or `#RRGGBBAA`.

## Satellite and hillshade

For a separate source satellite image, set `satmap.mode` to `source`, provide
`satmap.source`, and run `run-satmap.ps1`. Engine satellite mode is part of the
2D MapWidget export and can contain native layers.

Hillshade requires the authoritative terrain ASC. With `hillshade.enabled`
set to true, configure `hillshade.heightmap`; the derived result is written to
`output/<world>/tourist/` and the clean 2D master remains unchanged.
