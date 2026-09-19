# DayZMapExporter

DayZMapExporter exports the native DayZ MapWidget as reproducible, lossless,
georeferenced 2D map images. It works with a compatible terrain mod and an
offline mission for that terrain.

## Quick start

1. Install DayZ, DayZ Tools, .NET 8 SDK, Python 3, Pillow, NumPy, and [RaG DayZ Tools](https://github.com/Tyson89/RaG-DayZ-Tools).

2. Create your local configuration:

   ```powershell
   Copy-Item .\config.example.json .\config.json
   ```

3. Edit `config.json`. The important fields are `paths.dayz`,
   `paths.dayzTools`, `paths.ragDayZTools`, `paths.terrainMod`, `world.name`,
   and `world.size`.

4. Create a minimal exporter mission:

   ```powershell
   .\scripts\create-mission.ps1 -ConfigPath .\config.json
   ```

   If the terrain needs its own mission or extra files, use the mission it
   distributes and set `paths.mission` to that folder instead.

5. Validate before opening DayZ:

   ```powershell
   .\run-2d.ps1 -ValidateOnly
   ```

6. Export:

   ```powershell
   .\run-2d.ps1
   ```

   Enter the offline mission when DayZDiag opens. Press `Ctrl+F8`, then `F8`
   once. Return to the console only after the automatic export completes.

Results are written under:

```text
output/<world>/2d/overview.png
output/<world>/2d/detail.png
output/<world>/2d/manifest.json
```

## What you need

DayZ, DayZ Tools, Python 3 with Pillow and NumPy, and .NET 8 are needed on the
machine that performs exports. RaG DayZ Tools is needed by the current command
because it rebuilds the small exporter addon before each run; it is not a
runtime dependency of a previously built addon.

`world.name` is the DayZ world/config name, not the Steam Workshop display
name. `world.size` is the terrain width in metres: for example, `8192`,
`10240`, `15360`, or `20480` describe metres, never pixels.

See [configuration](docs/CONFIGURATION.md) for every setting.

## Satellite and hillshade

`run-satmap.ps1` exports a standalone source raster when `satmap.mode` is
`source`. It is optional and does not block a 2D export. `satmap.mode: engine`
uses imagery exposed by the loaded terrain as part of the 2D MapWidget export;
it can retain native map layers.

Hillshade is optional. When enabled, provide the authoritative ASC heightmap
for the terrain. It creates a separate image in `output/<world>/tourist/` and
never overwrites the 2D master.

## Known limitations

- DayZ must remain visible, unminimized, and unobstructed during capture.
- Some native object icons can remain because this DayZ build does not safely
  expose their MapDefaults styling to an addon.
- The included mission template is deliberately minimal. Some custom terrains
  require additional mission files or mods.

## Example output

These are compact example viewports from a custom terrain, not terrain data or
full-resolution masters.

| Native MapWidget | Engine-clean topographic |
| --- | --- |
| ![Native MapWidget example](images/examples/raw-map.jpg) | ![Engine-clean example](images/examples/engine-clean.jpg) |

## License

DayZMapExporter source code and documentation are licensed under the [MIT License](LICENSE). DayZ, missions, terrain data, WRP data, captures, and other third-party assets are not included.

For implementation detail, see [architecture](docs/ARCHITECTURE.md) and [product capabilities](docs/PRODUCT_CAPABILITIES.md).
