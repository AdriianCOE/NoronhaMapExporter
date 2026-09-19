#!/usr/bin/env python3
"""Losslessly normalize a user-provided satellite source to an RGB PNG."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--world", required=True)
    parser.add_argument("--world-size", type=float, required=True)
    args = parser.parse_args()
    if args.world_size <= 0:
        raise ValueError("world size must be greater than zero")
    if not args.source.is_file():
        raise ValueError(f"satmap source was not found: {args.source}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(args.source) as source:
        source.load()
        width, height = source.size
        if width <= 0 or height <= 0:
            raise ValueError("satmap source has invalid dimensions")
        image = source.convert("RGB")
        image.save(args.output, "PNG", optimize=False)
        source_format = source.format
    manifest = {
        "version": 1,
        "world": args.world,
        "worldSize": args.world_size,
        "mode": "source",
        "source": str(args.source.resolve()),
        "sourceFormat": source_format,
        "orientation": "preserved from source; no crop, resize, recolor, or enhancement applied",
        "output": {
            "path": args.output.name,
            "format": "PNG/RGB/lossless",
            "width": width,
            "height": height,
            "sha256": sha256(args.output),
        },
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
