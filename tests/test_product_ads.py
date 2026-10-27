import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import product_ads as ads
from upload_youtube import publishing_text


def fixture():
    now = datetime.now(timezone.utc)
    return {
        "id": "test-only-reflector", "name": "測試反光吊牌", "market": "TW",
        "available": True, "affiliate_eligible": True,
        "affiliate_url": "https://s.shopee.tw/test-only-not-a-live-offer",
        "source": "synthetic-test-fixture-not-a-live-offer",
        "verified_at": now.isoformat(), "expires_at": (now+timedelta(hours=2)).isoformat(),
        "keywords": ["末班車", "深夜"], "benefit_zh": "背包上的日常小配件。",
    }


STORY = {"story_id": "test-story", "title_zh": "末班車", "title_en": "Last Bus",
         "story_zh": "深夜，末班車停在路邊。",
         "youtube": {"description_zh": "完整中文說明", "description_en": "Full description"}}


class ProductAdsTests(unittest.TestCase):
    def test_selects_relevant_product_instead_of_highest_commission(self):
        good, irrelevant = fixture(), fixture()
        irrelevant.update(id="irrelevant", keywords=["咖啡"], commission_rate=0.9)
        self.assertEqual(ads.select_offer(STORY, {"products": [irrelevant, good]})["id"], good["id"])

    def test_rejects_unverified_expired_and_wrong_market(self):
        now = datetime.now(timezone.utc)
        mutations = [{"affiliate_eligible": False}, {"available": False}, {"market": "BR"},
                     {"verified_at": (now-timedelta(hours=25)).isoformat()},
                     {"expires_at": (now-timedelta(seconds=1)).isoformat()},
                     {"affiliate_url": "https://example.com/item"},
                     {"verified_at": "2026-10-27T08:00:00"}, {"commission_rate": float("nan")}]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                product = fixture()
                product.update(mutation)
                with self.assertRaises(ValueError):
                    ads.select_offer(STORY, {"products": [product]})

    def test_pending_legacy_candidate_is_never_burned(self):
        story = dict(STORY, product_recommendation={"burn_into_zh_video": True,
                     "status": "candidate_pending_user_confirmation"})
        self.assertIsNone(ads.ad_for_language(story, "zh"))

    def test_ad_is_chinese_only_and_bound_to_story(self):
        ad = ads.make_ad(STORY, fixture())
        story = dict(STORY, product_ad=ad)
        self.assertIsNone(ads.ad_for_language(story, "en"))
        story["story_id"] = "different-story"
        with self.assertRaises(ValueError):
            ads.ad_for_language(story, "zh")

    def test_no_voiceover_or_invalid_duration_allowed(self):
        for change in [{"voiceover": True}, {"duration_seconds": 0},
                       {"duration_seconds": float("nan")}, {"duration_seconds": 13}]:
            ad = ads.make_ad(STORY, fixture())
            ad.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                ads.validate_ad(ad)

    def test_publishing_preserves_full_description_and_matches_product(self):
        ad = ads.make_ad(STORY, fixture())
        story = dict(STORY, product_ad=ad)
        qa = {"product_ad": {"enabled": True, "product_id": ad["product"]["id"]}}
        with patch.dict(os.environ, {"PRODUCT_AD_FILE": ""}):
            _, desc = publishing_text(story, "zh", qa)
            self.assertTrue(desc.startswith("完整中文說明"))
            self.assertIn(ad["product"]["affiliate_url"], desc)
            self.assertIn("可能獲得分潤", desc)
            _, en = publishing_text(story, "en", qa)
            self.assertEqual(en, "Full description")
            qa["product_ad"]["product_id"] = "different-product"
            with self.assertRaises(ValueError):
                publishing_text(story, "zh", qa)

    def test_ad_metadata_required_when_video_has_ad(self):
        with patch.dict(os.environ, {"PRODUCT_AD_FILE": ""}):
            with self.assertRaises(ValueError):
                publishing_text(STORY, "zh", {"product_ad": {"enabled": True}})

    def test_missing_feed_does_not_reuse_stale_output(self):
        with tempfile.TemporaryDirectory() as directory:
            story_path, out = Path(directory)/"story.json", Path(directory)/"ad.json"
            story_path.write_text(json.dumps(STORY), encoding="utf-8")
            out.write_text("yesterday")
            out.with_suffix(".png").write_text("yesterday")
            with patch.dict(os.environ, {"SHOPEE_AFFILIATE_FEED_URL": ""}), patch.object(
                    sys, "argv", ["product_ads", "--story", str(story_path), "--out", str(out)]):
                with self.assertRaises(ValueError):
                    ads.main()
            self.assertFalse(out.exists())
            self.assertFalse(out.with_suffix(".png").exists())

    def test_incomplete_font_cannot_publish_missing_glyph_boxes(self):
        from PIL import Image, ImageDraw
        incomplete = ads.ROOT / "assets/common/NotoSansTC.ttf"
        ads.font.cache_clear()
        with patch.dict(os.environ, {"PRODUCT_AD_FONT": str(incomplete)}):
            with self.assertRaisesRegex(ValueError, "missing characters"):
                ads.draw_text(ImageDraw.Draw(Image.new("RGB", (1080, 1920))), "測試反光吊牌", 300)
        ads.font.cache_clear()


if __name__ == "__main__":
    unittest.main()
