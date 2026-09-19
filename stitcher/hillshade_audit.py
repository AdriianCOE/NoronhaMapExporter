"""Create small, deterministic hillshade review artifacts from an ESRI ASCII Grid.

This is an audit tool.  It never changes the source master, the ASC, a WRP,
or public exporter configuration.  It writes derived files only to --output.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


class HillshadeError(RuntimeError):
    """Raised for an invalid heightmap or an unsafe audit request."""


@dataclass(frozen=True)
class AscGrid:
    path: Path
    ncols: int
    nrows: int
    xll: float
    yll: float
    xll_reference: str
    yll_reference: str
    cellsize: float
    nodata_value: float | None
    elevation: np.ndarray

    @property
    def width_m(self) -> float:
        return self.ncols * self.cellsize

    @property
    def height_m(self) -> float:
        return self.nrows * self.cellsize


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_asc(path: Path) -> AscGrid:
    """Read a strictly validated ESRI ASCII Grid without guessing its extent."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        raise HillshadeError(f"Cannot read ASC: {path}") from error

    allowed = {"ncols", "nrows", "xllcorner", "xllcenter", "yllcorner", "yllcenter", "cellsize", "nodata_value"}
    header: dict[str, str] = {}
    data_start = 0
    for index, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) >= 2 and tokens[0].lower() in allowed:
            key = tokens[0].lower()
            if key in header:
                raise HillshadeError(f"Duplicate ASC header field: {key}")
            if len(tokens) != 2:
                raise HillshadeError(f"ASC header field {key} must have exactly one value")
            header[key] = tokens[1]
            data_start = index + 1
            continue
        if not header:
            raise HillshadeError("ASC must begin with header fields")
        data_start = index
        break

    required = {"ncols", "nrows", "cellsize"}
    missing = sorted(required - set(header))
    if missing:
        raise HillshadeError("ASC missing required header fields: " + ", ".join(missing))
    if ("xllcorner" in header) == ("xllcenter" in header):
        raise HillshadeError("ASC requires exactly one of xllcorner or xllcenter")
    if ("yllcorner" in header) == ("yllcenter" in header):
        raise HillshadeError("ASC requires exactly one of yllcorner or yllcenter")

    try:
        ncols = int(header["ncols"])
        nrows = int(header["nrows"])
        cellsize = float(header["cellsize"])
        x_key = "xllcorner" if "xllcorner" in header else "xllcenter"
        y_key = "yllcorner" if "yllcorner" in header else "yllcenter"
        xll = float(header[x_key])
        yll = float(header[y_key])
        nodata = float(header["nodata_value"]) if "nodata_value" in header else None
    except ValueError as error:
        raise HillshadeError("ASC header contains a non-numeric value") from error
    if ncols < 2 or nrows < 2 or not math.isfinite(cellsize) or cellsize <= 0:
        raise HillshadeError("ASC dimensions must be at least 2x2 and cellsize must be positive")
    if not math.isfinite(xll) or not math.isfinite(yll) or (nodata is not None and not math.isfinite(nodata)):
        raise HillshadeError("ASC header values must be finite")
    if data_start >= len(lines):
        raise HillshadeError("ASC contains no numeric data rows")

    try:
        elevation = np.loadtxt(io.StringIO("\n".join(lines[data_start:])), dtype=np.float32)
    except ValueError as error:
        raise HillshadeError("ASC has a non-numeric elevation value") from error
    elevation = np.atleast_2d(elevation)
    if elevation.shape != (nrows, ncols):
        raise HillshadeError(f"ASC data dimensions {elevation.shape[1]}x{elevation.shape[0]} do not match header {ncols}x{nrows}")
    if not np.all(np.isfinite(elevation)):
        raise HillshadeError("ASC contains non-finite elevation values")

    return AscGrid(path, ncols, nrows, xll, yll, x_key, y_key, cellsize, nodata, elevation)


def validate_extent(grid: AscGrid, world_size: float) -> None:
    if world_size <= 0:
        raise HillshadeError("world size must be positive")
    if not math.isclose(grid.width_m, world_size, rel_tol=0.0, abs_tol=1e-6) or not math.isclose(grid.height_m, world_size, rel_tol=0.0, abs_tol=1e-6):
        raise HillshadeError(f"ASC physical extent {grid.width_m:g}x{grid.height_m:g} m does not match world size {world_size:g} m")


def valid_land_mask(grid: AscGrid, sea_level: float) -> np.ndarray:
    valid = np.ones(grid.elevation.shape, dtype=bool)
    if grid.nodata_value is not None:
        valid &= grid.elevation != grid.nodata_value
    return valid & (grid.elevation > sea_level)


def _filled_elevation(grid: AscGrid) -> np.ndarray:
    elevation = grid.elevation.astype(np.float32, copy=True)
    if grid.nodata_value is None:
        return elevation
    invalid = elevation == grid.nodata_value
    if not invalid.any():
        return elevation
    valid_values = elevation[~invalid]
    if valid_values.size == 0:
        raise HillshadeError("ASC has no valid elevation cells")
    # NODATA is never rendered, but a neutral fill prevents it from injecting
    # NaNs or extreme gradients into neighboring valid samples.
    elevation[invalid] = np.median(valid_values)
    return elevation


def surface_hillshade(grid: AscGrid, azimuth: float, elevation_degrees: float) -> np.ndarray:
    """Return a normalized 0..1 illumination field from world-space normals."""
    if not 0 <= azimuth <= 360 or not 0 < elevation_degrees < 90:
        raise HillshadeError("azimuth must be 0..360 and elevation must be between 0 and 90")
    source = _filled_elevation(grid)
    row_gradient, x_gradient = np.gradient(source, grid.cellsize, grid.cellsize)
    # ASC row 0 is north. Map-world Z increases north, unlike image rows.
    z_gradient = -row_gradient
    normal_x = -x_gradient
    normal_z = -z_gradient
    normal_y = np.ones_like(source)
    norm = np.sqrt(normal_x * normal_x + normal_y * normal_y + normal_z * normal_z)
    normal_x /= norm
    normal_y /= norm
    normal_z /= norm

    azimuth_radians = np.deg2rad(azimuth)
    altitude_radians = np.deg2rad(elevation_degrees)
    light_x = np.sin(azimuth_radians) * np.cos(altitude_radians)
    light_z = np.cos(azimuth_radians) * np.cos(altitude_radians)
    light_y = np.sin(altitude_radians)
    shade = normal_x * light_x + normal_y * light_y + normal_z * light_z
    return np.clip(shade, 0.0, 1.0).astype(np.float32)


def normalize_hillshade(shade: np.ndarray, valid: np.ndarray) -> np.ndarray:
    values = shade[valid]
    if values.size == 0:
        raise HillshadeError("No valid cells available for hillshade normalization")
    low, high = np.quantile(values, (0.01, 0.99))
    if high - low < 1e-6:
        return np.full(shade.shape, 0.5, dtype=np.float32)
    return np.clip((shade - low) / (high - low), 0.0, 1.0).astype(np.float32)


def multidirectional_hillshade(grid: AscGrid, azimuths: Iterable[float], elevation_degrees: float, valid: np.ndarray) -> np.ndarray:
    directions = tuple(float(value) for value in azimuths)
    if not directions:
        raise HillshadeError("At least one multidirectional azimuth is required")
    stacked = np.stack([surface_hillshade(grid, azimuth, elevation_degrees) for azimuth in directions])
    return normalize_hillshade(stacked.mean(axis=0), valid)


def slope_weight_from_degrees(slope_degrees: np.ndarray, flat_degrees: float = 5.0, steep_degrees: float = 30.0) -> np.ndarray:
    """Smoothly suppress relief on flat ground and retain it on steep slopes."""
    if not 0 <= flat_degrees < steep_degrees:
        raise HillshadeError("slope weighting requires 0 <= flat_degrees < steep_degrees")
    linear = np.clip((slope_degrees - flat_degrees) / (steep_degrees - flat_degrees), 0.0, 1.0)
    return (linear * linear * (3.0 - 2.0 * linear)).astype(np.float32)


def world_bounds_to_image_box(bounds: tuple[float, float, float, float], world_size: float, image_size: tuple[int, int]) -> tuple[float, float, float, float]:
    """Translate left,bottom,right,top world bounds to top-down image bounds."""
    left, bottom, right, top = bounds
    if not (0 <= left < right <= world_size and 0 <= bottom < top <= world_size):
        raise HillshadeError("Crop bounds must be inside the declared world extent")
    width, height = image_size
    return (left / world_size * width, (world_size - top) / world_size * height, right / world_size * width, (world_size - bottom) / world_size * height)


def resample_world_array(array: np.ndarray, bounds: tuple[float, float, float, float], world_size: float, destination_size: tuple[int, int], resampling: Image.Resampling) -> np.ndarray:
    box = world_bounds_to_image_box(bounds, world_size, (array.shape[1], array.shape[0]))
    image = Image.fromarray(array.astype(np.float32), mode="F")
    transformed = image.transform(destination_size, Image.Transform.EXTENT, box, resample=resampling)
    return np.asarray(transformed, dtype=np.float32)


def load_master_crop(path: Path, bounds: tuple[float, float, float, float], world_size: float) -> tuple[Image.Image, tuple[int, int]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(path) as master:
            destination_size = (
                round((bounds[2] - bounds[0]) / world_size * master.width),
                round((bounds[3] - bounds[1]) / world_size * master.height),
            )
            box = world_bounds_to_image_box(bounds, world_size, master.size)
            return master.convert("RGB").transform(destination_size, Image.Transform.EXTENT, box, resample=Image.Resampling.BICUBIC), master.size


def blend_luminance(base: np.ndarray, shade: np.ndarray, land: np.ndarray, opacity: float) -> np.ndarray:
    if not 0 <= opacity <= 1:
        raise HillshadeError("opacity must be between 0 and 1")
    if base.shape[:2] != shade.shape or shade.shape != land.shape:
        raise HillshadeError("Base, hillshade, and land mask dimensions must match")
    delta = (shade - 0.5) * 0.8
    factor = 1.0 + opacity * land * delta
    return np.clip(base.astype(np.float32) * factor[:, :, None], 0, 255).astype(np.uint8)


def blend_multiply(base: np.ndarray, shade: np.ndarray, land: np.ndarray, opacity: float) -> np.ndarray:
    if not 0 <= opacity <= 1:
        raise HillshadeError("opacity must be between 0 and 1")
    factor = 1.0 - opacity * land * (1.0 - shade)
    return np.clip(base.astype(np.float32) * factor[:, :, None], 0, 255).astype(np.uint8)


def _caption(image: Image.Image, label: str) -> Image.Image:
    caption_height = 28
    result = Image.new("RGB", (image.width, image.height + caption_height), "white")
    result.paste(image, (0, caption_height))
    ImageDraw.Draw(result).text((8, 7), label, fill="black", font=ImageFont.load_default())
    return result


def _sheet(images: list[tuple[str, Image.Image]], columns: int = 4) -> Image.Image:
    thumbnails = []
    for label, image in images:
        thumbnail = image.copy()
        thumbnail.thumbnail((480, 270), Image.Resampling.LANCZOS)
        thumbnails.append(_caption(thumbnail, label))
    cell_width = max(image.width for image in thumbnails)
    cell_height = max(image.height for image in thumbnails)
    rows = math.ceil(len(thumbnails) / columns)
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "#efefef")
    for index, image in enumerate(thumbnails):
        sheet.paste(image, ((index % columns) * cell_width, (index // columns) * cell_height))
    return sheet


def coastline_overlay(base: Image.Image, land: np.ndarray) -> Image.Image:
    edges = land.astype(bool)
    boundary = np.zeros(edges.shape, dtype=bool)
    boundary[1:, :] |= edges[1:, :] != edges[:-1, :]
    boundary[:, 1:] |= edges[:, 1:] != edges[:, :-1]
    result = np.asarray(base, dtype=np.uint8).copy()
    result[boundary] = (0, 220, 255)
    return Image.fromarray(result, "RGB")


def audit(args: argparse.Namespace) -> dict[str, object]:
    started = time.perf_counter()
    grid = parse_asc(args.heightmap)
    validate_extent(grid, args.world_size)
    valid = np.ones(grid.elevation.shape, dtype=bool)
    if grid.nodata_value is not None:
        valid &= grid.elevation != grid.nodata_value
    land = valid_land_mask(grid, args.sea_level)
    single = normalize_hillshade(surface_hillshade(grid, args.azimuth, args.elevation), valid)
    multi_directions = (225.0, 270.0, 315.0, 360.0)
    multi = multidirectional_hillshade(grid, multi_directions, args.elevation, valid)

    base, master_size = load_master_crop(args.master, args.bounds, args.world_size)
    base_array = np.asarray(base, dtype=np.uint8)
    size = base.size
    single_crop = resample_world_array(single, args.bounds, args.world_size, size, Image.Resampling.BICUBIC)
    multi_crop = resample_world_array(multi, args.bounds, args.world_size, size, Image.Resampling.BICUBIC)
    land_crop = resample_world_array(land.astype(np.float32), args.bounds, args.world_size, size, Image.Resampling.BILINEAR)
    land_crop = np.clip(land_crop, 0.0, 1.0)

    args.output.mkdir(parents=True, exist_ok=True)
    # The land mask protects the composite. Give ocean/NODATA a neutral value
    # in the diagnostic grayscale as well, rather than visualizing a false
    # black cliff along non-land samples.
    diagnostic_single = single_crop.copy()
    diagnostic_multi = multi_crop.copy()
    diagnostic_single[land_crop < 0.5] = 0.5
    diagnostic_multi[land_crop < 0.5] = 0.5
    Image.fromarray(np.round(diagnostic_single * 255).astype(np.uint8), "L").save(args.output / "hillshade_single_grayscale.png")
    Image.fromarray(np.round(diagnostic_multi * 255).astype(np.uint8), "L").save(args.output / "hillshade_multi_grayscale.png")
    Image.fromarray(np.round(land_crop * 255).astype(np.uint8), "L").save(args.output / "land_mask.png")
    base.save(args.output / "hillshade_test_00_none.png")

    samples: list[tuple[str, Image.Image]] = [("NO HILLSHADE", base)]
    variants: dict[str, Image.Image] = {}
    for name, shade, opacity in (
        ("hillshade_test_01_single_10.png", single_crop, 0.10),
        ("hillshade_test_02_single_15.png", single_crop, 0.15),
        ("hillshade_test_03_single_20.png", single_crop, 0.20),
        ("hillshade_test_04_multi_10.png", multi_crop, 0.10),
        ("hillshade_test_05_multi_15.png", multi_crop, 0.15),
        ("hillshade_test_06_multi_20.png", multi_crop, 0.20),
    ):
        output = Image.fromarray(blend_luminance(base_array, shade, land_crop, opacity), "RGB")
        output.save(args.output / name)
        variants[name] = output
        samples.append((name.replace("hillshade_test_", "").replace(".png", "").replace("_", " ").upper(), output))
    _sheet(samples).save(args.output / "hillshade_comparison.png")

    neutral = variants["hillshade_test_02_single_15.png"]
    multiply = Image.fromarray(blend_multiply(base_array, single_crop, land_crop, 0.15), "RGB")
    _sheet([("BASE", base), ("SINGLE 15 NEUTRAL", neutral), ("SINGLE 15 MULTIPLY", multiply)], columns=3).save(args.output / "hillshade_blend_methods.png")
    _sheet([("BASE + ASC COASTLINE (CYAN)", coastline_overlay(base, land_crop >= 0.5)), ("MULTIDIRECTIONAL 15", variants["hillshade_test_05_multi_15.png"])], columns=2).save(args.output / "heightmap_hillshade_alignment.png")

    result = {
        "version": 1,
        "auditOnly": True,
        "master": {"path": str(args.master), "sha256": sha256(args.master), "sourceDimensions": {"width": master_size[0], "height": master_size[1]}, "cropDimensions": {"width": size[0], "height": size[1]}},
        "heightmap": {
            "path": str(args.heightmap), "sha256": sha256(args.heightmap), "ncols": grid.ncols, "nrows": grid.nrows,
            "xll": grid.xll, "yll": grid.yll, "xllReference": grid.xll_reference, "yllReference": grid.yll_reference,
            "cellsize": grid.cellsize, "physicalExtent": {"width": grid.width_m, "height": grid.height_m}, "nodataValue": grid.nodata_value,
        },
        "world": {"size": args.world_size, "bounds": {"left": args.bounds[0], "bottom": args.bounds[1], "right": args.bounds[2], "top": args.bounds[3]}},
        "orientation": {"ascRows": "north-to-south (ESRI ASCII Grid)", "masterImageY": "north-to-south / world Z decreases downward", "flipVertical": False, "validation": "cyan ASC land boundary over exact world-bound master crop"},
        "landMask": {"seaLevel": args.sea_level, "landCells": int(land.sum()), "waterOrNoDataCells": int((~land).sum())},
        "single": {"azimuth": args.azimuth, "elevation": args.elevation},
        "multidirectional": {"azimuths": multi_directions, "elevation": args.elevation},
        "blend": {"variantMethod": "luminance modulation", "comparisonMethod": "multiply", "opacities": [0.10, 0.15, 0.20]},
        "outputs": {path.name: sha256(path) for path in sorted(args.output.glob("*.png"))},
        "runtimeSeconds": round(time.perf_counter() - started, 3),
    }
    (args.output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heightmap", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--world-size", type=float, required=True)
    parser.add_argument("--sea-level", type=float, required=True)
    parser.add_argument("--bounds", type=float, nargs=4, metavar=("LEFT", "BOTTOM", "RIGHT", "TOP"), required=True)
    parser.add_argument("--azimuth", type=float, default=315.0)
    parser.add_argument("--elevation", type=float, default=40.0)
    return parser.parse_args()


def main() -> int:
    try:
        result = audit(parse_arguments())
    except HillshadeError as error:
        print(f"ERROR: {error}")
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
