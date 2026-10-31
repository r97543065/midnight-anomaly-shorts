import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ai_ad_job import apply_job

class AIJobTests(unittest.TestCase):
    def test_story_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "job.json"
            path.write_text(json.dumps({"schema_version": 1, "story_id": "wrong", "scene_images": []}))
            with self.assertRaisesRegex(ValueError, "mismatch"):
                apply_job({"story_id": "today"}, path)

    def test_no_unapproved_ad(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "job.json"
            path.write_text(json.dumps({"schema_version": 1, "story_id": "s",
                "scene_images": [{"file": "assets/does-not-exist.png"}] * 6,
                "product_ad": {"enabled": True}, "publication_approved": False}))
            with self.assertRaises(ValueError):
                apply_job({"story_id": "s", "assets": {"images": []}}, path)

    def test_ad_preview_does_not_require_publication_approval(self):
        from unittest.mock import patch
        from ai_ad_job import apply_job
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "job.json"
            ad = {"enabled": True, "product": {"id": "fixture"}}
            path.write_text(json.dumps({
                "schema_version": 1, "story_id": "preview",
                "publication_approved": False,
                "scene_images": [{"file": "assets/test.webp"}] * 6,
                "product_ad": ad
            }), encoding="utf-8")
            with patch("ai_ad_job.asset_path", side_effect=lambda p: p), \
                 patch("verify_ai_product.verify_selected_product", return_value=ad["product"]), \
                 patch("product_ads.validate_ad", return_value=ad):
                result = apply_job({"story_id": "preview", "assets": {"images": []}}, path)
            self.assertTrue(result["product_ad"]["enabled"])
            self.assertFalse(json.loads(path.read_text())["publication_approved"])

    def test_missing_image_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "job.json"
            path.write_text(json.dumps({"schema_version": 1, "story_id": "s",
                "scene_images": [{"file": "assets/missing-ai-scene.png"}] * 6}))
            with self.assertRaisesRegex(ValueError, "inside assets"):
                apply_job({"story_id": "s", "assets": {"images": []}}, path)

if __name__ == "__main__":
    unittest.main()
