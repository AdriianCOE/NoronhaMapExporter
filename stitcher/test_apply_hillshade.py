from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from stitcher.apply_hillshade import apply


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


if __name__ == "__main__":
    unittest.main()
