# Offline mission

`dayzOffline.Noronha` is copied here as development mission source. It contains
the small configuration, economy, environment, and startup files needed by the
exporter smoke workflow.

The following local/generated items are deliberately excluded:

- `storage_-1/` — DayZ runtime persistence.
- `areaflags.map` — a 75 MB generated map artifact.

The mission's `config.cpp` currently requires `Noronha_Items`; configure that
dependency through `AdditionalModPaths` when the compatible terrain build
requires it. No Noronha terrain or item PBO is included in this repository.
