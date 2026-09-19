# Noronha Map Exporter capture helper

Windows/.NET 8 console helper for the file handshake used by the DayZ addon.
It polls each session under `--sessions-root` for `capture_request.json`.

```text
capture_request.json (DayZ) → client-area PNG → capture_ack.json (helper)
```

The request is authoritative for tile order, filename, map bounds, and widget
rectangle. The helper never derives sequence or tile identity. It locates a
`DayZDiag_x64.exe` or `DayZ_x64.exe` process, reads its HWND client rectangle,
converts its origin to screen coordinates, and captures only the requested
widget rectangle. The game window must be visible, not minimized, and not
covered by another window.

## Build and run

```powershell
dotnet build .\DayZMapCapture.csproj -c Release
dotnet run --project .\DayZMapCapture.csproj -c Release -- --self-test
dotnet run --project .\DayZMapCapture.csproj -c Release -- --sessions-root "C:\...\profiles\DayZMapExporter\map-exports"
```

PNGs are saved as `<session>/captures/<filename>`, with no scaling, JPEG, or
post-processing. The helper validates the capture dimensions, hashes the PNG
with SHA-256, and writes an `OK` ACK atomically. The ACK must match the
session ID, request ID, and filename before the addon advances.

Requests with absolute or traversal filenames are rejected. A repeated
`sessionId + requestId` reuses its ACK, including after a helper restart via a
per-request receipt. An existing PNG without that matching receipt is never
overwritten or silently adopted. Invalid dimensions, missing DayZ window,
out-of-client widget rectangles, malformed requests, and capture errors
produce no `OK` ACK.

`DayZMapExporter` in the profile path is a stable internal handshake folder;
the public addon and package are named `NoronhaMapExporter`.
