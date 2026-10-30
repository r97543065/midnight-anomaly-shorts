"""Regression tests for WebP/PNG/JPEG scene preparation."""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, features

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scene_images import prepare_scene_image


class SceneImageTests(unittest.TestCase):
    def test_supported_formats_create_1080p_proportionate_png_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for image_format, extension in (("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp")):
                if image_format == "WEBP" and not features.check("webp"):
                    self.skipTest("Pillow was built without WebP")
                with self.subTest(format=image_format):
                    source = root / ("source" + extension)
                    output = root / (image_format + "-frame.png")
                    Image.new("RGB", (160, 160), (80, 130, 200)).save(source, format=image_format)
                    prepare_scene_image(source, output, (108, 192))
                    with Image.open(output) as frame:
                        self.assertEqual(frame.format, "PNG")
                        self.assertEqual(frame.mode, "RGB")
                        self.assertEqual(frame.size, (108, 192))

    def test_transparency_is_composited_on_black_before_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "transparent.png", root / "frame.png"
            Image.new("RGBA", (10, 20), (255, 0, 0, 0)).save(source)
            prepare_scene_image(source, output, (108, 192))
            with Image.open(output) as frame:
                self.assertEqual(frame.getpixel((54, 96)), (0, 0, 0))

    def test_rejects_unsupported_gif(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "scene.gif", root / "frame.png"
            Image.new("RGB", (20, 20), "blue").save(source)
            with self.assertRaisesRegex(ValueError, "Unsupported scene image format"):
                prepare_scene_image(source, output, (108, 192))

    def test_rejects_zero_sized_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "scene.webp", root / "frame.png"
            Image.new("RGB", (20, 20)).save(source, format="WEBP")
            with self.assertRaisesRegex(ValueError, "dimensions must be positive"):
                prepare_scene_image(source, output, (0, 192))


if __name__ == "__main__":
    unittest.main()
