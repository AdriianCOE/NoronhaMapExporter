# Architecture

```text
DayZ terrain
    ↓
MapWidget
    ↓  SetScale / SetMapPos
ScreenToMap at the four widget corners
    ↓
world-space bounds and capture manifest
    ↓
capture request / ACK (automatic) or manual full-frame screenshots
    ↓
Python geometric stitcher
    ↓
exact 10240 × 10240 m world crop
    ↓
engine master PNG
```

The DayZ addon owns viewport control and measurement. It waits for updates
after changing map position/scale, reads the widget's actual pixel rectangle,
and records corners, bounds, meters per pixel, and Z direction for each tile.

The stitcher owns only offline image composition. It validates the manifest,
places each screenshot from its recorded world bounds, crops known adjacent
overlaps at their geometric midpoint, and rejects any output crop with gaps.
It does not capture DayZ, call render APIs, or compare image features.

## Coordinate mapping

- World X is horizontal, east/west.
- World Z is vertical, north/south.
- Image X increases rightward; image Y increases downward.
- The Z-to-image-Y sign is derived from each tile's `topLeft` and
  `bottomLeft` corners. It is never assumed.

The active terrain extent comes from ignored profile configuration. The final
crop uses those configured limits only after the larger capture canvas is
complete. The validated Noronha extent was `X=0..10240`, `Z=0..10240` metres;
it is documentation only.
