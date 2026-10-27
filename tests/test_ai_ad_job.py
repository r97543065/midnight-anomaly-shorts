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

    def test_missing_image_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "job.json"
            path.write_text(json.dumps({"schema_version": 1, "story_id": "s",
                "scene_images": [{"file": "assets/missing-ai-scene.png"}] * 6}))
            with self.assertRaisesRegex(ValueError, "inside assets"):
                apply_job({"story_id": "s", "assets": {"images": []}}, path)

if __name__ == "__main__":
    unittest.main()
