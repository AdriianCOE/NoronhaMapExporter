# DayZ Map Exporter

Development tools for exporting and stitching the native DayZ 2D map of a
custom terrain as a georeferenced raster. Fernando de Noronha is the validated
example terrain, not a hardcoded runtime requirement.

The addon controls DayZ's `MapWidget`, positions deterministic viewports with
`SetScale` and `SetMapPos`, records real world-space bounds with
`ScreenToMap`, and delegates image assembly to a Python stitcher. The stitcher
uses recorded bounds and midpoint overlap crops; it never performs feature
matching.

> Português: este é um ambiente de desenvolvimento privado para capturar o
> mapa 2D já renderizado pela engine do DayZ. O terrain compilado é uma
> dependência externa e não faz parte deste repositório.

## Repository layout

```text
addon/       DayZ development addon source
mission/     lightweight offline mission source
stitcher/    Pillow-based geometric stitcher and tests
scripts/     portable build and DayZDiag launcher scripts
docs/        architecture, workflow, and validated baseline
```

Generated PBOs, profiles, logs, capture sessions, screenshots, and masters
are ignored. The validated master is reproducible and is therefore not stored
in Git.

## Dependencies

- DayZ and `DayZDiag_x64.exe`
- [RaG DayZ Tools](https://github.com/Tyson89/RaG-DayZ-Tools) and Python 3
- a compatible Fernando de Noronha terrain build, provided separately
- any terrain dependencies required by that build (for example `Noronha_Items`)
- Python 3 and Pillow (`stitcher/requirements.txt`)

This repository does not contain DayZ files, DayZ Tools binaries, terrain PBOs,
item PBOs, VPP Admin Tools source, or capture images.

## Setup on a new PC

```powershell
git clone <your-private-repository-url> NoronhaMapExporter
cd NoronhaMapExporter

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\stitcher\requirements.txt

Copy-Item .\config.example.ps1 .\config.local.ps1
# Edit config.local.ps1 with this PC's DayZ, RaG DayZ Tools, terrain, and dependency paths.

.\scripts\build.ps1
.\scripts\run-offline.ps1
```

On first launch the launcher copies `exporter-config.example.json` to the
ignored profile path `DayZMapExporter/exporter-config.json`. Set its `WorldName`,
`WorldSize`, world bounds, `ExportScale`, overlap, output prefix, and auto
capture values for the selected terrain. No PC-specific path belongs in Git.

The launcher creates an ignored local profile directory and loads the terrain,
configured dependencies, the freshly built exporter, and
`mission/dayzOffline.Noronha`.

`scripts/build.ps1` uses RaG PBO Builder's CLI with preflight and produces
`build/@NoronhaMapExporter-dev/Addons/NoronhaMapExporter.pbo`. This script
intentionally disables Binarize, CfgConvert, and signing for the exporter
because it contains only script/layout/config assets and this PC's DayZ Tools
installation does not include those executables. Terrain builds remain a
separate workflow and need a complete DayZ Tools installation.

For the isolated cartography audit, the build can stage a named
`RscMapControl` candidate without mutating the source's `Raw` baseline:

```powershell
.\scripts\build.ps1 -CartographyStyle combined-v1
```

The available candidates are `raw`, `no-grid`, `no-labels`, `no-icons`,
`reduced-vegetation`, `soft-contours`, `palette`, and `combined-v1`. DayZ
binds this control when the MapWidget is created, so use a fresh client launch
between candidates. The validated results and limitations are in
[docs/CLEAN_CARTOGRAPHY_AUDIT.md](docs/CLEAN_CARTOGRAPHY_AUDIT.md).

## Automatic capture and stitch

The Windows helper removes the screenshot/rename/next-tile loop:

```text
DayZ MapWidget → capture_request.json → Windows helper → PNG → capture_ack.json → next tile
```

Build and start it before beginning an automatic export:

```powershell
dotnet build .\capture-helper\DayZMapCapture.csproj -c Release
dotnet run --project .\capture-helper\DayZMapCapture.csproj -c Release -- --sessions-root "<ProfileDirectory>\DayZMapExporter\map-exports"
```

It requires .NET 8 SDK or later and Windows. It finds `DayZDiag_x64.exe` or
`DayZ_x64.exe`, gets its real client rectangle with Win32, crops the actual
MapWidget rectangle from that client area, and writes lossless PNGs to the
active session's `captures/` folder. DayZ must remain visible, unminimized,
and unobstructed during capture.

`F8` starts AUTO EXPORT; `F5` runs the mandatory 2×2 AUTO SMOKE; `F9` retries
only a failed/timeout tile; `F10` aborts without advancing. AUTO forces CLEAN
and waits for stabilized position, scale, viewport bounds, and square pixels.
It only advances when session ID, request ID, filename, dimensions, and an
`OK` ACK with SHA-256 match. Existing valid captures are acknowledged
idempotently; unsafe filenames and dimension mismatches are rejected.

The helper writes ACKs with temp-and-replace. The addon writes a complete JSON
request in one operation; the helper treats parse/IO failures as not-ready and
retries, so it never acts on a partial request.

## Detail Scale Audit

`F4` runs the isolated automatic Detail Scale Audit. Configure `DetailAudit`
in the ignored profile `exporter-config.json`; its center is world-space and
its scales are tried in the stated order. Each capture remains at the same
world-space center, while `ScreenToMap` records the actual bounds and MPP for
that scale. The committed example is disabled so it cannot start accidentally.

For Noronha the local audit configuration uses `X=7800, Z=7200`, covering the
Vila dos Remédios / Vila do Trinta cluster identified in the terrain's
keypoints source. Once the five automatic ACKs complete, build the review
artifacts without feature matching or resampling:

```powershell
python .\stitcher\detail_audit.py --session "<session-directory>"
```

It writes `<session-directory>\detail-audit\`: verified original RGB PNGs,
native-pixel and same-world geometric comparisons, and an enriched manifest
with measured MPP, overlap-derived grid, screenshot count, and estimated
master dimensions for each candidate scale.

## Freeze a dual-scale RAW reference

After a completed automatic full-world session has passed the geometric
stitcher, preserve it outside Git with its WRP provenance. This refuses to
overwrite an existing reference directory:

```powershell
python .\stitcher\freeze_raw_master.py freeze `
  --session "<completed-session>" `
  --reference-root ".\.runtime\reference-exports" `
  --wrp-sha256 "<binarized-wrp-sha256>" `
  --name overview `
  --world-size 10240
```

Freeze the detail session in the same way with `--name detail`, then create
the immutable `masters.json` and a native-pixel same-world comparison:

```powershell
python .\stitcher\freeze_raw_master.py index --reference-root .\.runtime\reference-exports --wrp-sha256 "<wrp-sha256>"
python .\stitcher\freeze_raw_master.py compare --reference-root .\.runtime\reference-exports --wrp-sha256 "<wrp-sha256>" --bounds 7117.33 8482.67 6816 7584
```

## Manual capture and stitch

1. In DayZDiag, press `Ctrl+F8` and wait for calibration.
2. Press `F6` to begin the full export.
3. Use CLEAN mode (`F7`) and wait for `CAPTURE READY`.
4. Save each full, uncropped screenshot with the filename printed by the addon.
5. Press `N` only after saving that screenshot. `B` revisits a tile; `P`
   prints current metadata; `R` resets manual inspection; `Esc` closes.
6. Put the requested images in the session's `captures/` directory.
7. Stitch the session:

```powershell
python .\stitcher\stitch_map.py "<session-directory>"
```

The output is `output/noronha_engine_master.png`, plus a preview and
`logs/stitch.log`. See [EXPORT_WORKFLOW.md](docs/EXPORT_WORKFLOW.md) for the
complete sequence.

## Tests

```powershell
python -m unittest -v stitcher.test_stitch_map
```

The tests use synthetic small images only. They do not include real captures.

## Status

The complete runtime capture and geometric stitch pipeline has been validated
once at 1920×1080. See [CURRENT_STATE.md](docs/CURRENT_STATE.md). Values in
that document are a baseline; the addon recalculates the viewport and grid
from `ScreenToMap` for each session.

See [LICENSE-TODO.md](LICENSE-TODO.md) before redistributing the repository.
