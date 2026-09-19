from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from stitcher.stitch_map import stitch


class StitchMapTests(unittest.TestCase):
    def test_stitches_exact_world_crop_with_midpoint_overlaps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            session = Path(temp)
            captures = session / "captures"
            captures.mkdir()
            colours = {(0, 0): (255, 0, 0), (1, 0): (0, 255, 0), (0, 1): (0, 0, 255), (1, 1): (255, 255, 0)}
            tiles = []
            for grid_z in range(2):
                for grid_x in range(2):
                    left, bottom = grid_x * 40.0, grid_z * 40.0
                    right, top = left + 60.0, bottom + 60.0
                    filename = f"map_x{grid_x:02}_z{grid_z:02}.png"
                    Image.new("RGB", (60, 60), colours[(grid_x, grid_z)]).save(captures / filename)
                    tiles.append({
                        "index": len(tiles), "gridX": grid_x, "gridZ": grid_z, "filename": filename,
                        "bounds": {"left": left, "right": right, "bottom": bottom, "top": top},
                        "corners": {"topLeft": [left, bottom], "topRight": [right, bottom], "bottomLeft": [left, top], "bottomRight": [right, top]},
                        "metersPerPixel": {"x": 1.0, "z": 1.0},
                        "widget": {"x": 0, "y": 0, "width": 60, "height": 60},
                    })
            manifest = {
                "captureComplete": True, "valid": False, "validationMessage": "INVALID_COVERAGE",
                "worldBounds": {"left": 0, "right": 100, "bottom": 0, "top": 100},
                "grid": {"columns": 2, "rows": 2, "total": 4}, "tiles": tiles,
            }
            (session / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = stitch(session)
            self.assertEqual((result["width"], result["height"]), (100, 100))
            with Image.open(result["master"]) as master:
                self.assertEqual(master.getpixel((10, 10)), colours[(0, 0)])
                self.assertEqual(master.getpixel((90, 10)), colours[(1, 0)])
                self.assertEqual(master.getpixel((10, 90)), colours[(0, 1)])
                self.assertEqual(master.getpixel((90, 90)), colours[(1, 1)])

    def test_preserves_a_reversed_mapwidget_z_screen_axis(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            session = Path(temp)
            captures = session / "captures"
            captures.mkdir()
            tiles = []
            colours = {0: (220, 10, 10), 1: (10, 20, 220)}
            for grid_z in range(2):
                bottom, top = grid_z * 40.0, (grid_z * 40.0) + 60.0
                filename = f"map_x00_z{grid_z:02}.png"
                Image.new("RGB", (60, 60), colours[grid_z]).save(captures / filename)
                tiles.append({
                    "index": grid_z, "gridX": 0, "gridZ": grid_z, "filename": filename,
                    "bounds": {"left": 0, "right": 60, "bottom": bottom, "top": top},
                    "corners": {"topLeft": [0, top], "topRight": [60, top], "bottomLeft": [0, bottom], "bottomRight": [60, bottom]},
                    "metersPerPixel": {"x": 1.0, "z": 1.0},
                    "widget": {"x": 0, "y": 0, "width": 60, "height": 60},
                })
            manifest = {
                "captureComplete": True, "valid": True, "validationMessage": "PASS",
                "worldBounds": {"left": 0, "right": 60, "bottom": 0, "top": 100},
                "grid": {"columns": 1, "rows": 2, "total": 2}, "tiles": tiles,
            }
            (session / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = stitch(session)
            self.assertEqual(result["zScreenDirection"], "decreases-down")
            with Image.open(result["master"]) as master:
                self.assertEqual(master.getpixel((10, 10)), colours[1])
                self.assertEqual(master.getpixel((10, 90)), colours[0])


if __name__ == "__main__":
    unittest.main()
