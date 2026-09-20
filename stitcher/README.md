# NoronhaMapExporter stitcher

The primary workflow is `.\setup.ps1` followed by `.\run-2d.ps1`. The notes
below document the stitcher and the manual capture fallback used for advanced
diagnostics.

This is the offline half of the exporter. It consumes the `manifest.json`
created by the DayZ exporter. In the normal workflow, the capture helper writes
the PNG files and ACKs automatically; screenshots placed manually in the
session's `captures/` directory remain a diagnostic fallback. The stitcher
does not capture DayZ and does not use image-feature matching.

## Manual capture fallback

1. Open the exporter with `Ctrl+F8` and wait for calibration.
2. Press `F6` to start the full grid. It calculates its columns and rows from
   the real `ScreenToMap` viewport; the current 1920×1080 calibration should
   be 3×5 (15 tiles), but this is intentionally not hardcoded.
3. Keep `F7` in CLEAN mode, wait for `CAPTURE READY`, take one unmodified full
   game screenshot, save it as the printed `map_xNN_zNN.png`, then press
   `N`. Use `B` to return to a tile. `P` reprints the active tile metadata.
4. When the last tile is confirmed, copy/rename the images into the printed
   session directory under `captures/`. The game wrote `manifest.json` there.

Screenshots must be the same pixel dimensions recorded for the MapWidget. Do
not crop, resize, include debug text, or overwrite an existing session.

## Stitch

From this folder:

```powershell
python -m unittest -v test_stitch_map.py
python .\stitch_map.py "<session-directory-printed-by-DayZ>"
```

The helper rejects incomplete captures, mismatched widget sizes, non-square
pixels, inconsistent Z orientation, missing grid cells, invalid coverage, and
uncovered output pixels. It uses real tile bounds to position screenshots,
then splits known adjacent overlaps at their midpoint. The configured world is cropped
only after the geometric canvas is complete.

Outputs:

- `output/map_master.png` — exact configured-world crop.
- `output/map_preview.jpg` — convenient reduced preview.
- `logs/stitch.log` — placement and crop evidence.
- `manifest.json` — updated with the output paths and scale evidence.
