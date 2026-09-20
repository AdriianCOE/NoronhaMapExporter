from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


@dataclass(frozen=True)
class FieldSpec:
    filename: str
    size: tuple[int, int]
    seed: int
    threshold: int
    ceiling: int
    streak_angle: float


FIELD_SPECS = (
    FieldSpec("cloud-system-1.webp", (2048, 1024), 7319, 118, 190, -7.0),
    FieldSpec("cloud-system-2.webp", (2048, 1024), 19421, 124, 194, 5.0),
    FieldSpec("cloud-system-3.webp", (1536, 768), 88217, 132, 188, -11.0),
)


def _noise(size: tuple[int, int], cells: tuple[int, int], rng: random.Random) -> Image.Image:
    width, height = cells
    source = Image.frombytes("L", (width, height), rng.randbytes(width * height))
    return source.resize(size, Image.Resampling.BICUBIC)


def _blend_octaves(
    size: tuple[int, int],
    octaves: tuple[tuple[tuple[int, int], float, int], ...],
    rng: random.Random,
) -> Image.Image:
    field = None
    total_weight = 0.0
    for cells, weight, blur in octaves:
        octave = _noise(size, cells, rng)
        if blur:
            octave = octave.filter(ImageFilter.GaussianBlur(blur))
        if field is None:
            field = octave
            total_weight = weight
            continue
        field = Image.blend(field, octave, weight / (total_weight + weight))
        total_weight += weight
    assert field is not None
    return field


def _fractal_noise(spec: FieldSpec) -> Image.Image:
    rng = random.Random(spec.seed)
    width, height = spec.size
    broad = _blend_octaves(
        spec.size,
        (
            ((10, 5), 0.46, 18),
            ((22, 11), 0.34, 9),
            ((48, 24), 0.20, 4),
        ),
        rng,
    )
    detail = _blend_octaves(
        spec.size,
        (
            ((48, 24), 0.38, 3),
            ((96, 48), 0.30, 1),
            ((192, 96), 0.21, 0),
            ((384, 192), 0.11, 0),
        ),
        rng,
    ).filter(ImageFilter.UnsharpMask(radius=3, percent=125, threshold=2))

    modulation = detail.point(lambda value: max(82, min(232, round(158 + (value - 128) * 1.35))))
    field = Image.blend(broad, ImageChops.multiply(broad, modulation), 0.40)

    # A stretched low-frequency pass creates weather-front wisps without
    # introducing a recognizable cloud silhouette.
    streak = _noise((width, max(16, height // 5)), (42, 5), rng)
    streak = streak.resize(spec.size, Image.Resampling.BICUBIC)
    streak = streak.rotate(spec.streak_angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=127)
    streak = streak.filter(ImageFilter.GaussianBlur(max(6, width // 220)))
    return Image.blend(field, streak, 0.17)


def _edge_feather(size: tuple[int, int]) -> Image.Image:
    width, height = size
    feather_x = max(1, int(width * 0.19))
    feather_y = max(1, int(height * 0.23))
    horizontal_values = []
    for x in range(width):
        value = min(1.0, x / feather_x, (width - 1 - x) / feather_x)
        horizontal_values.append(round(255 * value * value * (3.0 - 2.0 * value)))
    vertical_values = []
    for y in range(height):
        value = min(1.0, y / feather_y, (height - 1 - y) / feather_y)
        vertical_values.append(round(255 * value * value * (3.0 - 2.0 * value)))

    horizontal = Image.new("L", (width, 1))
    horizontal.putdata(horizontal_values)
    vertical = Image.new("L", (1, height))
    vertical.putdata(vertical_values)
    return ImageChops.multiply(
        horizontal.resize(size, Image.Resampling.NEAREST),
        vertical.resize(size, Image.Resampling.NEAREST),
    )


def generate_field(spec: FieldSpec) -> Image.Image:
    field = _fractal_noise(spec)
    span = max(1, spec.ceiling - spec.threshold)
    alpha = field.point(
        lambda value: 0
        if value <= spec.threshold
        else min(172, round(((value - spec.threshold) / span) ** 1.62 * 172))
    )
    opened = alpha.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    alpha = Image.blend(alpha, opened, 0.52)
    alpha = alpha.filter(ImageFilter.GaussianBlur(max(2, spec.size[0] // 900)))
    alpha = ImageChops.multiply(alpha, _edge_feather(spec.size))

    # Transparent pixels are neutral black, preventing colored fringe when the
    # browser interpolates the texture over dark or light map layers.
    luma = alpha.point(lambda value: 0 if value == 0 else min(252, 238 + value // 15))
    return Image.merge("RGBA", (luma, luma, luma, alpha))


def _composite_on(image: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    background = Image.new("RGBA", image.size, color)
    background.alpha_composite(image)
    return background.convert("RGB")


def write_qa_contact_sheet(fields: list[tuple[FieldSpec, Image.Image]], qa_dir: Path) -> None:
    qa_dir.mkdir(parents=True, exist_ok=True)
    preview_width = 720
    preview_height = 360
    sheet = Image.new("RGB", (preview_width * 2, preview_height * len(fields)), "#777777")
    for row, (spec, image) in enumerate(fields):
        preview = image.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
        black = _composite_on(preview, (0, 0, 0, 255))
        white = _composite_on(preview, (255, 255, 255, 255))
        black.save(qa_dir / f"{Path(spec.filename).stem}-black.jpg", quality=90)
        white.save(qa_dir / f"{Path(spec.filename).stem}-white.jpg", quality=90)
        sheet.paste(black, (0, row * preview_height))
        sheet.paste(white, (preview_width, row * preview_height))
    sheet.save(qa_dir / "cloud-fields-contact-sheet.jpg", quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic atmospheric cloud fields.")
    parser.add_argument("--output", type=Path, default=Path("web/assets"))
    parser.add_argument("--qa-dir", type=Path)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    generated: list[tuple[FieldSpec, Image.Image]] = []
    for spec in FIELD_SPECS:
        image = generate_field(spec)
        destination = args.output / spec.filename
        image.save(destination, "WEBP", lossless=False, quality=88, method=6, exact=True)
        generated.append((spec, image))
        print(f"{destination}: {image.width}x{image.height} ({destination.stat().st_size} bytes)")

    if args.qa_dir:
        write_qa_contact_sheet(generated, args.qa_dir)
        print(f"QA contact sheet: {args.qa_dir / 'cloud-fields-contact-sheet.jpg'}")


if __name__ == "__main__":
    main()
