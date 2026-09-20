from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("generate-cloud-fields.py")
SPEC = importlib.util.spec_from_file_location("generate_cloud_fields", SCRIPT)
assert SPEC and SPEC.loader
GENERATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GENERATOR
SPEC.loader.exec_module(GENERATOR)


class CloudFieldTests(unittest.TestCase):
    def test_viewer_uses_persistent_layers_and_css_drift(self) -> None:
        source = (SCRIPT.parent.parent / "web" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("requestAnimationFrame", source)
        self.assertNotIn("cancelAnimationFrame", source)
        self.assertIn('L.DomUtil.create("div", "cloud-field__motion"', source)
        self.assertIn("if (!map.hasLayer(field)) field.addTo(map);", source)
        self.assertNotIn("map.removeLayer(field)", source)

    def test_generated_fields_have_soft_transparent_edges_and_neutral_empty_pixels(self) -> None:
        for spec in GENERATOR.FIELD_SPECS:
            image = GENERATOR.generate_field(spec)
            self.assertEqual(image.size, spec.size)
            self.assertEqual(image.mode, "RGBA")

            alpha = image.getchannel("A")
            self.assertIsNotNone(alpha.getbbox())
            self.assertGreater(alpha.getextrema()[1], 80)
            self.assertLessEqual(alpha.getextrema()[1], 172)
            self.assertNotEqual(alpha.getbbox(), (0, 0, image.width, image.height))

            corners = ((0, 0), (image.width - 1, 0), (0, image.height - 1), (image.width - 1, image.height - 1))
            for point in corners:
                self.assertEqual(image.getpixel(point), (0, 0, 0, 0))

            transparent_rgb = {
                pixel[:3]
                for pixel in image.get_flattened_data()
                if pixel[3] == 0
            }
            self.assertEqual(transparent_rgb, {(0, 0, 0)})

    def test_generation_is_deterministic(self) -> None:
        spec = GENERATOR.FIELD_SPECS[0]
        self.assertEqual(GENERATOR.generate_field(spec).tobytes(), GENERATOR.generate_field(spec).tobytes())


if __name__ == "__main__":
    unittest.main()
