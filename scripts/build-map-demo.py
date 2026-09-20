"""Build a static Leaflet tile package from explicit local map masters.

The generated directory is intended for GitHub Pages deployment, not for the
source branch. The input masters remain read-only and are never copied whole
into the result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class LayerInput:
    identifier: str
    name: str
    source: Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_image(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"Map master was not found: {resolved}")
    return resolved


def max_zoom_for(width: int, height: int, tile_size: int) -> int:
    return max(0, math.ceil(math.log2(max(width, height) / tile_size)))


def save_tile(image: Image.Image, output: Path, is_full_resolution: bool, quality: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    options: dict[str, object] = {"format": "WEBP", "method": 6}
    if is_full_resolution:
        options["lossless"] = True
    else:
        options["quality"] = quality
    image.save(output, **options)


def build_layer(
    layer: LayerInput,
    tiles_root: Path,
    tile_size: int,
    quality: int,
    initial_bounds: tuple[int, int, int, int] | None,
    canvas_size: tuple[int, int] | None = None,
) -> dict[str, object]:
    source_hash = sha256(layer.source)
    revision = source_hash[:12]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(layer.source) as opened:
            source = opened.convert("RGB")
            source_width, source_height = source.size
            if canvas_size and source.size != canvas_size:
                source = source.resize(canvas_size, Image.Resampling.LANCZOS)
            width, height = source.size
            if initial_bounds:
                left, top, right, bottom = initial_bounds
                if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                    raise ValueError("--initial-bounds must stay inside each supplied master dimensions")
            max_zoom = max_zoom_for(width, height, tile_size)
            tile_count = 0

            for zoom in range(max_zoom + 1):
                divisor = 2 ** (max_zoom - zoom)
                level_size = (math.ceil(width / divisor), math.ceil(height / divisor))
                level = source if level_size == source.size else source.resize(level_size, Image.Resampling.LANCZOS)
                columns = math.ceil(level.width / tile_size)
                rows = math.ceil(level.height / tile_size)
                for column in range(columns):
                    for row in range(rows):
                        left = column * tile_size
                        top = row * tile_size
                        crop = level.crop((left, top, min(left + tile_size, level.width), min(top + tile_size, level.height)))
                        tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
                        tile.paste(crop, (0, 0))
                        save_tile(
                            tile,
                            tiles_root / layer.identifier / revision / str(zoom) / str(column) / f"{row}.webp",
                            zoom == max_zoom,
                            quality,
                        )
                        tile_count += 1

    result = {
        "id": layer.identifier,
        "name": layer.name,
        "source": str(layer.source),
        "sourceSha256": source_hash,
        "revision": revision,
        "sourceWidth": source_width,
        "sourceHeight": source_height,
        "width": width,
        "height": height,
        "tileSize": tile_size,
        "format": "webp",
        "maxZoom": max_zoom,
        "tiles": tile_count,
    }
    if initial_bounds:
        result["initialBounds"] = list(initial_bounds)
    return result


def write_map_config(output: Path, layers: list[dict[str, object]]) -> None:
    config = {
        "githubUrl": "https://github.com/AdriianCOE/NoronhaMapExporter",
        "workshopUrl": "https://steamcommunity.com/sharedfiles/filedetails/?id=3682451894",
        "viewerVersion": "v1.0.0",
        "defaultLayer": "tourist",
        "cloudsEnabled": True,
        "layers": [{key: value for key, value in layer.items() if key not in ("source", "sourceSha256", "tiles")} for layer in layers],
    }
    (output / "map-config.js").write_text("window.NORONHA_MAP = " + json.dumps(config, indent=2) + ";\n", encoding="utf-8")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tourist", type=Path, required=True, help="Tourist master PNG (required default layer).")
    parser.add_argument("--clean", type=Path, help="Optional clean MapWidget master PNG.")
    parser.add_argument("--satmap", type=Path, help="Optional source satellite map master.")
    parser.add_argument("--native", type=Path, help="Optional raw native MapWidget reference PNG.")
    parser.add_argument("--output", type=Path, default=Path(".runtime/web-map"), help="Generated Pages directory.")
    parser.add_argument("--clean-output", action="store_true", help="Remove the existing generated output before building.")
    parser.add_argument("--tile-size", type=int, choices=(256, 512), default=512)
    parser.add_argument("--quality", type=int, default=90, help="WebP quality for reduced zoom levels (1-100).")
    parser.add_argument(
        "--initial-bounds", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="Optional initial view in source pixels; tiles and pan bounds remain full-size.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    if not 1 <= args.quality <= 100:
        raise ValueError("--quality must be between 1 and 100")

    layers = [
        LayerInput("tourist", "Tourist", require_image(args.tourist)),
    ]
    if args.clean:
        layers.append(LayerInput("clean", "Clean", require_image(args.clean)))
    if args.satmap:
        layers.append(LayerInput("satmap", "SatMap", require_image(args.satmap)))
    if args.native:
        layers.append(LayerInput("native", "Native", require_image(args.native)))

    output = args.output.expanduser().resolve()
    source_root = Path(__file__).resolve().parents[1] / "web"
    if output == source_root:
        raise ValueError("--output must not replace the tracked web source directory")
    if output.exists():
        if not args.clean_output:
            raise ValueError(f"Output already exists: {output}. Pass --clean-output to replace generated files.")
        shutil.rmtree(output)
    shutil.copytree(source_root, output)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(layers[0].source) as primary:
            canvas_size = primary.size
    generated = [
        build_layer(
            layer,
            output / "tiles",
            args.tile_size,
            args.quality,
            tuple(args.initial_bounds) if args.initial_bounds else None,
            canvas_size,
        )
        for layer in layers
    ]
    write_map_config(output, generated)
    asset_bytes = sum(path.stat().st_size for path in (output / "tiles").rglob("*.webp"))
    manifest = {
        "format": "NoronhaMapExporter static map package v1",
        "layers": [{key: value for key, value in layer.items() if key != "source"} for layer in generated],
        "totalTiles": sum(int(layer["tiles"]) for layer in generated),
        "tileAssetBytes": asset_bytes,
    }
    (output / "map-package-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(2)
