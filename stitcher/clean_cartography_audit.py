#!/usr/bin/env python3
"""Collect and compare isolated DayZ clean-cartography style captures.

This never resamples, feature-matches, or edits source captures.  It copies a
validated capture from a completed automatic detail-audit session, records its
runtime metadata, and composes only labeled native-pixel comparison sheets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw


HEADER_HEIGHT = 28
BACKGROUND = (24, 24, 24)
HEADER_BACKGROUND = (48, 48, 48)
TEXT = (240, 240, 240)
EXPECTED_CAPTURE_NAMES = {
    "00-raw": "clean_test_00_raw.png",
    "01-no-grid": "clean_test_01_no_grid.png",
    "02-no-labels": "clean_test_02_no_labels.png",
    "03-no-icons": "clean_test_03_no_icons.png",
    "04-reduced-vegetation": "clean_test_04_reduced_vegetation.png",
    "05-soft-contours": "clean_test_05_soft_contours.png",
    "06-palette": "clean_test_06_palette.png",
    "10-combined-v1": "clean_test_10_combined_v1.png",
    "v1-detail-015": "clean_test_v1_detail_015.png",
    "v1-overview-033": "clean_test_v1_overview_033.png",
}
CATEGORY_ORDER = list(EXPECTED_CAPTURE_NAMES)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def completed_detail_audit(session: Path) -> dict:
    manifest = load_json(session / "manifest.json")
    if manifest.get("mode") != "detail-audit":
        raise ValueError(f"{session} is not a detail-audit session")
    if not manifest.get("captureComplete") or not manifest.get("valid"):
        raise ValueError(f"{session} is incomplete or failed validation")
    return manifest


def matching_tile(manifest: dict, target_scale: float) -> dict:
    matches = [
        tile for tile in manifest.get("tiles", [])
        if math.isclose(float(tile.get("getScale", -1)), target_scale, abs_tol=0.0001)
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one capture at scale {target_scale:.2f}, found {len(matches)}")
    return matches[0]


def validated_png(session: Path, tile: dict) -> tuple[Path, Image.Image, str]:
    source = session / "captures" / tile["filename"]
    if not source.is_file():
        raise ValueError(f"missing capture: {source}")
    actual_hash = sha256(source)
    png = tile.get("png", {})
    if actual_hash != png.get("sha256"):
        raise ValueError(f"SHA256 mismatch for {source.name}")
    with Image.open(source) as opened:
        if source.suffix.lower() != ".png" or opened.format != "PNG" or opened.mode != "RGB":
            raise ValueError(f"{source.name} must be an opaque RGB PNG, got {opened.format}/{opened.mode}")
        if opened.size != (png.get("width"), png.get("height")):
            raise ValueError(f"dimension mismatch for {source.name}")
        return source, opened.copy(), actual_hash


def load_report(path: Path) -> dict:
    if not path.is_file():
        return {"version": 1, "captures": {}, "artifacts": {}}
    return load_json(path)


def raw_reference_hashes(reference_root: Path | None) -> dict | None:
    if reference_root is None:
        return None
    masters = load_json(reference_root / "masters.json")
    result = {}
    for name in ("overview", "detail"):
        item = masters.get(name)
        if not item:
            raise ValueError(f"masters.json has no {name} reference")
        output = reference_root / item["path"]
        actual = sha256(output)
        expected = item["sha256"]
        if actual != expected:
            raise ValueError(f"immutable RAW {name} master changed: {actual} != {expected}")
        result[name] = {
            "path": str(output),
            "sha256": actual,
            "dimensions": {"width": item.get("width"), "height": item.get("height")},
        }
    return result


def header(canvas: Image.Image, x: int, y: int, width: int, text: str) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x, y, x + width - 1, y + HEADER_HEIGHT - 1), fill=HEADER_BACKGROUND)
    draw.text((x + 6, y + 7), text, fill=TEXT)


def native_grid(audit_dir: Path, captures: dict) -> str | None:
    items = []
    for capture_id in CATEGORY_ORDER:
        item = captures.get(capture_id)
        if not item:
            continue
        path = audit_dir / item["filename"]
        with Image.open(path) as image:
            items.append((capture_id, item, image.copy()))
    if not items:
        return None
    cell_width = max(image.width for _, _, image in items)
    cell_height = max(image.height for _, _, image in items) + HEADER_HEIGHT
    columns = 2
    rows = math.ceil(len(items) / columns)
    canvas = Image.new("RGB", (cell_width * columns, cell_height * rows), BACKGROUND)
    for index, (capture_id, item, image) in enumerate(items):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        header(canvas, x, y, cell_width, f"{item['filename']} | {item['scale']:.2f} | native {image.width}x{image.height}")
        canvas.paste(image, (x, y + HEADER_HEIGHT))
    output = audit_dir / "comparison_all.png"
    canvas.save(output, format="PNG", optimize=False)
    return output.name


def raw_vs_clean(audit_dir: Path, captures: dict) -> str | None:
    raw = captures.get("00-raw")
    clean = captures.get("v1-detail-015") or captures.get("10-combined-v1")
    if not raw or not clean:
        return None
    with Image.open(audit_dir / raw["filename"]) as raw_image, Image.open(audit_dir / clean["filename"]) as clean_image:
        if raw_image.size != clean_image.size:
            raise ValueError("raw and clean detail frames have different dimensions")
        canvas = Image.new("RGB", (raw_image.width + clean_image.width, raw_image.height + HEADER_HEIGHT), BACKGROUND)
        header(canvas, 0, 0, raw_image.width, "RAW reference | native pixels")
        header(canvas, raw_image.width, 0, clean_image.width, "Clean V1 | native pixels")
        canvas.paste(raw_image, (0, HEADER_HEIGHT))
        canvas.paste(clean_image, (raw_image.width, HEADER_HEIGHT))
    output = audit_dir / "raw_vs_clean_v1.png"
    canvas.save(output, format="PNG", optimize=False)
    return output.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True, help="completed automatic detail-audit session")
    parser.add_argument("--capture", choices=CATEGORY_ORDER, required=True, help="named audit capture to collect")
    parser.add_argument("--scale", type=float, required=True, help="expected MapWidget scale in this session")
    parser.add_argument("--audit-dir", type=Path, required=True, help="clean-cartography-audit output directory")
    parser.add_argument("--reference-root", type=Path, help="immutable RAW reference root containing masters.json")
    parser.add_argument("--replace", action="store_true", help="replace the named audit capture after validating it")
    args = parser.parse_args()

    session = args.session.resolve()
    audit_dir = args.audit_dir.resolve()
    reference_root = args.reference_root.resolve() if args.reference_root else None
    manifest = completed_detail_audit(session)
    tile = matching_tile(manifest, args.scale)
    source, image, digest = validated_png(session, tile)
    audit_dir.mkdir(parents=True, exist_ok=True)
    report_path = audit_dir / "audit.json"
    report = load_report(report_path)
    captures = report.setdefault("captures", {})
    destination_name = EXPECTED_CAPTURE_NAMES[args.capture]
    destination = audit_dir / destination_name
    if (args.capture in captures or destination.exists()) and not args.replace:
        raise ValueError(f"{destination_name} already exists; use --replace only for a controlled retest")
    shutil.copy2(source, destination)
    copied_hash = sha256(destination)
    if copied_hash != digest:
        raise ValueError(f"copy verification failed for {destination_name}")

    captures[args.capture] = {
        "filename": destination_name,
        "sourceFilename": source.name,
        "sessionDirectory": str(session),
        "sessionId": manifest.get("sessionId"),
        "requestId": tile.get("requestId"),
        "scale": tile.get("getScale"),
        "targetScale": tile.get("targetScale"),
        "requestedCenter": tile.get("requestedCenter"),
        "actualCenter": tile.get("actualCenter"),
        "bounds": tile.get("bounds"),
        "metersPerPixel": tile.get("metersPerPixel"),
        "dimensions": tile.get("png"),
        "sha256": copied_hash,
        "format": "PNG/RGB/lossless",
    }
    report["version"] = 1
    report["world"] = manifest.get("world")
    report["captureContract"] = "automatic CAPTURE_READY -> helper PNG -> ACK; no resampling or feature matching"
    report["expectedCaptures"] = EXPECTED_CAPTURE_NAMES
    report["rawReferences"] = raw_reference_hashes(reference_root)
    report.setdefault("notes", {})["runtimeConfigSource"] = "DayZ MapDefaults is runtime-provided; candidate fields are accepted or rejected by this exact client during the isolated audit."
    artifacts = report.setdefault("artifacts", {})
    artifacts["comparisonAll"] = native_grid(audit_dir, captures)
    artifacts["rawVsCleanV1"] = raw_vs_clean(audit_dir, captures)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Collected {destination_name}: SHA256 {copied_hash}")
    print(f"Audit report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
