import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from post_affiliate_comment import comment_text, post_comment


def fixture():
    now = datetime.now(timezone.utc)
    return {
        "enabled": True, "status": "verified", "language": "zh",
        "story_id": "story", "duration_seconds": 8, "voiceover": False,
        "product": {
            "id": "P0005", "name": "測試貼", "market": "TW", "available": True,
            "affiliate_eligible": True, "affiliate_url": "https://s.shopee.tw/example",
            "source": "user-reviewed", "verified_at": now.isoformat(),
            "expires_at": (now+timedelta(days=2)).isoformat(),
            "keywords": ["手機"], "benefit_zh": "使用者提供",
        },
        "headline": "故事後選物", "ad_copy_zh": "歡迎看看",
        "slogan": "別回頭", "cta": "留言有連結",
        "disclosure": "商品推廣｜透過連結購買，我可能獲得分潤",
    }


class CommentTests(unittest.TestCase):
    def test_comment_contains_link_and_disclosure(self):
        comment = comment_text(fixture())
        self.assertIn("https://s.shopee.tw/example", comment)
        self.assertIn("商品推廣", comment)
        self.assertIn("分潤", comment)

    @patch("post_affiliate_comment.youtube_json")
    def test_private_video_rejected_without_comment(self, request):
        request.return_value = {"items": [{
            "snippet": {"channelId": "UCoJaSnd5EybHJEJ47Q5aZdQ"},
            "status": {"privacyStatus": "private"}}]}
        with self.assertRaisesRegex(ValueError, "Private"):
            post_comment("12345678901", fixture(), "fake-token")
        self.assertEqual(request.call_count, 1)

    @patch("post_affiliate_comment.youtube_json")
    def test_retry_does_not_duplicate_comment(self, request):
        ad = fixture()
        request.side_effect = [
            {"items": [{"snippet": {"channelId": "UCoJaSnd5EybHJEJ47Q5aZdQ"},
                         "status": {"privacyStatus": "unlisted"}}]},
            {"items": [{"snippet": {"topLevelComment": {"snippet": {"textOriginal": comment_text(ad)}}}}]}
        ]
        self.assertEqual(post_comment("12345678901", ad, "fake-token"), "already_present")
        self.assertEqual(request.call_count, 2)

    @patch("post_affiliate_comment.youtube_json")
    def test_new_comment_posted_after_video_review(self, request):
        request.side_effect = [
            {"items": [{"snippet": {"channelId": "UCoJaSnd5EybHJEJ47Q5aZdQ"},
                         "status": {"privacyStatus": "public"}}]},
            {"items": []},
            {"id": "comment-thread-id"}
        ]
        self.assertEqual(post_comment("12345678901", fixture(), "fake-token"), "comment-thread-id")
        self.assertEqual(request.call_count, 3)


if __name__ == "__main__":
    unittest.main()
