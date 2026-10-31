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

    def test_rainy_bus_story_matches_umbrella_context(self):
        rainy = dict(STORY, title_zh="末班車", story_zh="手機收到照片，拍照的人站在車外的雨裡。")
        umbrella = fixture()
        umbrella.update(id="umbrella", keywords=["下雨", "夜晚"])
        camera = fixture()
        camera.update(id="camera", keywords=["咖啡"])
        self.assertEqual(ads.select_offer(rainy, {"products": [camera, umbrella]})["id"], "umbrella")

    def test_exact_keyword_beats_context_only(self):
        story = dict(STORY, story_zh="雨裡的末班車停在我面前")
        exact, contextual = fixture(), fixture()
        exact.update(id="exact", keywords=["末班車"])
        contextual.update(id="context", keywords=["下雨"])
        self.assertEqual(ads.select_offer(story, {"products": [contextual, exact]})["id"], "exact")

    def test_unrelated_story_fails_closed(self):
        story = dict(STORY, title_zh="空白", story_zh="一個安靜的房間")
        unrelated = fixture()
        unrelated.update(keywords=["下雨", "相機"])
        with self.assertRaises(ValueError):
            ads.select_offer(story, {"products": [unrelated]})

    def test_rejects_unverified_expired_and_wrong_market(self):
        now = datetime.now(timezone.utc)
        mutations = [{"affiliate_eligible": False}, {"available": False}, {"market": "BR"},
                     {"expires_at": (now-timedelta(seconds=1)).isoformat()},
                     {"verified_at": (now+timedelta(minutes=10)).isoformat()},
                     {"expires_at": (now-timedelta(minutes=1)).isoformat(), "verified_at": (now-timedelta(days=1)).isoformat()},
                     {"affiliate_url": "https://example.com/item"},
                     {"verified_at": "2026-10-27T08:00:00"}, {"commission_rate": float("nan")}]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                product = fixture()
                product.update(mutation)
                with self.assertRaises(ValueError):
                    ads.select_offer(STORY, {"products": [product]})

    def test_old_but_unexpired_offer_is_accepted_without_24h_limit(self):
        now = datetime.now(timezone.utc)
        old = fixture()
        old["verified_at"] = (now-timedelta(days=30)).isoformat()
        old["expires_at"] = (now+timedelta(days=30)).isoformat()
        self.assertEqual(ads.validate_offer(old), old)
        self.assertEqual(ads.select_offer(STORY, {"products": [old]})["id"], old["id"])
        ad = ads.make_ad(STORY, old)
        story = dict(STORY, product_ad=ad)
        self.assertIsNotNone(ads.ad_for_language(story, "zh"))
        qa = {"product_ad": {"enabled": True, "product_id": old["id"],
                             "affiliate_url": old["affiliate_url"],
                             "verified_at": old["verified_at"]}}
        with patch.dict(os.environ, {"PRODUCT_AD_FILE": ""}):
            _, desc = publishing_text(story, "zh", qa)
            self.assertIn(old["affiliate_url"], desc)

    def test_ad_card_shows_promotion_label_not_commission_copy(self):
        ad = ads.make_ad(STORY, fixture())
        with tempfile.TemporaryDirectory() as directory, patch.object(ads, "draw_text", side_effect=lambda draw, content, y, *args, **kwargs: y+70) as spy:
            ads.render_card(ad, Path(directory)/"ad.png")
        displayed = [call.args[1] for call in spy.call_args_list]
        self.assertIn("商品推廣", displayed)
        self.assertFalse(any("分潤" in label for label in displayed))

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
        qa = {"product_ad": {"enabled": True, "product_id": ad["product"]["id"], "affiliate_url": ad["product"]["affiliate_url"], "verified_at": ad["product"]["verified_at"]}}
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

    def test_delayed_upload_fails_closed_even_when_snapshot_matches(self):
        from datetime import datetime, timedelta, timezone
        old = fixture()
        old["verified_at"] = (datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
        old["expires_at"] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        ad = ads.make_ad(STORY, old)
        story = dict(STORY, product_ad=ad)
        qa = {"product_ad": {"enabled": True, "product_id": old["id"],
                             "affiliate_url": old["affiliate_url"], "verified_at": old["verified_at"]}}
        with patch.dict(os.environ, {"PRODUCT_AD_FILE": ""}):
            with self.assertRaisesRegex(ValueError, "refuse upload"):
                publishing_text(story, "zh", qa)
        # Historical snapshot can still be read, without treating it as fresh.
        self.assertIsNotNone(ads.ad_for_language(story, "zh", historical_snapshot=True))

    def test_changed_affiliate_link_is_rejected(self):
        ad = ads.make_ad(STORY, fixture())
        story = dict(STORY, product_ad=ad)
        qa = {"product_ad": {"enabled": True, "product_id": ad["product"]["id"],
                             "affiliate_url": "https://s.shopee.tw/different",
                             "verified_at": ad["product"]["verified_at"]}}
        with patch.dict(os.environ, {"PRODUCT_AD_FILE": ""}):
            with self.assertRaisesRegex(ValueError, "link does not match"):
                publishing_text(story, "zh", qa)

    def test_ad_metadata_required_when_video_has_ad(self):
        with patch.dict(os.environ, {"PRODUCT_AD_FILE": ""}):
            with self.assertRaises(ValueError):
                publishing_text(STORY, "zh", {"product_ad": {"enabled": True}})

    def test_long_product_card_copy_fails_safe_area(self):
        from PIL import Image, ImageDraw
        with self.assertRaisesRegex(ValueError, "safe area"):
            ads.draw_text(ImageDraw.Draw(Image.new("RGB", (1080, 1920))),
                          "測試", 1800, size=48)

    def test_excessively_long_product_name_is_rejected(self):
        ad = ads.make_ad(STORY, fixture())
        ad["product"]["name"] = "很長的反光商品名稱" * 20
        with self.assertRaises(ValueError):
            ads.validate_ad(ad)

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
