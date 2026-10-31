import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_visual_approval as gate


class ImageReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.story_id = "approved_episode_123"
        self.episode_id = "2026-11-01-approved"
        self.images = []
        self.checks = []
        for i in range(6):
            name = f"assets/scene{i+1:02d}.webp"
            content = b"WEBP_test_" + bytes([i])
            p = self.root / name
            p.write_bytes(content)
            self.images.append({"file": name})
            self.checks.append({"file": name, "sha256": hashlib.sha256(content).hexdigest()})
        self.story = self.root / "story.json"
        self.story.write_text(json.dumps({
            "story_id": self.story_id, "episode_id": self.episode_id,
            "assets": {"images": self.images}
        }))
        self.review = self.root / "review.json"
        self.review.write_text(json.dumps({
            "story_id": self.story_id, "episode_id": self.episode_id,
            "visual_review_approved": True, "images": self.checks
        }))
        self.root_patch = patch.object(gate, "ROOT", self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_missing_approval_rejected(self):
        self.review.unlink()
        with self.assertRaises(PermissionError):
            gate.check_approval(self.story, self.review, self.story_id)

    def test_same_episode_exact_hashes_accepted(self):
        result = gate.check_approval(self.story, self.review, self.story_id)
        self.assertTrue(result["visual_review_approved"])

    def test_changed_image_after_approval_rejected(self):
        (self.root / self.images[0]["file"]).write_bytes(b"different")
        with self.assertRaisesRegex(PermissionError, "changed since human review"):
            gate.check_approval(self.story, self.review, self.story_id)

    def test_previous_episode_approval_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            gate.check_approval(self.story, self.review, "another_episode_123")

    def test_fewer_approved_images_rejected(self):
        review = json.loads(self.review.read_text())
        review["images"] = review["images"][:-1]
        self.review.write_text(json.dumps(review))
        with self.assertRaisesRegex(PermissionError, "EVERY image"):
            gate.check_approval(self.story, self.review, self.story_id)

    def test_approval_flag_not_true_rejected(self):
        review = json.loads(self.review.read_text())
        review["visual_review_approved"] = False
        self.review.write_text(json.dumps(review))
        with self.assertRaises(PermissionError):
            gate.check_approval(self.story, self.review, self.story_id)


if __name__ == "__main__":
    unittest.main()
