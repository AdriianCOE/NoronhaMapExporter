from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).with_name("build-map-demo.py")
SPEC = importlib.util.spec_from_file_location("build_map_demo", SCRIPT)
assert SPEC and SPEC.loader
BUILD_MAP_DEMO = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BUILD_MAP_DEMO
SPEC.loader.exec_module(BUILD_MAP_DEMO)


class BuildMapDemoTests(unittest.TestCase):
    def test_full_resolution_tiles_reconstruct_the_source_without_rotation_or_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "master.png"
            image = Image.new("RGB", (600, 400))
            pixels = image.load()
            for y in range(image.height):
                for x in range(image.width):
                    pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
            image.save(source)
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            result = BUILD_MAP_DEMO.build_layer(
                BUILD_MAP_DEMO.LayerInput("tourist", "Tourist", source), root / "tiles", 256, 90, (0, 0, 600, 400)
            )
            self.assertEqual(result["maxZoom"], 2)
            self.assertEqual(result["tiles"], 9)
            self.assertEqual(result["revision"], original_hash[:12])
            self.assertEqual(result["initialBounds"], [0, 0, 600, 400])
            self.assertEqual((result["sourceWidth"], result["sourceHeight"]), (600, 400))

            generated_tiles = list((root / "tiles").rglob("*.webp"))
            self.assertEqual(len(generated_tiles), result["tiles"])
            for tile_path in generated_tiles:
                with Image.open(tile_path) as tile:
                    self.assertEqual(tile.size, (256, 256))

            tile_root = root / "tiles" / "tourist" / result["revision"]
            with Image.open(tile_root / "2" / "2" / "1.webp") as edge_tile:
                self.assertEqual(edge_tile.convert("RGBA").getpixel((88, 144))[3], 0)

            reconstruction = Image.new("RGB", image.size)
            for column in range(3):
                for row in range(2):
                    tile_path = tile_root / "2" / str(column) / f"{row}.webp"
                    with Image.open(tile_path) as tile:
                        reconstruction.paste(tile.convert("RGB"), (column * 256, row * 256))
            self.assertEqual(reconstruction.tobytes(), image.tobytes())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_secondary_layer_can_be_normalized_to_the_primary_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "satmap.png"
            Image.new("RGB", (640, 480), "navy").save(source)

            result = BUILD_MAP_DEMO.build_layer(
                BUILD_MAP_DEMO.LayerInput("satmap", "SatMap", source),
                root / "tiles",
                256,
                90,
                (0, 0, 600, 400),
                (600, 400),
            )

            self.assertEqual((result["sourceWidth"], result["sourceHeight"]), (640, 480))
            self.assertEqual((result["width"], result["height"]), (600, 400))
            self.assertEqual(result["initialBounds"], [0, 0, 600, 400])


if __name__ == "__main__":
    unittest.main()
