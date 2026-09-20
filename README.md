# NoronhaMapExporter

Export the native DayZ map as a high-resolution, lossless image.

![Full Fernando de Noronha export with hillshade](images/examples/noronha-master.jpg)

I built this while working on my Fernando de Noronha terrain. I spent far too
long looking for a reliable way to export the native DayZ map at high
resolution, so eventually I stopped looking and made one.

It solved my problem, so I cleaned it up for other terrain makers too. Despite
the name, NoronhaMapExporter is made for any compatible DayZ terrain.

## Get started

```powershell
.\setup.ps1
.\run-2d.ps1
```

Windows · DayZ · DayZ Tools · Python 3 · .NET 8 SDK

`setup.ps1` finds DayZ and DayZ Tools, lets you choose Chernarus, Livonia, or a
custom terrain, creates `config.json`, creates the offline exporter mission,
and checks the dependencies. `run-2d.ps1` builds the exporter addon, starts
DayZDiag, captures the map, and stitches the result.

When DayZDiag opens:

1. Enter the generated offline mission.
2. Press `Ctrl+F8`.
3. Press `F8` once.
4. Wait for the export to finish.

The script detects completion automatically.

## What it exports

- The native DayZ `MapWidget`
- High-resolution stitched PNGs for overview and detail views
- Optional hillshade and source satellite output

| Native DayZ MapWidget | Clean exported map |
| --- | --- |
| ![Native MapWidget with its normal grid](images/examples/raw-map.jpg) | ![Clean map export without the technical grid](images/examples/engine-clean.jpg) |

The full Fernando de Noronha output above was exported at `9600 × 9600` pixels
from 60 native captures, with hillshade applied separately after stitching.

## Custom terrains

`setup.ps1` is the recommended path. For manual setup or advanced changes, see
[`config.example.json`](config.example.json). A minimal custom-terrain setup
looks like this:

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

`world.name` is the DayZ world/config name, not the Steam Workshop display
name. `world.size` is the terrain width in metres, not pixels. For an installed
world, set `terrainMod` to `null`.

## Map compatibility

NoronhaMapExporter is designed to work with any DayZ world that exposes its
map through the native `MapWidget`.

Runtime tested with:

- Fernando de Noronha — custom terrain
- Chernarus — `ChernarusPlus`
- Livonia — `Enoch`

Other installed and custom worlds should use the same pipeline, though not
every terrain has been individually tested.

## Output

```text
output/<world>/2d/overview.png
output/<world>/2d/detail.png
output/<world>/tourist/
output/<world>/satmap/
```

The `tourist` folder is created when hillshade is enabled. The `satmap` folder
is created by the optional satellite export. A small manifest sits beside each
output for later reference.

## Optional: hillshade and satellite

Hillshade adds terrain relief to a separate copy of the clean 2D export; it
never replaces the original map. The same authoritative ASC can also provide a
soft coast-distance ocean gradient and a subtle slope mask for cliffs. The
recommended tourist preset is in [`config.example.json`](config.example.json):
25% luminance hillshade, slope weighting from 5° to 30°, a 12% cliff mask from
18° to 35°, and a restrained ocean gradient from the shore to open water.

The DayZ control already distinguishes native minor and main contour lines.
`cartography.contours.mainOpacity` only strengthens that native hierarchy; the
exporter does not draw image-derived replacement contours.

Satellite export is also separate and uses an explicit source raster. Neither
option is required for a normal 2D export.

## FAQ

**Can I export at a higher resolution?** Yes. Lower `MapWidget` scales produce
more captures and a larger final image. This is native engine rendering, not
artificial upscaling, and more pixels do not always reveal more DayZ map detail.

**Does it work on Linux?** The full capture workflow currently requires Windows
because it depends on DayZDiag, DayZ Tools, and the Windows capture helper.
Offline Python processing may work elsewhere; Wine and Proton are untested and
unsupported.

## Requirements

- DayZ
- DayZ Tools
- Python 3
- Pillow and NumPy
- .NET 8 SDK
- Windows

```powershell
python -m pip install -r .\stitcher\requirements.txt
```

For implementation details, see [Architecture](docs/ARCHITECTURE.md).

## License

MIT. See [LICENSE](LICENSE).
