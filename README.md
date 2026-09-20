# NoronhaMapExporter

Export high-resolution native DayZ maps with lossless capture and geometric stitching.

I originally built NoronhaMapExporter while developing the Fernando de Noronha terrain for DayZ. I needed a reliable way to export the native in-game map at high resolution, so I built the tool I could not find. It is published because the same problem affects other terrain creators too: despite the name, NoronhaMapExporter is not specific to Noronha.

## Features

- Renders the native DayZ `MapWidget`, including terrain map data, roads, contours, vegetation, buildings, and location data exposed by the engine.
- Measures each widget viewport in world space and stitches captures from those recorded bounds rather than image-feature matching.
- Captures lossless PNGs through a local request/ACK helper and produces exact configured-world crops.
- Supports compatible custom terrains and locally detected installed DayZ worlds.
- Keeps satellite source export and hillshade separate from the native 2D master.

## Quick Start

```powershell
.\setup.ps1
.\run-2d.ps1
```

`setup.ps1` tries to find DayZ and DayZ Tools, asks for Chernarus, Livonia, or a custom terrain, writes the ignored local `config.json`, creates a minimal offline mission, and runs a preflight check. `run-2d.ps1` builds the addon, opens DayZDiag, and detects a completed capture manifest automatically.

During an export, enter the offline mission, press `Ctrl+F8`, then `F8`. There is no console Enter step.

Requirements: DayZ with `DayZDiag_x64.exe`, DayZ Tools, Python 3 with Pillow and NumPy, and the .NET 8 SDK. If Pillow or NumPy is missing, install them explicitly:

```powershell
python -m pip install -r .\stitcher\requirements.txt
```

## Configuration

For most custom terrains, edit only `paths.dayz`, `paths.dayzTools`, `paths.terrainMod`, `paths.mission`, `world.name`, and `world.size`. Start with `config.example.json`, then generate the matching mission:

```powershell
Copy-Item .\config.example.json .\config.json
.\scripts\create-mission.ps1 -ConfigPath .\config.json
.\setup.ps1 -Check
```

```json
{
  "paths": {
    "terrainMod": "D:/DayZMods/@MyTerrain",
    "mission": "./mission/dayzOffline.MyTerrain"
  },
  "world": {
    "name": "MyTerrain",
    "size": 10240
  }
}
```

Use `"terrainMod": null` (or `""`) for an installed world; no terrain mod is added to the launch command. `exports` controls overview/detail scales. `cartography` controls the generated public map presentation. `satmap` is needed only for `run-satmap.ps1`, and hillshade is disabled unless explicitly enabled with an authoritative ASC heightmap.

## Output

```text
output/<world>/2d/overview.png
output/<world>/2d/detail.png
output/<world>/2d/manifest.json
```

The manifest records the source session, scale, dimensions, metres per pixel, and hash. Local profiles, capture sessions, generated PBOs, screenshots, masters, and configuration stay out of Git.

## Resolution

Lower `MapWidget` scales cover fewer metres per capture, so the exporter takes more tiles and produces a larger raster. This is native engine rendering, not artificial upscaling; more pixels do not necessarily reveal more map detail.

## Satellite & Hillshade

`run-satmap.ps1` copies an explicit RGB source raster losslessly and records its dimensions and hash. It is optional and never blocks a 2D export.

Hillshade is optional post-processing. When enabled, it needs an authoritative ASC heightmap and writes a separate tourist image without replacing the clean native 2D master.

## Supported Worlds

| World | Config name | Current status | Notes |
| --- | --- | --- | --- |
| Fernando de Noronha | user supplied | tested | custom-terrain runtime smoke; 10240 m |
| Chernarus | `ChernarusPlus` | tested | 15360 m runtime smoke |
| Livonia | `Enoch` | tested | 12800 m runtime smoke |
| Other custom terrains | user supplied | compatible configuration | provide the terrain mod, mission, class name, and width |

Other installed worlds may work but are unverified.

## FAQ / Limitations

**Can I export at a higher resolution?** Yes. Lower `MapWidget` scales produce more captures and a larger raster, but more pixels do not necessarily expose additional engine detail.

**Does it work on Linux?** The complete capture workflow is currently Windows-only because it depends on DayZDiag, DayZ Tools, and the Windows capture helper. Python offline processing can be cross-platform, but Linux capture is not currently supported. Wine and Proton are untested and unsupported.

**Why is the map not a replacement for terrain source data?** The exporter records what DayZ renders at runtime. It does not regenerate WRP, terrain, satellite, or heightmap data.

For the coordinate and capture boundary, see [the architecture note](docs/ARCHITECTURE.md).

## License

MIT. See [LICENSE](LICENSE).
