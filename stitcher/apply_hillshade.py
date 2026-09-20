"""Create a clean tourist-map derivative from a stitched native 2D master.

The input master and ASC are read-only. Composition order is native base,
ocean, slope-weighted luminance hillshade, slope mask, then coast effects.
Every effect is optional and recorded in the output manifest.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import warnings
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

try:
    from stitcher.hillshade_audit import (
        HillshadeError,
        _filled_elevation,
        blend_luminance,
        multidirectional_hillshade,
        parse_asc,
        resample_world_array,
        sha256,
        slope_weight_from_degrees,
        valid_land_mask,
        validate_extent,
    )
except ModuleNotFoundError:
    from hillshade_audit import (
        HillshadeError,
        _filled_elevation,
        blend_luminance,
        multidirectional_hillshade,
        parse_asc,
        resample_world_array,
        sha256,
        slope_weight_from_degrees,
        valid_land_mask,
        validate_extent,
    )


COMPOSITION_ORDER = [
    "native-2d-master",
    "ocean-fill",
    "slope-weighted-luminance-hillshade",
    "slope-cliff-mask",
    "coast-halo",
    "coast-stroke",
]


def _option(args: argparse.Namespace, name: str, default: object) -> object:
    """Keep direct callers from older releases compatible with new options."""
    return getattr(args, name, default)


def parse_hex_color(value: str, label: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise HillshadeError(f"{label} must be a #RRGGBB color")
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("true", "1", "yes", "on"):
        return True
    if normalized in ("false", "0", "no", "off"):
        return False
    raise argparse.ArgumentTypeError("must be true or false")


def tint(base: np.ndarray, color: tuple[int, int, int], alpha: np.ndarray) -> np.ndarray:
    """Apply a bounded translucent color layer without multiply darkening."""
    if base.shape[:2] != alpha.shape:
        raise HillshadeError("color layer dimensions do not match the master")
    amount = np.clip(alpha, 0.0, 1.0).astype(np.float32, copy=False)
    overlay = np.asarray(color, dtype=np.float32)
    result = base.astype(np.float32) * (1.0 - amount[:, :, None]) + overlay * amount[:, :, None]
    return np.clip(result, 0, 255).astype(np.uint8)


def coast_layers(land: np.ndarray, halo_width: int, stroke_width: int) -> tuple[np.ndarray, np.ndarray]:
    """Return subtle ocean-side halo and two-sided shoreline masks in pixels."""
    if halo_width < 0 or stroke_width < 0:
        raise HillshadeError("coast widths must not be negative")
    binary = land >= 0.5
    source = Image.fromarray((binary.astype(np.uint8) * 255), "L")

    def expand(radius: int) -> np.ndarray:
        if radius == 0:
            return binary
        return np.asarray(source.filter(ImageFilter.MaxFilter(radius * 2 + 1))) >= 128

    def contract(radius: int) -> np.ndarray:
        if radius == 0:
            return binary
        return np.asarray(source.filter(ImageFilter.MinFilter(radius * 2 + 1))) >= 128

    halo = np.zeros(binary.shape, dtype=np.float32)
    if halo_width:
        # Two bands are visually soft enough at tourist-map scale and avoid a
        # full dilation pass per pixel of halo width on large masters.
        outer = expand(halo_width) & ~binary
        halo[outer] = 0.10
        inner = expand(min(2, halo_width)) & ~binary
        halo[inner] = 0.25

    stroke = np.zeros(binary.shape, dtype=np.float32)
    if stroke_width:
        shoreline = expand(stroke_width) & ~contract(stroke_width)
        stroke = shoreline.astype(np.float32) * 0.58
    return halo, stroke


def resample_rows(
    array: np.ndarray,
    top: int,
    bottom: int,
    width: int,
    full_height: int,
    world_size: float,
    resampling: Image.Resampling,
) -> np.ndarray:
    bounds = (
        0.0,
        world_size * (full_height - bottom) / full_height,
        world_size,
        world_size * (full_height - top) / full_height,
    )
    return resample_world_array(array, bounds, world_size, (width, bottom - top), resampling)


def apply(args: argparse.Namespace) -> dict[str, object]:
    started = time.perf_counter()
    world_size = float(args.world_size)
    grid = parse_asc(args.heightmap)
    validate_extent(grid, world_size)
    valid = np.ones(grid.elevation.shape, dtype=bool)
    if grid.nodata_value is not None:
        valid &= grid.elevation != grid.nodata_value
    land = valid_land_mask(grid, float(args.sea_level))

    row, column = np.gradient(_filled_elevation(grid), grid.cellsize, grid.cellsize)
    slope_degrees = np.degrees(np.arctan(np.hypot(row, column))).astype(np.float32)

    hillshade_enabled = bool(_option(args, "hillshade_enabled", True))
    hillshade_slope_weighted = bool(_option(args, "hillshade_slope_weighted", True))
    hillshade_opacity = float(args.opacity)
    slope_start = float(args.slope_start)
    slope_full = float(args.slope_full)
    if not 0.0 <= hillshade_opacity <= 1.0:
        raise HillshadeError("opacity must be between 0 and 1")
    if slope_start < 0 or slope_start >= slope_full:
        raise HillshadeError("hillshade slope thresholds require 0 <= start < full")
    shade = None
    hillshade_weight = None
    if hillshade_enabled:
        shade = multidirectional_hillshade(grid, (225, 270, 315, 360), float(args.elevation), valid)
        if hillshade_slope_weighted:
            hillshade_weight = slope_weight_from_degrees(slope_degrees, slope_start, slope_full) * land
        else:
            hillshade_weight = land.astype(np.float32)

    ocean_enabled = bool(_option(args, "ocean_enabled", False))
    ocean_color = parse_hex_color(str(_option(args, "ocean_color", "#C9DEE9")), "ocean color")
    halo_color = parse_hex_color(str(_option(args, "coast_halo_color", "#D3E4EC")), "coast halo color")
    stroke_color = parse_hex_color(str(_option(args, "coast_stroke_color", "#A7BDC8")), "coast stroke color")
    halo_width = int(_option(args, "coast_halo_width", 4))
    stroke_width = int(_option(args, "coast_stroke_width", 1))

    slope_mask_enabled = bool(_option(args, "slope_mask_enabled", False))
    slope_mask_color = parse_hex_color(str(_option(args, "slope_mask_color", "#7A7A7A")), "slope mask color")
    slope_mask_opacity = float(_option(args, "slope_mask_opacity", 0.12))
    slope_mask_start = float(_option(args, "slope_mask_start", 18.0))
    slope_mask_full = float(_option(args, "slope_mask_full", 35.0))
    if not 0.0 <= slope_mask_opacity <= 1.0:
        raise HillshadeError("slope mask opacity must be between 0 and 1")
    if slope_mask_start < 0 or slope_mask_start >= slope_mask_full:
        raise HillshadeError("slope mask thresholds require 0 <= start < full")
    slope_mask_weight = None
    if slope_mask_enabled:
        slope_mask_weight = slope_weight_from_degrees(slope_degrees, slope_mask_start, slope_mask_full) * land

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(args.master) as source:
            width, height = source.size
            if source.mode not in ("RGB", "RGBA"):
                raise HillshadeError(f"master must be RGB/RGBA, found {source.mode}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            target = Image.new("RGB", source.size)
            strip_height = 256
            coast_margin = max(halo_width, stroke_width) + 1 if ocean_enabled else 0
            for top in range(0, height, strip_height):
                bottom = min(top + strip_height, height)
                land_strip = np.clip(
                    resample_rows(land.astype(np.float32), top, bottom, width, height, world_size, Image.Resampling.BILINEAR),
                    0,
                    1,
                )
                base = np.asarray(source.crop((0, top, width, bottom)).convert("RGB"), dtype=np.uint8)
                composed = base
                if ocean_enabled:
                    composed = tint(composed, ocean_color, 1.0 - land_strip)
                if hillshade_enabled and shade is not None and hillshade_weight is not None:
                    shade_strip = resample_rows(shade, top, bottom, width, height, world_size, Image.Resampling.BICUBIC)
                    weight_strip = np.clip(
                        resample_rows(hillshade_weight, top, bottom, width, height, world_size, Image.Resampling.BICUBIC),
                        0,
                        1,
                    )
                    effective = 0.5 + (shade_strip - 0.5) * weight_strip
                    composed = blend_luminance(composed, effective, land_strip, hillshade_opacity)
                if slope_mask_enabled and slope_mask_weight is not None:
                    mask_strip = np.clip(
                        resample_rows(slope_mask_weight, top, bottom, width, height, world_size, Image.Resampling.BICUBIC),
                        0,
                        1,
                    )
                    composed = tint(composed, slope_mask_color, mask_strip * slope_mask_opacity)
                if ocean_enabled and (halo_width or stroke_width):
                    expanded_top = max(0, top - coast_margin)
                    expanded_bottom = min(height, bottom + coast_margin)
                    expanded_land = np.clip(
                        resample_rows(
                            land.astype(np.float32), expanded_top, expanded_bottom, width, height, world_size, Image.Resampling.BILINEAR
                        ),
                        0,
                        1,
                    )
                    halo, stroke = coast_layers(expanded_land, halo_width, stroke_width)
                    offset_top = top - expanded_top
                    offset_bottom = offset_top + (bottom - top)
                    composed = tint(composed, halo_color, halo[offset_top:offset_bottom])
                    composed = tint(composed, stroke_color, stroke[offset_top:offset_bottom])
                target.paste(Image.fromarray(composed, "RGB"), (0, top))
            target.save(args.output, "PNG")

    result = {
        "version": 2,
        "mode": "tourist-composite",
        "input2d": {"path": str(args.master), "sha256": sha256(args.master)},
        "heightmap": {"path": str(args.heightmap), "sha256": sha256(args.heightmap), "ncols": grid.ncols, "nrows": grid.nrows, "cellsize": grid.cellsize, "nodataValue": grid.nodata_value},
        "worldSize": world_size,
        "output": {"path": str(args.output), "width": width, "height": height, "sha256": sha256(args.output)},
        "orientation": {"flipVertical": False, "ascRows": "north-to-south", "masterY": "north-to-south"},
        "compositionOrder": COMPOSITION_ORDER,
        "ocean": {"enabled": ocean_enabled, "color": str(_option(args, "ocean_color", "#C9DEE9")), "coastHaloColor": str(_option(args, "coast_halo_color", "#D3E4EC")), "coastHaloWidthPx": halo_width, "coastStrokeColor": str(_option(args, "coast_stroke_color", "#A7BDC8")), "coastStrokeWidthPx": stroke_width},
        "hillshade": {"enabled": hillshade_enabled, "blend": "luminance", "multidirectional": {"azimuths": [225, 270, 315, 360], "elevation": float(args.elevation)}, "slopeWeight": {"enabled": hillshade_slope_weighted, "startDegrees": slope_start, "fullDegrees": slope_full}, "opacity": hillshade_opacity},
        "slopeMask": {"enabled": slope_mask_enabled, "color": str(_option(args, "slope_mask_color", "#7A7A7A")), "opacity": slope_mask_opacity, "startDegrees": slope_mask_start, "fullDegrees": slope_mask_full},
        "seaLevel": float(args.sea_level),
        "runtimeSeconds": round(time.perf_counter() - started, 3),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heightmap", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--world-size", type=float, required=True)
    parser.add_argument("--sea-level", type=float, required=True)
    parser.add_argument("--opacity", type=float, required=True)
    parser.add_argument("--elevation", type=float, default=40)
    parser.add_argument("--slope-start", type=float, default=5)
    parser.add_argument("--slope-full", type=float, default=30)
    parser.add_argument("--hillshade-enabled", type=parse_bool, default=True)
    parser.add_argument("--hillshade-slope-weighted", type=parse_bool, default=True)
    parser.add_argument("--ocean-enabled", type=parse_bool, default=False)
    parser.add_argument("--ocean-color", default="#C9DEE9")
    parser.add_argument("--coast-halo-color", default="#D3E4EC")
    parser.add_argument("--coast-halo-width", type=int, default=4)
    parser.add_argument("--coast-stroke-color", default="#A7BDC8")
    parser.add_argument("--coast-stroke-width", type=int, default=1)
    parser.add_argument("--slope-mask-enabled", type=parse_bool, default=False)
    parser.add_argument("--slope-mask-color", default="#7A7A7A")
    parser.add_argument("--slope-mask-opacity", type=float, default=0.12)
    parser.add_argument("--slope-mask-start", type=float, default=18)
    parser.add_argument("--slope-mask-full", type=float, default=35)
    return parser.parse_args()


if __name__ == "__main__":
    try:
        print(json.dumps(apply(arguments()), indent=2))
    except HillshadeError as error:
        print(f"ERROR: {error}")
        raise SystemExit(2)
