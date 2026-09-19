# Export workflow

## Build and launch

1. Create `config.local.ps1` from `config.example.ps1` and set paths.
2. Run `./scripts/build.ps1`.
3. Run `./scripts/run-offline.ps1`.
4. Verify that the offline Noronha mission creates/selects the local player.

## In-game controls

| Key | Action |
| --- | --- |
| `Ctrl+F8` | Open or close the exporter |
| `F6` | Start a new full-export session |
| `F8` | Start automatic export (helper required) |
| `F5` | Run automatic 2×2 smoke test |
| `F9` | Retry the failed/timeout automatic tile |
| `F10` | Abort automatic export without advancing |
| `N` | Confirm the current screenshot and advance |
| `B` | Return to the previous full-export tile |
| `F7` | Toggle DEBUG/CLEAN overlay |
| `P` | Print current bounds and expected filename |
| Arrow keys | Inspect adjacent tiles outside full-export mode |
| `R` | Return to tile `0,0` outside full-export mode |
| `Esc` | Close the exporter |

## Capture

1. Open with `Ctrl+F8`; wait for calibration.
2. Press `F6`. The addon measures the viewport and computes the grid.
3. Keep CLEAN mode active. DEBUG may be used to read `CAPTURE READY`, then
   toggle back to CLEAN before taking the image.
4. Capture a full unmodified game frame with the exact filename printed by the
   addon. Do not crop or resize it.
5. Press `N` to record that tile and move to the next one.
6. After the final `N`, find the session's `manifest.json` in the configured
   DayZ profile directory and copy all requested images to `captures/`.

## Automatic capture

Start `capture-helper` with the profile's `DayZMapExporter/map-exports`
directory, then press `F5` for the initial 2×2 smoke test. After four unique
PNGs and matching ACKs, use `F8` for the full world. The manifest records the
four smoke bounds and can be stitched normally. Automatic mode forces CLEAN,
waits for stabilization, and does not advance on a timeout or error.

For failure, use `F9` to send a new request for the same stable tile, use
`F10` to abort, or return to the preserved manual `F6`/screenshot/`N` flow.

## Stitch

```powershell
python .\stitcher\stitch_map.py "<session-directory>"
```

The helper checks complete grid coverage, image/widget dimensions, world pixel
scale, and Z orientation. It writes the exact world crop to
`output/noronha_engine_master.png`, plus a preview and `logs/stitch.log`.
