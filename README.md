# DayZMapExporter

DayZMapExporter turns DayZ's native `MapWidget` into reproducible, georeferenced map exports. It captures tiles through the game client, acknowledges every lossless PNG, and stitches them from recorded world bounds. It works with custom terrains and with vanilla worlds when an offline mission is supplied.

The user-facing workflow has two commands:

```powershell
.\run-2d.ps1       # native 2D overview/detail exports
.\run-satmap.ps1   # optional source satellite layer
```

There are no public style presets. One `config.json` controls the engine properties that are safe to change: grid, location labels/icons, vegetation, contours, roads, tracks, buildings, and palette/opacity. The example is an engine-clean topographic configuration: clear of UI labels but intentionally rich in terrain character.

## Quick start

1. Install DayZ, DayZ Tools, .NET 8 SDK, Python 3, Pillow, and [RaG DayZ Tools](https://github.com/Tyson89/RaG-DayZ-Tools).
2. Clone this repository and create the only machine-local file:

   ```powershell
   Copy-Item .\config.example.json .\config.json
   ```

3. Edit the paths, world name/size, offline mission, desired export scales, and cartography properties. `config.json`, output, profiles, PBOs, and captures are ignored by Git.
4. Validate without opening DayZ:

   ```powershell
   .\run-2d.ps1 -ValidateOnly
   .\run-satmap.ps1 -ValidateOnly   # only when satmap.mode is "source"
   ```

5. Run `run-2d.ps1`. For each enabled export it builds the addon and helper, opens DayZDiag, and tells you when to enter the offline mission and press `Ctrl+F8`, then `F8` once. Do not press `F5`; it is a development smoke shortcut, not the product workflow.
6. When each automatic export completes, return to the console and press Enter. The command geometrically stitches the captures and writes:

   ```text
   output/<world>/2d/overview.png
   output/<world>/2d/detail.png
   output/<world>/2d/previews/*.jpg
   output/<world>/2d/manifest.json
   output/<world>/logs/
   ```

The manifest records full output paths, source sessions, scale, metres-per-pixel, hashes, and generated cartography capabilities.

## Cartography configuration

`config.example.json` is the authoritative template. The essential section is:

```json
"cartography": {
  "grid": false,
  "gridNumbers": false,
  "locationLabels": false,
  "locationIcons": false,
  "vegetation": { "enabled": true, "opacity": 0.75, "color": "#94D96B" },
  "contours": { "enabled": true, "opacity": 0.65, "color": "#66513F" },
  "roads": { "enabled": true },
  "tracks": { "enabled": true },
  "buildings": { "enabled": true }
}
```

`#RRGGBB` and `#RRGGBBAA` colours are supported. MapWidget properties are generated only in an ignored build staging directory, leaving source and terrain data untouched. `mapObjectIcons` is deliberately not a public control: this DayZ build does not safely allow an addon to override the remaining object icons. The run manifest reports that limitation if it is requested.

## Examples

| Native reference | Engine-clean topographic |
| --- | --- |
| ![Native MapWidget reference](images/examples/raw-map.jpg) | ![Engine-clean topographic viewport](images/examples/engine-clean.jpg) |

The examples are compact viewport JPEGs only. See [images/examples](images/examples/README.md) for their scope; full-world masters are not stored in the repository.

## Satellite layer

There are two explicit choices:

- `"satmap": { "mode": "engine" }` uses imagery provided by the loaded terrain in DayZ's MapWidget. It is captured with the 2D export and aligns automatically because the engine owns both layers. It is an engine-composite map: residual native layers may remain.
- `"satmap": { "mode": "source", "source": "..." }` is an independent source image. `run-satmap.ps1` copies it to a validated lossless PNG and records a hash and declared world extent. It does not invent projection, crop, scale, recolour, or alignment.

Use `source` for a standalone satellite raster. See [docs/SATELLITE_AUDIT.md](docs/SATELLITE_AUDIT.md) for runtime evidence and the integration boundary.

## Optional hillshade

Set `hillshade.enabled` only when you have the authoritative ASC used to make the terrain. The default `multidirectional-slope-weighted` setting uses terrain slope to keep flats nearly neutral and make steep relief readable; it writes separate `output/<world>/tourist/*_hillshade.png` files. The clean `2d/*.png` master is never overwritten. If no heightmap is configured, the 2D export continues and reports that hillshade was skipped.

## Guarantees and limits

- Capture uses the real DayZ client rectangle and produces RGB lossless PNGs.
- The helper is ACK/idempotency-aware: a completed request is not recaptured merely because the helper sees it again.
- Stitching uses recorded bounds and midpoint overlap crops only. It never uses feature matching.
- DayZ must remain visible, unminimized, and unobstructed during capture.
- Native object icons resolved through `MapDefaults` can remain baked into a map. This is a known engine limitation, not a silent failure.
- DayZMapExporter exports what the loaded terrain exposes. It does not build, change, or redistribute terrain/WRP data.

## Verification

```powershell
dotnet build .\capture-helper\DayZMapCapture.csproj -c Release
python -m unittest -v stitcher.test_stitch_map
.\run-2d.ps1 -ValidateOnly
```

The repository keeps only synthetic tests and small product examples. PBOs, profiles, real captures, masters, WRP data, and machine paths stay local.

More detail: [capabilities](docs/PRODUCT_CAPABILITIES.md), [architecture](docs/ARCHITECTURE.md), and [current validated baseline](docs/CURRENT_STATE.md).
