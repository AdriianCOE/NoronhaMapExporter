# Interactive map design QA

Result: passed

## Scope

Static public map viewer only: pan and zoom through Leaflet, a compact floating
toolbar, the Tourist/Clean/SatMap layer selector, and the GitHub link. No DayZ,
GIS, or export workflow was changed.

## Reference and evidence

- Selected direction: user-selected option 2 from the design exploration in
  this conversation (floating dark toolbar over an edge-to-edge map). The
  source concept was conversation-only and has no retained local file path.
- Desktop implementation screenshot:
  `.runtime/web-map-desktop-final.png` at 1440 x 1024.
- Mobile implementation screenshot:
  `.runtime/web-map-mobile-firefox.png` at 390 x 844.

## Review

- The map is the only main surface; the toolbar is compact and does not turn
  the viewer into a dashboard.
- The default Tourist layer shows the whole Noronha region, while Clean and
  SatMap remain selectable from the same control.
- Layer changes retain the current center and zoom. The initial overview is
  also the furthest zoom-out level, avoiding a stretched-looking extra zoom-out.
- Desktop controls stay in the lower-right corner. At 390 px, the toolbar
  switches to its compact layout without horizontal page scrolling.
- The GitHub link is visible but secondary to the map.
- Leaflet 1.9.4 is bundled under `web/vendor/leaflet/`; the public viewer makes
  no CDN request for its map runtime or stylesheet.

## Validation

- Desktop: Edge headless loaded the static page and tiles from the generated
  package; the initial view, visible island extremes, toolbar, selector, and
  zoom controls were reviewed.
- Mobile: Firefox headless confirmed the 390 px toolbar layout. Its immediate
  screenshot completes before Leaflet's external CDN has finished loading map
  tiles, so it is layout evidence rather than a tile-load timing measurement.
- Static checks: `node --check web/app.js`, `python -m py_compile
  scripts/build-map-demo.py scripts/test_build_map_demo.py`, and
  `python scripts/test_build_map_demo.py` passed.
- Package check: 1,500 expected tiles were generated with none missing. The
  original Tourist, Clean, and 10240² SatMap inputs retained their SHA-256
  hashes; only the generated SatMap tiles are normalized to the 9600² viewer
  canvas so all layers share one coordinate space.
