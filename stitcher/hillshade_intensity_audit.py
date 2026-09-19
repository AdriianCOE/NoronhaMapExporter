"""Visual-only opacity refinement for the selected slope-weighted hillshade."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from stitcher.hillshade_audit import HillshadeError, _filled_elevation, _sheet, blend_luminance, load_master_crop, multidirectional_hillshade, parse_asc, resample_world_array, sha256, slope_weight_from_degrees, valid_land_mask, validate_extent
except ModuleNotFoundError:
    from hillshade_audit import HillshadeError, _filled_elevation, _sheet, blend_luminance, load_master_crop, multidirectional_hillshade, parse_asc, resample_world_array, sha256, slope_weight_from_degrees, valid_land_mask, validate_extent


def run(args: argparse.Namespace) -> dict[str, object]:
    started = time.perf_counter()
    grid = parse_asc(args.heightmap)
    validate_extent(grid, args.world_size)
    valid = np.ones(grid.elevation.shape, dtype=bool)
    if grid.nodata_value is not None:
        valid &= grid.elevation != grid.nodata_value
    land = valid_land_mask(grid, args.sea_level)
    multi = multidirectional_hillshade(grid, (225.0, 270.0, 315.0, 360.0), args.elevation, valid)
    row_gradient, x_gradient = np.gradient(_filled_elevation(grid), grid.cellsize, grid.cellsize)
    slope = np.degrees(np.arctan(np.hypot(row_gradient, x_gradient)))
    weight = slope_weight_from_degrees(slope, args.flat_slope, args.steep_slope) * land

    base, source_size = load_master_crop(args.master, args.bounds, args.world_size)
    base_array = np.asarray(base, dtype=np.uint8)
    multi_crop = resample_world_array(multi, args.bounds, args.world_size, base.size, Image.Resampling.BICUBIC)
    land_crop = np.clip(resample_world_array(land.astype(np.float32), args.bounds, args.world_size, base.size, Image.Resampling.BILINEAR), 0.0, 1.0)
    weight_crop = np.clip(resample_world_array(weight, args.bounds, args.world_size, base.size, Image.Resampling.BICUBIC), 0.0, 1.0)
    weighted_shade = 0.5 + (multi_crop - 0.5) * weight_crop

    variants = [("BASE", base)]
    for opacity in (0.20, 0.225, 0.25):
        variants.append((f"SLOPE-WEIGHTED MAX {opacity * 100:g}%", Image.fromarray(blend_luminance(base_array, weighted_shade, land_crop, opacity), "RGB")))
    args.output.mkdir(parents=True, exist_ok=False)
    sheet = args.output / "hillshade_slope_weighted_intensity_comparison.png"
    _sheet(variants, columns=4).save(sheet)
    result = {
        "version": 1, "auditOnly": True,
        "master": {"sha256": sha256(args.master), "sourceDimensions": source_size, "cropDimensions": base.size},
        "heightmap": {"sha256": sha256(args.heightmap), "seaLevel": args.sea_level},
        "worldBounds": args.bounds,
        "mode": "multidirectional-slope-weighted",
        "azimuths": [225, 270, 315, 360], "elevation": args.elevation,
        "slopeWeight": {"startDegrees": args.flat_slope, "fullDegrees": args.steep_slope},
        "opacities": [0.20, 0.225, 0.25],
        "output": {"path": sheet.name, "sha256": sha256(sheet)},
        "runtimeSeconds": round(time.perf_counter() - started, 3),
    }
    (args.output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heightmap", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--world-size", type=float, required=True)
    parser.add_argument("--sea-level", type=float, required=True)
    parser.add_argument("--bounds", type=float, nargs=4, required=True)
    parser.add_argument("--elevation", type=float, default=40.0)
    parser.add_argument("--flat-slope", type=float, default=5.0)
    parser.add_argument("--steep-slope", type=float, default=30.0)
    return parser.parse_args()


if __name__ == "__main__":
    try:
        print(json.dumps(run(arguments()), indent=2))
    except HillshadeError as error:
        print(f"ERROR: {error}")
        raise SystemExit(2)
