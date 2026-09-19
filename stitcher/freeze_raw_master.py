#!/usr/bin/env python3
"""Freeze validated raw masters outside Git and compare their native world crops."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw


# A validated 0.15 Noronha master is 92.16 million pixels. Keep Pillow's
# accidental-bomb guard above the documented raw-master range while retaining
# protection for unexpectedly huge input files.
Image.MAX_IMAGE_PIXELS = 200_000_000


HEADER_HEIGHT = 28
BACKGROUND = (24, 24, 24)
HEADER = (48, 48, 48)
TEXT = (240, 240, 240)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def session_manifest(session: Path) -> dict:
    manifest = read_json(session / "manifest.json")
    if not manifest.get("captureComplete") or not manifest.get("valid"):
        raise ValueError("source session is incomplete or invalid")
    tiles = manifest.get("tiles")
    if not isinstance(tiles, list) or len(tiles) != manifest.get("grid", {}).get("total"):
        raise ValueError("source session has incomplete tiles")
    request_ids = [tile.get("requestId") for tile in tiles]
    filenames = [tile.get("filename") for tile in tiles]
    if None in request_ids or len(set(request_ids)) != len(request_ids):
        raise ValueError("source session request IDs are missing or duplicated")
    if None in filenames or len(set(filenames)) != len(filenames):
        raise ValueError("source session filenames are missing or duplicated")
    return manifest


def master_paths(session: Path) -> tuple[Path, Path]:
    output = session / "output"
    master = output / "noronha_engine_master.png"
    preview = output / "noronha_engine_preview.jpg"
    if not master.is_file() or not preview.is_file():
        raise ValueError("stitch output is missing; run stitch_map.py first")
    return master, preview


def uniform_mpp(manifest: dict) -> tuple[float, float, float]:
    tiles = manifest["tiles"]
    scales = {float(tile["getScale"]) for tile in tiles}
    mpp_x = {float(tile["metersPerPixel"]["x"]) for tile in tiles}
    mpp_z = {float(tile["metersPerPixel"]["z"]) for tile in tiles}
    if len(scales) != 1 or len(mpp_x) != 1 or len(mpp_z) != 1:
        raise ValueError("raw master session must have one scale and one MPP")
    return scales.pop(), mpp_x.pop(), mpp_z.pop()


def freeze(args: argparse.Namespace) -> int:
    session = args.session.resolve()
    manifest = session_manifest(session)
    scale, mpp_x, mpp_z = uniform_mpp(manifest)
    master, preview = master_paths(session)
    with Image.open(master) as image:
        if image.format != "PNG" or image.mode != "RGB":
            raise ValueError("raw master must be RGB PNG")
        width, height = image.size
    root = args.reference_root.resolve() / args.wrp_sha256[:16] / args.name
    if root.exists():
        raise ValueError(f"refusing to overwrite existing immutable reference: {root}")
    output = root / "output"
    captures = root / "captures"
    logs = root / "logs"
    output.mkdir(parents=True)
    captures.mkdir()
    logs.mkdir()
    for tile in manifest["tiles"]:
        source = session / "captures" / tile["filename"]
        if not source.is_file():
            raise ValueError(f"missing source capture: {source}")
        if sha256(source) != tile["png"]["sha256"]:
            raise ValueError(f"capture hash mismatch: {source.name}")
        shutil.copy2(source, captures / source.name)
    raw_name = f"noronha_{args.name}_raw.png"
    preview_name = f"noronha_{args.name}_preview.jpg"
    shutil.copy2(master, output / raw_name)
    shutil.copy2(preview, output / preview_name)
    stitch_log = session / "logs" / "stitch.log"
    if stitch_log.is_file():
        shutil.copy2(stitch_log, logs / "stitch.log")
    frozen = {
        "version": 1,
        "name": args.name,
        "sourceSession": str(session),
        "terrain": {
            "world": manifest["world"],
            "worldSize": args.world_size,
            "wrpSha256": args.wrp_sha256,
        },
        "renderer": {"scale": scale},
        "capture": {
            "resolution": {"width": manifest["tiles"][0]["png"]["width"], "height": manifest["tiles"][0]["png"]["height"]},
            "overlapFraction": manifest["overlapFraction"],
            "grid": manifest["grid"],
            "metersPerPixel": {"x": mpp_x, "z": mpp_z},
            "tiles": manifest["tiles"],
        },
        "rawMaster": {
            "path": f"output/{raw_name}",
            "width": width,
            "height": height,
            "sha256": sha256(output / raw_name),
        },
        "preview": f"output/{preview_name}",
        "stitching": "geometric world bounds; exact terrain crop; no feature matching",
    }
    write_json(root / "manifest.json", frozen)
    print(root)
    return 0


def index(args: argparse.Namespace) -> int:
    base = args.reference_root.resolve() / args.wrp_sha256[:16]
    destination = base / "masters.json"
    if destination.exists():
        raise ValueError(f"refusing to overwrite existing index: {destination}")
    masters = {}
    for name in ("overview", "detail"):
        manifest = read_json(base / name / "manifest.json")
        capture = manifest["capture"]
        raw = manifest["rawMaster"]
        masters[name] = {
            "scale": manifest["renderer"]["scale"],
            "width": raw["width"],
            "height": raw["height"],
            "metersPerPixel": capture["metersPerPixel"],
            "grid": capture["grid"],
            "tileCount": len(capture["tiles"]),
            "sha256": raw["sha256"],
            "path": f"{name}/{raw['path']}",
        }
    first = read_json(base / "overview" / "manifest.json")["terrain"]
    write_json(destination, {"world": first["world"], "worldSize": first["worldSize"], "wrpSha256": args.wrp_sha256, **masters})
    print(destination)
    return 0


def crop_world(manifest: dict, path: Path, bounds: tuple[float, float, float, float]) -> Image.Image:
    left, right, bottom, top = bounds
    world = manifest["terrain"]
    size = float(world["worldSize"])
    with Image.open(path) as source:
        image = source.convert("RGB")
    x0 = round(left / size * image.width)
    x1 = round(right / size * image.width)
    y0 = round((size - top) / size * image.height)
    y1 = round((size - bottom) / size * image.height)
    return image.crop((x0, y0, x1, y1))


def comparison(args: argparse.Namespace) -> int:
    base = args.reference_root.resolve() / args.wrp_sha256[:16]
    overview = read_json(base / "overview" / "manifest.json")
    detail = read_json(base / "detail" / "manifest.json")
    bounds = tuple(args.bounds)
    size = float(overview["terrain"]["worldSize"])
    if not (0 <= bounds[0] < bounds[1] <= size and 0 <= bounds[2] < bounds[3] <= size):
        raise ValueError("comparison bounds must lie inside the terrain")
    destination = base / "comparison"
    if destination.exists():
        raise ValueError(f"refusing to overwrite existing comparison: {destination}")
    destination.mkdir()
    overview_master = base / "overview" / overview["rawMaster"]["path"]
    detail_master = base / "detail" / detail["rawMaster"]["path"]
    overview_crop = crop_world(overview, overview_master, bounds)
    detail_crop = crop_world(detail, detail_master, bounds)
    overview_crop.save(destination / "overview_same_area_native.png", "PNG")
    detail_crop.save(destination / "detail_same_area_native.png", "PNG")
    width = overview_crop.width + detail_crop.width
    height = HEADER_HEIGHT + max(overview_crop.height, detail_crop.height)
    combined = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(combined)
    draw.rectangle((0, 0, overview_crop.width, HEADER_HEIGHT), fill=HEADER)
    draw.rectangle((overview_crop.width, 0, width, HEADER_HEIGHT), fill=HEADER)
    draw.text((6, 7), f"OVERVIEW {overview['renderer']['scale']:.2f} | native {overview_crop.width}x{overview_crop.height}", fill=TEXT)
    draw.text((overview_crop.width + 6, 7), f"DETAIL {detail['renderer']['scale']:.2f} | native {detail_crop.width}x{detail_crop.height}", fill=TEXT)
    combined.paste(overview_crop, (0, HEADER_HEIGHT))
    combined.paste(detail_crop, (overview_crop.width, HEADER_HEIGHT))
    combined.save(destination / "overview_vs_detail_same_area.png", "PNG")
    shutil.copy2(base / "overview" / overview["preview"], destination / "overview_preview.jpg")
    shutil.copy2(base / "detail" / detail["preview"], destination / "detail_preview.jpg")
    write_json(destination / "comparison.json", {"worldBounds": {"left": bounds[0], "right": bounds[1], "bottom": bounds[2], "top": bounds[3]}, "resampling": "none; native crops only"})
    print(destination)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(required=True)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--reference-root", type=Path, required=True)
    shared.add_argument("--wrp-sha256", required=True)
    freeze_parser = sub.add_parser("freeze", parents=[shared])
    freeze_parser.add_argument("--session", type=Path, required=True)
    freeze_parser.add_argument("--name", choices=("overview", "detail"), required=True)
    freeze_parser.add_argument("--world-size", type=float, required=True)
    freeze_parser.set_defaults(func=freeze)
    index_parser = sub.add_parser("index", parents=[shared])
    index_parser.set_defaults(func=index)
    compare_parser = sub.add_parser("compare", parents=[shared])
    compare_parser.add_argument("--bounds", type=float, nargs=4, metavar=("LEFT", "RIGHT", "BOTTOM", "TOP"), required=True)
    compare_parser.set_defaults(func=comparison)
    return root


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.func(arguments))
