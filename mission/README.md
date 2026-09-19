# Export mission

NoronhaMapExporter needs an offline mission for the target world. Create the
included minimal exporter mission with:

```powershell
.\scripts\create-mission.ps1 -ConfigPath .\config.json
```

For `world.name = "MyTerrain"`, this creates `mission/dayzOffline.MyTerrain`.

The template contains only project-authored startup source. Some custom
terrains require additional mission files or mods; use the terrain-provided
mission when required.
