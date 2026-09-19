# Offline mission

DayZMapExporter does not distribute DayZ missions, economy files, map groups,
terrain data, or runtime persistence. Configure the absolute path to a
compatible offline mission in `config.json` under `paths.mission`.

The mission must load the target terrain and any terrain-required dependencies.
Keep its `storage_-1/`, generated map artifacts, logs, and other runtime state
outside this repository.
