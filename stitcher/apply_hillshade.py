"""Apply optional multidirectional slope-weighted hillshade to a 2D master.

The input master is read-only.  Output is a separate PNG plus manifest.
"""
from __future__ import annotations
import argparse, json, time, warnings
from pathlib import Path
import numpy as np
from PIL import Image
try:
    from stitcher.hillshade_audit import HillshadeError, _filled_elevation, blend_luminance, multidirectional_hillshade, parse_asc, resample_world_array, sha256, slope_weight_from_degrees, valid_land_mask, validate_extent
except ModuleNotFoundError:
    from hillshade_audit import HillshadeError, _filled_elevation, blend_luminance, multidirectional_hillshade, parse_asc, resample_world_array, sha256, slope_weight_from_degrees, valid_land_mask, validate_extent

def apply(args: argparse.Namespace) -> dict[str, object]:
    started = time.perf_counter()
    grid = parse_asc(args.heightmap); validate_extent(grid, args.world_size)
    valid = np.ones(grid.elevation.shape, dtype=bool)
    if grid.nodata_value is not None: valid &= grid.elevation != grid.nodata_value
    land = valid_land_mask(grid, args.sea_level)
    shade = multidirectional_hillshade(grid, (225, 270, 315, 360), args.elevation, valid)
    row, column = np.gradient(_filled_elevation(grid), grid.cellsize, grid.cellsize)
    slope = np.degrees(np.arctan(np.hypot(row, column)))
    weight = slope_weight_from_degrees(slope, args.slope_start, args.slope_full) * land
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(args.master) as source:
            width, height = source.size
            if source.mode not in ("RGB", "RGBA"): raise HillshadeError(f"master must be RGB/RGBA, found {source.mode}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            target = Image.new("RGB", source.size)
            # Keeping height fields at 1024² limits NumPy memory.  Only one
            # 256-row RGB source/composite strip is materialized at a time.
            for top in range(0, height, 256):
                bottom = min(top + 256, height)
                bounds = (0.0, args.world_size * (height - bottom) / height, args.world_size, args.world_size * (height - top) / height)
                size = (width, bottom - top)
                shade_strip = resample_world_array(shade, bounds, args.world_size, size, Image.Resampling.BICUBIC)
                land_strip = np.clip(resample_world_array(land.astype(np.float32), bounds, args.world_size, size, Image.Resampling.BILINEAR), 0, 1)
                weight_strip = np.clip(resample_world_array(weight, bounds, args.world_size, size, Image.Resampling.BICUBIC), 0, 1)
                effective = 0.5 + (shade_strip - 0.5) * weight_strip
                base = np.asarray(source.crop((0, top, width, bottom)).convert("RGB"), dtype=np.uint8)
                target.paste(Image.fromarray(blend_luminance(base, effective, land_strip, args.opacity), "RGB"), (0, top))
            target.save(args.output, "PNG")
    result = {"version": 1, "mode": "multidirectional-slope-weighted", "input2d": {"path": str(args.master), "sha256": sha256(args.master)}, "heightmap": {"path": str(args.heightmap), "sha256": sha256(args.heightmap), "ncols": grid.ncols, "nrows": grid.nrows, "cellsize": grid.cellsize, "nodataValue": grid.nodata_value}, "worldSize": args.world_size, "output": {"path": str(args.output), "width": width, "height": height, "sha256": sha256(args.output)}, "orientation": {"flipVertical": False, "ascRows": "north-to-south", "masterY": "north-to-south"}, "multidirectional": {"azimuths": [225,270,315,360], "elevation": args.elevation}, "slopeWeight": {"startDegrees": args.slope_start, "fullDegrees": args.slope_full}, "seaLevel": args.sea_level, "opacity": args.opacity, "runtimeSeconds": round(time.perf_counter()-started,3)}
    args.manifest.parent.mkdir(parents=True, exist_ok=True); args.manifest.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result

def arguments() -> argparse.Namespace:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--heightmap",type=Path,required=True); p.add_argument("--master",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--manifest",type=Path,required=True); p.add_argument("--world-size",type=float,required=True); p.add_argument("--sea-level",type=float,required=True); p.add_argument("--opacity",type=float,required=True); p.add_argument("--elevation",type=float,default=40); p.add_argument("--slope-start",type=float,default=5); p.add_argument("--slope-full",type=float,default=30); return p.parse_args()
if __name__ == "__main__":
    try: print(json.dumps(apply(arguments()), indent=2))
    except HillshadeError as error: print(f"ERROR: {error}"); raise SystemExit(2)
