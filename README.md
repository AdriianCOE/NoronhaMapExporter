# Noronha Map Exporter

Development tools for exporting and stitching the native DayZ 2D map of the
Fernando de Noronha custom terrain as a georeferenced raster.

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
- DayZ Tools (`AddonBuilder` and `CfgConvert`)
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
# Edit config.local.ps1 with this PC's DayZ, DayZ Tools, terrain, and dependency paths.

.\scripts\build.ps1
.\scripts\run-offline.ps1
```

The launcher creates an ignored local profile directory and loads the terrain,
configured dependencies, the freshly built exporter, and
`mission/dayzOffline.Noronha`.

## Capture and stitch

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
