# Current state

## Baseline

Status: automatic lossless capture validated.

The interactive 2×2 automatic smoke completed in one session with request IDs
1 through 4, matching `OK` ACKs, four unique 1920×1080 RGB PNGs, and a
successful geometric stitch. The helper is idempotent: reprocessing a request
reuses its receipt without recapturing or advancing the exporter. Runtime
sessions, captures, hashes, and local launcher paths remain outside Git.

## Detail Scale Audit (2026-09-19)

Status: completed in an isolated automatic session at `X=7800, Z=7200`, the
Vila dos Remédios / Vila do Trinta cluster. All five requested scales completed
with matching `OK` ACKs and unique request IDs (`1` through `5`), producing
opaque 1920×1080 RGB PNGs. The review utility makes native-pixel and
same-world geometric comparisons without resampling or feature matching.

The measured candidates and full-world cost estimates are: `0.33` = 15 tiles
at 2.34667 m/px; `0.25` = 24 at 1.77778 m/px; `0.20` = 40 at 1.42222 m/px;
`0.15` = 60 at 1.06667 m/px; `0.10` = 135 at 0.711111 m/px. The audit is a
decision aid, not a new full-world export or a cartographic style change.

## Dual RAW masters (2026-09-19)

Status: validated and frozen outside Git under an immutable WRP-hash directory.

- [x] deterministic MapWidget export
- [x] geometric stitching
- [x] automatic lossless capture
- [x] Detail Scale Audit
- [x] overview raw master
- [x] detail raw master

For the current Noronha WRP (`6d3868ce714052decccac3a95008a527aa4b65bc062b1e45317fc32b548c5ad5`),
the overview reference is scale `0.33`, `3 x 5`, 15 captures, 4364 x 4364
pixels at 2.34667 m/px. The detail reference is scale `0.15`, `6 x 10`, 60
captures, 9600 x 9600 pixels at 1.06667 m/px. Both use only automatic opaque
RGB PNG capture and geometric world-bounds stitching.

Scale 0.33 is the general/low-zoom cartographic reference. Scale 0.15 is the
current high-detail Noronha raster baseline, preserving building footprints
and other features that lower scales do not render as clearly. This is a
terrain-specific decision based on the audit, not a universal scale rule.

`stitcher/freeze_raw_master.py` copies a validated session into the ignored
reference store, records terrain/renderer/capture provenance, refuses to
overwrite a reference, writes `masters.json`, and creates same-world native
comparison crops. It never changes map styling or uses feature matching.

## Clean Cartography Style Audit (2026-09-19)

Status: completed as isolated automatic captures at `X=7800, Z=7200`; no
full-world clean master was generated. The selected `CombinedV1` renderer
removes the grid, reduces vegetation, softens contours and uses a restrained
palette while preserving building footprints at scale `0.15`. Its `0.33`
preview remains appropriate for overview use.

The exact client accepted and visibly applied the grid, vegetation, contour
and palette candidates. The tested native label and POI candidate fields did
not visibly remove those features, so V1 intentionally keeps them rather
than claiming a false clean result. The ignored runtime package contains all
native PNGs, `comparison_all.png`, `raw_vs_clean_v1.png`, and `audit.json`.
See [CLEAN_CARTOGRAPHY_AUDIT.md](CLEAN_CARTOGRAPHY_AUDIT.md) for hashes,
request IDs, bounds, and the reproducible build command.

## Location / Map-Icon Follow-up (2026-09-19)

Status: completed investigation; `CombinedV2` intentionally not created.

The exact client accepted isolated `CfgLocationTypes` overrides for place
names and `NameIcon` descendants. Both were automatically captured at the
urban audit center, with matching ACKs and preserved roads/building
footprints. Map-object icon classes do exist in `MapDefaults`, but their
effective `icon` paths cannot be safely overridden by this addon: derived
`RscMapControl` children are ignored, reopening `MapDefaults` is a DayZ
compile error, and the explicit inherited-child syntax fails this PC's
`CfgConvert`. The active development build was restored to `CombinedV1` and
passes `CfgConvert`; no V2 preview, clean master, WRP, terrain, or RAW master
was changed.

| Item | Validated baseline |
| --- | --- |
| Runtime | DayZDiag with `dayzOffline.Noronha` |
| World | 10240 × 10240 m |
| Capture resolution | 1920 × 1080 px |
| Measured viewport | about 4505.6 × 2534.4 m |
| Overlap | 10% |
| Full grid | 3 × 5 / 15 captures |
| Meters per pixel | about 2.34667 m/px on both axes |
| Master | 4364 × 4364 px |
| Stitching | geometric from recorded world bounds |
| Feature matching | not used |
| Gaps | none in the validated export |

These are baseline observations, not hardcoded requirements. The addon derives
viewport size, step, grid count, coordinate direction, and per-tile bounds
from `ScreenToMap` at runtime.

## Confirmed corrections

- A custom `MapWidget` initially rendered transparent; the standalone control
  needs the `RscMapControl` configuration inheriting `MapDefaults`.
- Bounds must be read after the widget receives update frames following
  `SetScale` or `SetMapPos`.
- Bounds must use the real pixel rectangle of the widget, not presumed screen
  dimensions.
- Revisited tiles log bounds deltas to verify repeatability.
- Coverage checks allow a small epsilon because DayZ can return millimetre
  floating-point offsets at a world edge.
- The stitcher uses recorded world bounds and overlap midpoints, never visual
  feature matching.
- The ACK schema uses the helper's lower-camel-case JSON field names; the
  addon removes the consumed ACK before publishing the next request.
- The helper writes opaque RGB PNGs so geometric compositing never receives
  transparent screen-capture pixels.

## Deliberate exclusions

The validated master, its 15 screenshots, full export sessions, profiles,
runtime logs, generated PBOs, and terrain PBOs are reproducible or external
artifacts. They remain outside Git. Their absence does not invalidate the
source/test baseline documented here.
