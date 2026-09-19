# Satellite-layer runtime audit

## Decision

`SATELLITE_RENDER = SUPPORTED_WITH_LIMITATIONS` for the validated local Noronha MapWidget. The product supports `satmap.mode: "engine"` in `run-2d.ps1` as an aligned engine composite, while `satmap.mode: "source"` remains the standalone-satellite export path.

## Runtime evidence

Two fresh DayZDiag captures were made at the same detail-audit viewport (`X=7800`, `Z=7200`, scale `0.15`) after building isolated temporary controls:

| Check | Session | Result |
| --- | --- | --- |
| satellite forced | `2026-09-19_07-08-40_01` | terrain imagery visibly rendered below map layers |
| satellite isolated | `2026-09-19_07-11-28_01` | imagery remained visible; grid and location labels disappeared, while roads, building footprints, vegetation symbols, and some object icons remained |

The isolated capture proves imagery is an independent engine layer, not a palette side effect. It also establishes the practical limit: the tested map-control fields do not make a clean, standalone satellite raster on this build. A terrain must provide satellite data for engine mode to be useful.

## Implementation boundary

The generated public map control requests full satellite alpha across the export scale range only when `satmap.mode` is `engine`. It does not contain an external tile provider, scraper, or projection system. In engine mode, DayZ owns alignment between imagery and the remaining native vector layers.

Source mode accepts a supplied image and preserves it unchanged as a PNG. It records the declared world size, but does not pretend to derive georeferencing from pixels. Registration and overlay ownership stay with the downstream map application.

## Reference research and licensing

DayZ Editor was inspected only as a technical reference for configuration field names and possible MapWidget behaviour. No DayZ Editor files, functions, or classes were copied, ported, or included. This implementation was written independently against DayZ runtime behaviour and remains suitable for this repository's intended licensing boundary. The reference repository is [DayZ Editor](https://github.com/InclementDab/DayZ-Editor/blob/legacy/DayZEditor/Scripts/config.cpp), which is CC BY-NC-ND 4.0.
