# Noronha Map Exporter stitcher

This is the offline half of the exporter. It consumes the `manifest.json`
created by the DayZ prototype and clean screenshots manually placed in the
session's `captures/` directory. It does not capture DayZ and it does not use
image-feature matching.

## Capture session

1. Open the exporter with `Ctrl+F8` and wait for calibration.
2. Press `F6` to start the full grid. It calculates its columns and rows from
   the real `ScreenToMap` viewport; the current 1920×1080 calibration should
   be 3×5 (15 tiles), but this is intentionally not hardcoded.
3. Keep `F7` in CLEAN mode, wait for `CAPTURE READY`, take one unmodified full
   game screenshot, save it as the printed `noronha_xNN_zNN.png`, then press
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
then splits known adjacent overlaps at their midpoint. `0..10240` is cropped
only after the geometric canvas is complete.

Outputs:

- `output/noronha_engine_master.png` — exact 0..10240 world crop.
- `output/noronha_engine_preview.jpg` — convenient reduced preview.
- `logs/stitch.log` — placement and crop evidence.
- `manifest.json` — updated with the output paths and scale evidence.
