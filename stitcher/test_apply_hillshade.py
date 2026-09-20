from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from stitcher.apply_hillshade import COMPOSITION_ORDER, apply, coast_layers


class ApplyHillshadeTests(unittest.TestCase):
    def test_writes_derived_png_without_changing_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asc = root / "height.asc"
            asc.write_text("""ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 10\nNODATA_value -9999\n-10 20\n0 40\n""", encoding="utf-8")
            source = root / "master.png"
            Image.new("RGB", (8, 8), (200, 210, 220)).save(source)
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            output = root / "tourist.png"
            manifest = root / "manifest.json"
            result = apply(SimpleNamespace(heightmap=asc, master=source, output=output, manifest=manifest, world_size=20.0, sea_level=-2.0, opacity=0.225, elevation=40.0, slope_start=5.0, slope_full=30.0))
            self.assertTrue(output.is_file())
            self.assertTrue(manifest.is_file())
            with Image.open(output) as generated:
                self.assertEqual(generated.size, (8, 8))
            self.assertEqual(result["input2d"]["sha256"], original_hash)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_ocean_fill_uses_heightmap_land_mask_without_replacing_land(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asc = root / "height.asc"
            asc.write_text("""ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 10\n-10 20\n-10 20\n""", encoding="utf-8")
            source = root / "master.png"
            Image.new("RGB", (8, 8), (240, 230, 220)).save(source)
            output = root / "tourist.png"
            result = apply(SimpleNamespace(
                heightmap=asc, master=source, output=output, manifest=root / "manifest.json",
                world_size=20.0, sea_level=0.0, opacity=0.25, elevation=40.0,
                slope_start=5.0, slope_full=30.0, hillshade_enabled=False,
                ocean_enabled=True, ocean_color="#C9DEE9", coast_halo_color="#D7E8F0",
                coast_halo_width=0, coast_stroke_color="#A7BDC8", coast_stroke_width=0,
                slope_mask_enabled=False,
            ))
            with Image.open(output) as generated:
                self.assertEqual(generated.getpixel((0, 3)), (201, 222, 233))
                self.assertEqual(generated.getpixel((7, 3)), (240, 230, 220))
            self.assertEqual(result["compositionOrder"], COMPOSITION_ORDER)

    def test_coast_layers_keep_halo_on_water_and_stroke_on_shoreline(self) -> None:
        land = np.zeros((9, 9), dtype=np.float32)
        land[3:6, 3:6] = 1.0
        halo, stroke = coast_layers(land, halo_width=2, stroke_width=1)
        self.assertGreater(halo[2, 4], 0.0)
        self.assertEqual(halo[4, 4], 0.0)
        self.assertGreater(stroke[3, 4], 0.0)


if __name__ == "__main__":
    unittest.main()
