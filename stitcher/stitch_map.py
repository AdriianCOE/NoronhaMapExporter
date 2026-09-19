#!/usr/bin/env python3
"""Geometrically stitch a DayZMapExporter capture session.

This tool deliberately never searches image content for seams.  It places every
capture using the real MapWidget bounds in manifest.json and splits each known
overlap at its geometric midpoint.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
from typing import Any

from PIL import Image


WORLD_KEYS = ("left", "right", "bottom", "top")
EPSILON = 0.01


class StitchError(RuntimeError):
    """The capture session is incomplete or geometrically inconsistent."""


def round_half_up(value: float) -> int:
    """Stable world-to-pixel rounding. Positive coordinates are expected."""
    return int(math.floor(value + 0.5))


def require_number(mapping: dict[str, Any], key: str, label: str) -> float:
    try:
        return float(mapping[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise StitchError(f"{label}.{key} must be numeric") from exc


def configure_log(session: Path) -> logging.Logger:
    log_dir = session / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("dayz_map_stitcher")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_dir / "stitch.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def close_log(logger: logging.Logger) -> None:
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def load_manifest(session: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = session / "manifest.json"
    if not manifest_path.is_file():
        raise StitchError(f"Missing manifest: {manifest_path}")
    try:
        return manifest_path, json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StitchError(f"Invalid JSON in {manifest_path}: {exc}") from exc


def source_path(session: Path, filename: str) -> Path:
    requested = session / "captures" / filename
    if requested.is_file():
        return requested
    for extension in (".png", ".jpg", ".jpeg"):
        candidate = requested.with_suffix(extension)
        if candidate.is_file():
            return candidate
    raise StitchError(f"Missing screenshot for {filename}: expected {requested}")


def validate_session(session: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, float], float, float]:
    if manifest.get("captureComplete") is not True:
        raise StitchError("manifest.captureComplete is not true; finish every tile before stitching")

    bounds = manifest.get("worldBounds")
    if not isinstance(bounds, dict):
        raise StitchError("manifest.worldBounds is missing")
    world = {key: require_number(bounds, key, "worldBounds") for key in WORLD_KEYS}
    if world["left"] >= world["right"] or world["bottom"] >= world["top"]:
        raise StitchError("worldBounds are invalid")

    grid = manifest.get("grid")
    tiles = manifest.get("tiles")
    if not isinstance(grid, dict) or not isinstance(tiles, list):
        raise StitchError("manifest.grid or manifest.tiles is missing")
    columns = int(grid.get("columns", 0))
    rows = int(grid.get("rows", 0))
    total = int(grid.get("total", 0))
    if columns <= 0 or rows <= 0 or total != columns * rows or len(tiles) != total:
        raise StitchError("grid dimensions and captured tile count do not agree")

    seen: set[tuple[int, int]] = set()
    first_mpp_x: float | None = None
    first_mpp_z: float | None = None
    z_sign: int | None = None
    for tile in tiles:
        if not isinstance(tile, dict):
            raise StitchError("a tile entry is not an object")
        try:
            grid_x = int(tile["gridX"])
            grid_z = int(tile["gridZ"])
            filename = str(tile["filename"])
            tile_bounds = tile["bounds"]
            mpp = tile["metersPerPixel"]
            widget = tile["widget"]
            corners = tile["corners"]
        except (KeyError, TypeError, ValueError) as exc:
            raise StitchError(f"tile is missing required metadata: {tile}") from exc
        if not 0 <= grid_x < columns or not 0 <= grid_z < rows:
            raise StitchError(f"tile {filename} has an out-of-range grid coordinate")
        if (grid_x, grid_z) in seen:
            raise StitchError(f"duplicate grid tile x={grid_x}, z={grid_z}")
        seen.add((grid_x, grid_z))
        for key in WORLD_KEYS:
            require_number(tile_bounds, key, f"tile {filename}.bounds")
        if require_number(tile_bounds, "left", "bounds") >= require_number(tile_bounds, "right", "bounds"):
            raise StitchError(f"tile {filename} has invalid X bounds")
        if require_number(tile_bounds, "bottom", "bounds") >= require_number(tile_bounds, "top", "bounds"):
            raise StitchError(f"tile {filename} has invalid Z bounds")
        mpp_x = require_number(mpp, "x", f"tile {filename}.metersPerPixel")
        mpp_z = require_number(mpp, "z", f"tile {filename}.metersPerPixel")
        if mpp_x <= 0 or mpp_z <= 0 or abs(mpp_x - mpp_z) > EPSILON:
            raise StitchError(f"tile {filename} does not have square world pixels")
        if first_mpp_x is None:
            first_mpp_x, first_mpp_z = mpp_x, mpp_z
        elif abs(mpp_x - first_mpp_x) > EPSILON or abs(mpp_z - first_mpp_z) > EPSILON:
            raise StitchError(f"tile {filename} has a different meters-per-pixel value")
        top_left = corners.get("topLeft")
        bottom_left = corners.get("bottomLeft")
        if not isinstance(top_left, list) or not isinstance(bottom_left, list) or len(top_left) < 2 or len(bottom_left) < 2:
            raise StitchError(f"tile {filename} does not expose topLeft/bottomLeft corners")
        delta_z = float(bottom_left[1]) - float(top_left[1])
        if abs(delta_z) <= EPSILON:
            raise StitchError(f"tile {filename} has indeterminate screen Z orientation")
        tile_sign = 1 if delta_z > 0 else -1
        if z_sign is None:
            z_sign = tile_sign
        elif tile_sign != z_sign:
            raise StitchError("tiles disagree on the MapWidget Z orientation")
        width = require_number(widget, "width", f"tile {filename}.widget")
        height = require_number(widget, "height", f"tile {filename}.widget")
        if width <= 0 or height <= 0:
            raise StitchError(f"tile {filename} has invalid widget dimensions")
        image_path = source_path(session, filename)
        with Image.open(image_path) as image:
            if image.width != round_half_up(width) or image.height != round_half_up(height):
                raise StitchError(
                    f"tile {filename} is {image.width}x{image.height}, but MapWidget was {width}x{height}; "
                    "use a clean, uncropped game screenshot at the recorded resolution"
                )

    expected = {(x, z) for x in range(columns) for z in range(rows)}
    if seen != expected:
        raise StitchError(f"manifest grid is incomplete; missing={sorted(expected - seen)}")
    coverage_left = min(float(tile["bounds"]["left"]) for tile in tiles)
    coverage_right = max(float(tile["bounds"]["right"]) for tile in tiles)
    coverage_bottom = min(float(tile["bounds"]["bottom"]) for tile in tiles)
    coverage_top = max(float(tile["bounds"]["top"]) for tile in tiles)
    if (
        coverage_left > world["left"] + EPSILON
        or coverage_right < world["right"] - EPSILON
        or coverage_bottom > world["bottom"] + EPSILON
        or coverage_top < world["top"] - EPSILON
    ):
        raise StitchError(
            "tile bounds do not cover the requested world crop: "
            f"coverage={coverage_left},{coverage_right},{coverage_bottom},{coverage_top}"
        )
    return tiles, world, first_mpp_x, first_mpp_z


def add_pixel_rectangles(tiles: list[dict[str, Any]], mpp_x: float, mpp_z: float) -> tuple[float, float, int]:
    coverage_left = min(float(tile["bounds"]["left"]) for tile in tiles)
    coverage_right = max(float(tile["bounds"]["right"]) for tile in tiles)
    coverage_bottom = min(float(tile["bounds"]["bottom"]) for tile in tiles)
    coverage_top = max(float(tile["bounds"]["top"]) for tile in tiles)
    first = tiles[0]
    top_left_z = float(first["corners"]["topLeft"][1])
    bottom_left_z = float(first["corners"]["bottomLeft"][1])
    z_sign = 1 if bottom_left_z > top_left_z else -1
    visual_z_origin = coverage_bottom if z_sign == 1 else coverage_top

    for tile in tiles:
        bounds = tile["bounds"]
        left = float(bounds["left"])
        right = float(bounds["right"])
        top = float(bounds["top"])
        bottom = float(bounds["bottom"])
        tile["_x0"] = round_half_up((left - coverage_left) / mpp_x)
        tile["_x1"] = round_half_up((right - coverage_left) / mpp_x)
        if z_sign == 1:
            tile["_y0"] = round_half_up((bottom - visual_z_origin) / mpp_z)
            tile["_y1"] = round_half_up((top - visual_z_origin) / mpp_z)
        else:
            tile["_y0"] = round_half_up((visual_z_origin - top) / mpp_z)
            tile["_y1"] = round_half_up((visual_z_origin - bottom) / mpp_z)
        tile["_crop_x0"], tile["_crop_x1"] = tile["_x0"], tile["_x1"]
        tile["_crop_y0"], tile["_crop_y1"] = tile["_y0"], tile["_y1"]
    return coverage_left, visual_z_origin, z_sign


def midpoint_crop(tiles: list[dict[str, Any]], logger: logging.Logger) -> None:
    by_grid = {(int(tile["gridX"]), int(tile["gridZ"])): tile for tile in tiles}
    for tile in tiles:
        x, z = int(tile["gridX"]), int(tile["gridZ"])
        for neighbor in (by_grid.get((x - 1, z)), by_grid.get((x + 1, z)), by_grid.get((x, z - 1)), by_grid.get((x, z + 1))):
            if neighbor is None:
                continue
            if neighbor["_x0"] < tile["_x0"]:
                midpoint = round_half_up((neighbor["_x1"] + tile["_x0"]) / 2.0)
                tile["_crop_x0"] = max(tile["_crop_x0"], midpoint)
            elif neighbor["_x0"] > tile["_x0"]:
                midpoint = round_half_up((tile["_x1"] + neighbor["_x0"]) / 2.0)
                tile["_crop_x1"] = min(tile["_crop_x1"], midpoint)
            elif neighbor["_y0"] < tile["_y0"]:
                midpoint = round_half_up((neighbor["_y1"] + tile["_y0"]) / 2.0)
                tile["_crop_y0"] = max(tile["_crop_y0"], midpoint)
            elif neighbor["_y0"] > tile["_y0"]:
                midpoint = round_half_up((tile["_y1"] + neighbor["_y0"]) / 2.0)
                tile["_crop_y1"] = min(tile["_crop_y1"], midpoint)
        if tile["_crop_x0"] >= tile["_crop_x1"] or tile["_crop_y0"] >= tile["_crop_y1"]:
            raise StitchError(f"midpoint crop removed all pixels from {tile['filename']}")
        logger.info(
            "tile=%s grid=%s,%s source=[%s,%s,%s,%s] crop=[%s,%s,%s,%s]",
            tile["filename"], x, z, tile["_x0"], tile["_y0"], tile["_x1"], tile["_y1"],
            tile["_crop_x0"], tile["_crop_y0"], tile["_crop_x1"], tile["_crop_y1"],
        )


def crop_world(canvas: Image.Image, world: dict[str, float], coverage_left: float, visual_z_origin: float, z_sign: int, mpp_x: float, mpp_z: float) -> Image.Image:
    left = round_half_up((world["left"] - coverage_left) / mpp_x)
    right = round_half_up((world["right"] - coverage_left) / mpp_x)
    if z_sign == 1:
        top = round_half_up((world["bottom"] - visual_z_origin) / mpp_z)
        bottom = round_half_up((world["top"] - visual_z_origin) / mpp_z)
    else:
        top = round_half_up((visual_z_origin - world["top"]) / mpp_z)
        bottom = round_half_up((visual_z_origin - world["bottom"]) / mpp_z)
    if left < 0 or top < 0 or right > canvas.width or bottom > canvas.height or left >= right or top >= bottom:
        raise StitchError("exact world crop falls outside the captured coverage")
    return canvas.crop((left, top, right, bottom))


def stitch(session: Path) -> dict[str, Any]:
    session = session.resolve()
    logger = configure_log(session)
    manifest_path, manifest = load_manifest(session)
    tiles, world, mpp_x, mpp_z = validate_session(session, manifest)
    coverage_left, visual_z_origin, z_sign = add_pixel_rectangles(tiles, mpp_x, mpp_z)
    coverage_width = max(tile["_x1"] for tile in tiles)
    coverage_height = max(tile["_y1"] for tile in tiles)
    logger.info("session=%s mpp_x=%.8f mpp_z=%.8f z_sign=%s coverage_canvas=%sx%s", session, mpp_x, mpp_z, z_sign, coverage_width, coverage_height)
    midpoint_crop(tiles, logger)

    canvas = Image.new("RGBA", (coverage_width, coverage_height), (0, 0, 0, 0))
    for tile in tiles:
        source = source_path(session, str(tile["filename"]))
        source_x0 = tile["_crop_x0"] - tile["_x0"]
        source_x1 = tile["_crop_x1"] - tile["_x0"]
        source_y0 = tile["_crop_y0"] - tile["_y0"]
        source_y1 = tile["_crop_y1"] - tile["_y0"]
        with Image.open(source) as image:
            fragment = image.convert("RGBA").crop((source_x0, source_y0, source_x1, source_y1))
            canvas.alpha_composite(fragment, (tile["_crop_x0"], tile["_crop_y0"]))

    master = crop_world(canvas, world, coverage_left, visual_z_origin, z_sign, mpp_x, mpp_z)
    alpha_min, alpha_max = master.getchannel("A").getextrema()
    if alpha_min != 255 or alpha_max != 255:
        raise StitchError("geometric crop contains uncovered pixels; refusing to create a partial master")

    output = session / "output"
    output.mkdir(parents=True, exist_ok=True)
    master_path = output / "map_master.png"
    preview_path = output / "map_preview.jpg"
    master.convert("RGB").save(master_path, "PNG")
    preview = master.convert("RGB").copy()
    preview.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    preview.save(preview_path, "JPEG", quality=92, optimize=True)

    stitch_info = {
        "method": "bounds-geometric-midpoint-overlap-crop",
        "master": str(master_path),
        "preview": str(preview_path),
        "width": master.width,
        "height": master.height,
        "metersPerPixel": {"x": mpp_x, "z": mpp_z},
        "zScreenDirection": "increases-down" if z_sign == 1 else "decreases-down",
        "rounding": "round-half-up",
    }
    manifest["stitch"] = stitch_info
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("master=%s size=%sx%s preview=%s", master_path, master.width, master.height, preview_path)
    close_log(logger)
    return stitch_info


def main() -> int:
    parser = argparse.ArgumentParser(description="Geometrically stitch a DayZMapExporter session.")
    parser.add_argument("session", type=Path, help="Directory containing manifest.json and captures/")
    args = parser.parse_args()
    try:
        result = stitch(args.session)
    except StitchError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Created {result['master']} ({result['width']}x{result['height']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
