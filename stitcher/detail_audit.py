#!/usr/bin/env python3
"""Build non-deceptive comparison artifacts for one automatic detail-audit session."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw


HEADER_HEIGHT = 26
BACKGROUND = (24, 24, 24)
HEADER_BACKGROUND = (48, 48, 48)
TEXT = (240, 240, 240)


def load_manifest(session: Path) -> dict:
    path = session / "manifest.json"
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("mode") != "detail-audit":
        raise ValueError(f"{path} is not a detail-audit manifest")
    if not manifest.get("captureComplete") or not manifest.get("valid"):
        raise ValueError("detail audit is incomplete or failed validation")
    return manifest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_and_tile(session: Path, tile: dict) -> tuple[Image.Image, Path]:
    path = session / "captures" / tile["filename"]
    if not path.is_file():
        raise ValueError(f"missing capture: {path}")
    expected = tile.get("png", {})
    actual_hash = sha256(path)
    if expected.get("sha256") != actual_hash:
        raise ValueError(f"SHA256 mismatch for {path.name}")
    with Image.open(path) as source:
        if source.format != "PNG" or source.mode != "RGB":
            raise ValueError(f"{path.name} must be an opaque RGB PNG, got {source.format}/{source.mode}")
        if source.size != (expected.get("width"), expected.get("height")):
            raise ValueError(f"dimension mismatch for {path.name}")
        return source.copy(), path


def add_header(canvas: Image.Image, x: int, y: int, width: int, text: str) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x, y, x + width - 1, y + HEADER_HEIGHT - 1), fill=HEADER_BACKGROUND)
    draw.text((x + 6, y + 6), text, fill=TEXT)


def native_comparison(items: list[tuple[dict, Image.Image]], destination: Path) -> None:
    width = sum(image.width for _, image in items)
    height = HEADER_HEIGHT + max(image.height for _, image in items)
    output = Image.new("RGB", (width, height), BACKGROUND)
    x = 0
    for tile, image in items:
        add_header(output, x, 0, image.width, f"scale {tile['getScale']:.2f} | native {image.width}x{image.height}")
        output.paste(image, (x, HEADER_HEIGHT))
        x += image.width
    output.save(destination, format="PNG", optimize=False)


def common_bounds(items: list[tuple[dict, Image.Image]]) -> dict[str, float]:
    return {
        "left": max(tile["bounds"]["left"] for tile, _ in items),
        "right": min(tile["bounds"]["right"] for tile, _ in items),
        "bottom": max(tile["bounds"]["bottom"] for tile, _ in items),
        "top": min(tile["bounds"]["top"] for tile, _ in items),
    }


def world_crop(tile: dict, image: Image.Image, bounds: dict[str, float]) -> Image.Image:
    tile_bounds = tile["bounds"]
    if bounds["left"] >= bounds["right"] or bounds["bottom"] >= bounds["top"]:
        raise ValueError("audit captures have no common world-space area")
    mpp = tile["metersPerPixel"]
    x0 = math.floor((bounds["left"] - tile_bounds["left"]) / mpp["x"])
    x1 = math.ceil((bounds["right"] - tile_bounds["left"]) / mpp["x"])
    if tile["zAxisDirection"] == "Z decreases from top to bottom":
        y0 = math.floor((tile_bounds["top"] - bounds["top"]) / mpp["z"])
        y1 = math.ceil((tile_bounds["top"] - bounds["bottom"]) / mpp["z"])
    elif tile["zAxisDirection"] == "Z increases from top to bottom":
        y0 = math.floor((bounds["bottom"] - tile_bounds["bottom"]) / mpp["z"])
        y1 = math.ceil((bounds["top"] - tile_bounds["bottom"]) / mpp["z"])
    else:
        raise ValueError(f"unsupported Z orientation: {tile['zAxisDirection']}")
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(image.width, x1), min(image.height, y1)
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"empty common crop for scale {tile['getScale']}")
    return image.crop((x0, y0, x1, y1))


def same_world_comparison(items: list[tuple[dict, Image.Image]], destination: Path) -> dict[str, float]:
    bounds = common_bounds(items)
    crops = [(tile, world_crop(tile, image, bounds)) for tile, image in items]
    width = max(image.width for _, image in crops)
    height = sum(HEADER_HEIGHT + image.height for _, image in crops)
    output = Image.new("RGB", (width, height), BACKGROUND)
    y = 0
    for tile, image in crops:
        add_header(output, 0, y, width, f"scale {tile['getScale']:.2f} | same-world crop | native {image.width}x{image.height}")
        output.paste(image, (0, y + HEADER_HEIGHT))
        y += HEADER_HEIGHT + image.height
    output.save(destination, format="PNG", optimize=False)
    return bounds


def tile_count(world_size: float, visible: float, step: float) -> int:
    if visible >= world_size:
        return 1
    return math.ceil((world_size - visible) / step) + 1


def estimate_cost(manifest: dict, items: list[tuple[dict, Image.Image]]) -> list[dict]:
    world = manifest["worldBounds"]
    world_width = world["right"] - world["left"]
    world_height = world["top"] - world["bottom"]
    overlap = manifest["overlapFraction"]
    estimates = []
    for tile, _ in items:
        width = tile["visibleWorldWidth"]
        height = tile["visibleWorldHeight"]
        step_x = width * (1 - overlap)
        step_z = height * (1 - overlap)
        columns = tile_count(world_width, width, step_x)
        rows = tile_count(world_height, height, step_z)
        mpp = tile["metersPerPixel"]
        covered_width = width + (columns - 1) * step_x
        covered_height = height + (rows - 1) * step_z
        estimates.append({
            "scale": tile["getScale"],
            "visibleWorldWidth": width,
            "visibleWorldHeight": height,
            "metersPerPixelX": mpp["x"],
            "metersPerPixelZ": mpp["z"],
            "stepX": step_x,
            "stepZ": step_z,
            "columns": columns,
            "rows": rows,
            "tiles": columns * rows,
            "estimatedMasterWidth": round(covered_width / mpp["x"]),
            "estimatedMasterHeight": round(covered_height / mpp["z"]),
        })
    return estimates


def write_report(output: Path, manifest: dict, common: dict[str, float], estimates: list[dict]) -> None:
    enhanced = dict(manifest)
    enhanced["detailAuditArtifacts"] = {
        "nativeComparison": "comparison_native.png",
        "sameWorldComparison": "comparison_same_world_area.png",
        "commonWorldBounds": common,
        "sameWorldComparisonResampling": "none; crops retain native source pixels",
    }
    enhanced["costEstimate"] = estimates
    (output / "manifest.json").write_text(json.dumps(enhanced, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True, help="completed map-exports detail-audit session")
    parser.add_argument("--output", type=Path, help="default: <session>/detail-audit")
    args = parser.parse_args()
    session = args.session.resolve()
    output = (args.output or session / "detail-audit").resolve()
    manifest = load_manifest(session)
    tiles = sorted(manifest["tiles"], key=lambda item: item["index"])
    if not tiles:
        raise ValueError("detail audit has no tiles")
    request_ids = [tile.get("requestId") for tile in tiles]
    if any(request_id is None for request_id in request_ids) or len(set(request_ids)) != len(request_ids):
        raise ValueError("detail audit request IDs are missing or duplicated")
    output.mkdir(parents=True, exist_ok=True)
    items = []
    for tile in tiles:
        image, source = image_and_tile(session, tile)
        shutil.copy2(source, output / source.name)
        items.append((tile, image))
    native_comparison(items, output / "comparison_native.png")
    common = same_world_comparison(items, output / "comparison_same_world_area.png")
    estimates = estimate_cost(manifest, items)
    write_report(output, manifest, common, estimates)
    print(f"Detail audit artifacts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
