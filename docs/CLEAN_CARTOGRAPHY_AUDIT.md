# Clean Cartography Style Audit

Status: completed on 2026-09-19. This is an isolated renderer-style audit,
not a full clean export. No terrain source, WRP, RAW master, or stitcher
geometry was changed.

## Scope and provenance

- World: `Noronha`, 10240 x 10240 m.
- Audit center: X=7800, Z=7200 (Vila dos Remedios / Vila do Trinta).
- Runtime capture: automatic `CAPTURE_READY -> helper PNG -> ACK` only.
- Capture frame: opaque RGB lossless PNG, 1920 x 1080.
- Detail preview: scale 0.15, 1.06667 m/px.
- Overview preview: scale 0.33, 2.34667 m/px.
- The ignored runtime package is `.runtime/clean-cartography-audit/`.

The local DayZ installation exposes `CfgConvert`, but its shipped PBO configs
do not expose the runtime-provided `MapDefaults` source text. Candidate
properties were therefore compiled with this PC's `CfgConvert` and tested one
at a time in this exact DayZ client. No property was adopted based solely on
an Arma-family configuration name.

## Candidate results

| Capture | Active candidate | Runtime result |
| --- | --- | --- |
| `clean_test_00_raw.png` | `Raw` | Control reference; grid, labels, POIs, vegetation and building footprints visible. |
| `clean_test_01_no_grid.png` | `NoGrid` | Effective: grid lines and grid numbers removed; building footprints retained. |
| `clean_test_02_no_labels.png` | `NoLabels` | No observable removal of native place labels in this DayZ build. |
| `clean_test_03_no_icons.png` | `NoIcons` | No observable removal of the remaining native POI symbols in this DayZ build. The first capture had a Steam overlay and was rejected; the recorded retry is clean. |
| `clean_test_04_reduced_vegetation.png` | `ReducedVegetation` | Effective: forest mass is materially lighter; buildings, roads and labels remain. |
| `clean_test_05_soft_contours.png` | `SoftContours` | Effective but deliberately subtle: contour lines are lighter without erasing terrain shape. |
| `clean_test_06_palette.png` | `Palette` | Effective restrained palette adjustment; building footprints remain opaque enough to inspect. |
| `clean_test_10_combined_v1.png` | `CombinedV1` | Selected V1: no grid, reduced vegetation, soft contours and restrained palette. Native labels/POIs remain because their tested candidates had no visible effect. |

`CombinedV1` is not presented as label-free or icon-free. Those renderer
features need a separately evidenced DayZ-specific control path before any
future clean master is made.

## Selected preview captures

Both selected previews came from automatic session `90919050621-2`, with
request IDs 1 then 2 and matching `OK` ACKs.

| Output | Scale | Bounds (X / Z) | SHA-256 |
| --- | --- | --- | --- |
| `clean_test_v1_detail_015.png` | 0.15 | 6776..8824 / 6624..7776 | `d1ca8e65a454fcbc1ebe9ed9a8e093553940988434c3ad7b69e3a94515275263` |
| `clean_test_v1_overview_033.png` | 0.33 | 5547.2..10052.8 / 5932.8..8467.2 | `389b90337b195ffa512e41af4a4f3ba6520b7be6a35597c1d6bba36ff2ba98d3` |

The audit package contains native-pixel comparison sheets only. It neither
resamples nor feature-matches its source PNGs.

## Immutable RAW check

The frozen RAW masters were SHA-256 verified before and after the audit:

- Overview: `0405202d8b3a344fefd216d394fff57cfb991993ad60cdca22ca1774fa1d570a`
- Detail: `5a36d88510af9bdd2703bd9858ad076d3e0c646fed6a3badefc62c8c20eb4c3e`

## Reproducing the selected renderer

`RscMapControl` is resolved while DayZ creates the `MapWidget`; a style change
therefore needs a new client launch. The source stays on `Raw`, while the
build stages the selected parent class without mutating source:

```powershell
.\scripts\build.ps1 -CartographyStyle combined-v1
```

The current development PBO was last built with `combined-v1`. A normal build
without the argument produces `Raw`. Future full clean masters are explicitly
out of scope for this audit.
