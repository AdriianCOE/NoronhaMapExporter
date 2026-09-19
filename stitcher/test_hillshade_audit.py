from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from stitcher.hillshade_audit import AscGrid, HillshadeError, blend_luminance, parse_asc, slope_weight_from_degrees, surface_hillshade, valid_land_mask, validate_extent, world_bounds_to_image_box


class HillshadeAuditTests(unittest.TestCase):
    def write_asc(self, text: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "height.asc"
        path.write_text(text, encoding="utf-8")
        return path

    def test_parses_header_and_nodata(self) -> None:
        path = self.write_asc("""ncols 3\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 10\nNODATA_value -9999\n-9999 5 6\n7 8 9\n""")
        grid = parse_asc(path)
        self.assertEqual((grid.ncols, grid.nrows), (3, 2))
        self.assertEqual(grid.nodata_value, -9999)
        self.assertFalse(valid_land_mask(grid, sea_level=0)[0, 0])

    def test_rejects_malformed_data_dimensions(self) -> None:
        path = self.write_asc("""ncols 3\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 10\n1 2\n3 4\n""")
        with self.assertRaises(HillshadeError):
            parse_asc(path)

    def test_rejects_extent_mismatch(self) -> None:
        path = self.write_asc("""ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 10\n1 2\n3 4\n""")
        with self.assertRaises(HillshadeError):
            validate_extent(parse_asc(path), 10240)

    def test_hillshade_is_deterministic(self) -> None:
        grid = AscGrid(Path("synthetic.asc"), 3, 3, 0, 0, "xllcorner", "yllcorner", 10, None, np.array([[3, 2, 1], [2, 1, 0], [1, 0, -1]], dtype=np.float32))
        first = surface_hillshade(grid, 315, 40)
        second = surface_hillshade(grid, 315, 40)
        np.testing.assert_array_equal(first, second)

    def test_orientation_world_bounds(self) -> None:
        self.assertEqual(world_bounds_to_image_box((0, 0, 10240, 10240), 10240, (9600, 9600)), (0, 0, 9600, 9600))
        self.assertEqual(world_bounds_to_image_box((6776, 6624, 8824, 7776), 10240, (9600, 9600)), (6352.5, 2310.0, 8272.5, 3390.0))

    def test_ocean_is_unchanged_by_luminance_blend(self) -> None:
        base = np.array([[[20, 40, 60], [30, 50, 70]]], dtype=np.uint8)
        shade = np.array([[0.0, 1.0]], dtype=np.float32)
        land = np.array([[0.0, 1.0]], dtype=np.float32)
        blended = blend_luminance(base, shade, land, 0.2)
        np.testing.assert_array_equal(blended[0, 0], base[0, 0])
        self.assertFalse(np.array_equal(blended[0, 1], base[0, 1]))

    def test_slope_weight_leaves_flat_ground_neutral(self) -> None:
        weights = slope_weight_from_degrees(np.array([0.0, 5.0, 17.5, 30.0, 45.0], dtype=np.float32), 5, 30)
        np.testing.assert_allclose(weights, np.array([0.0, 0.0, 0.5, 1.0, 1.0], dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
