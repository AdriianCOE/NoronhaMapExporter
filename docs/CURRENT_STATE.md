# Current state

## Baseline

Status: automatic lossless capture validated.

The interactive 2×2 automatic smoke completed in one session with request IDs
1 through 4, matching `OK` ACKs, four unique 1920×1080 RGB PNGs, and a
successful geometric stitch. The helper is idempotent: reprocessing a request
reuses its receipt without recapturing or advancing the exporter. Runtime
sessions, captures, hashes, and local launcher paths remain outside Git.

## Next recorded experiment

`Detail Scale Audit`: capture the same location at multiple configured
`MapWidget.SetScale` values to determine when buildings and other additional
details appear. It is deliberately not part of this baseline.

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
