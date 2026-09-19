"""Second visual-only hillshade audit for a known steep terrain crop."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

try:  # package execution: python -m stitcher.hillshade_strong_slope_audit
    from stitcher.hillshade_audit import (
        HillshadeError, _filled_elevation, _sheet, blend_luminance, load_master_crop,
        multidirectional_hillshade, parse_asc, resample_world_array, sha256,
        slope_weight_from_degrees, valid_land_mask, validate_extent,
    )
except ModuleNotFoundError:  # direct execution: python stitcher/hillshade_strong_slope_audit.py
    from hillshade_audit import (
        HillshadeError, _filled_elevation, _sheet, blend_luminance, load_master_crop,
        multidirectional_hillshade, parse_asc, resample_world_array, sha256,
        slope_weight_from_degrees, valid_land_mask, validate_extent,
    )


def slope_degrees(grid) -> np.ndarray:
    row_gradient, x_gradient = np.gradient(_filled_elevation(grid), grid.cellsize, grid.cellsize)
    return np.degrees(np.arctan(np.hypot(row_gradient, x_gradient))).astype(np.float32)


def run(args: argparse.Namespace) -> dict[str, object]:
    started = time.perf_counter()
    grid = parse_asc(args.heightmap)
    validate_extent(grid, args.world_size)
    valid = np.ones(grid.elevation.shape, dtype=bool)
    if grid.nodata_value is not None:
        valid &= grid.elevation != grid.nodata_value
    land = valid_land_mask(grid, args.sea_level)
    multi = multidirectional_hillshade(grid, (225.0, 270.0, 315.0, 360.0), args.elevation, valid)
    slope = slope_degrees(grid)
    weight = slope_weight_from_degrees(slope, args.flat_slope, args.steep_slope) * land

    base, master_size = load_master_crop(args.master, args.bounds, args.world_size)
    base_array = np.asarray(base, dtype=np.uint8)
    size = base.size
    multi_crop = resample_world_array(multi, args.bounds, args.world_size, size, Image.Resampling.BICUBIC)
    land_crop = np.clip(resample_world_array(land.astype(np.float32), args.bounds, args.world_size, size, Image.Resampling.BILINEAR), 0.0, 1.0)
    weight_crop = np.clip(resample_world_array(weight, args.bounds, args.world_size, size, Image.Resampling.BICUBIC), 0.0, 1.0)

    weighted_shade = 0.5 + (multi_crop - 0.5) * weight_crop
    variants = [
        ("BASE", base),
        ("MULTIDIRECTIONAL 15%", Image.fromarray(blend_luminance(base_array, multi_crop, land_crop, 0.15), "RGB")),
        ("MULTIDIRECTIONAL 20%", Image.fromarray(blend_luminance(base_array, multi_crop, land_crop, 0.20), "RGB")),
        ("MULTIDIRECTIONAL 25%", Image.fromarray(blend_luminance(base_array, multi_crop, land_crop, 0.25), "RGB")),
        ("MULTI SLOPE-WEIGHTED (MAX 25%)", Image.fromarray(blend_luminance(base_array, weighted_shade, land_crop, 0.25), "RGB")),
    ]
    args.output.mkdir(parents=True, exist_ok=False)
    sheet_path = args.output / "hillshade_strong_slope_comparison.png"
    _sheet(variants, columns=3).save(sheet_path)
    manifest = {
        "version": 1,
        "auditOnly": True,
        "master": {"path": str(args.master), "sha256": sha256(args.master), "sourceDimensions": {"width": master_size[0], "height": master_size[1]}, "cropDimensions": {"width": size[0], "height": size[1]}},
        "heightmap": {"path": str(args.heightmap), "sha256": sha256(args.heightmap), "ncols": grid.ncols, "nrows": grid.nrows, "cellsize": grid.cellsize, "nodataValue": grid.nodata_value},
        "world": {"size": args.world_size, "bounds": {"left": args.bounds[0], "bottom": args.bounds[1], "right": args.bounds[2], "top": args.bounds[3]}},
        "orientation": {"flipVertical": False, "method": "same ESRI north-top to MapWidget north-top geometry as the first audit"},
        "multidirectional": {"azimuths": [225, 270, 315, 360], "elevation": args.elevation},
        "slopeWeighted": {"method": "smoothstep", "flatSlopeDegrees": args.flat_slope, "steepSlopeDegrees": args.steep_slope, "maxOpacity": 0.25, "cropSlopeDegrees": {"minimum": float(slope[land].min()), "maximum": float(slope[land].max()), "mean": float(slope[land].mean())}},
        "seaLevel": args.sea_level,
        "output": {"path": sheet_path.name, "sha256": sha256(sheet_path)},
        "runtimeSeconds": round(time.perf_counter() - started, 3),
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heightmap", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--world-size", type=float, required=True)
    parser.add_argument("--sea-level", type=float, required=True)
    parser.add_argument("--bounds", type=float, nargs=4, metavar=("LEFT", "BOTTOM", "RIGHT", "TOP"), required=True)
    parser.add_argument("--elevation", type=float, default=40.0)
    parser.add_argument("--flat-slope", type=float, default=5.0)
    parser.add_argument("--steep-slope", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    try:
        print(json.dumps(run(arguments()), indent=2))
    except HillshadeError as error:
        print(f"ERROR: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
