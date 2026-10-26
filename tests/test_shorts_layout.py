"""Regression tests for vertical Shorts captions; no video rendering or uploads."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("make_video", ROOT / "scripts" / "make_video.py")
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class TestShortsTypography(unittest.TestCase):
    def test_zh_wrap_every_seventeen_characters(self):
        sentence = "凌晨兩點公車窗外出現了一個根本不應該存在的乘客還一直向我招手"
        lines = video.wrap_phrase(sentence, "zh").split(r"\N")
        self.assertEqual("".join(lines), sentence)
        self.assertTrue(all(len(line) <= 17 for line in lines))

    def test_english_wrap_without_loss(self):
        sentence = "The last bus never stopped at the terminal, although I pressed the bell."
        lines = video.wrap_phrase(sentence, "en").split(r"\N")
        self.assertTrue(all(len(line) <= 32 for line in lines))
        self.assertEqual(" ".join(lines), sentence)

    def test_long_caption_split_into_max_two_lines(self):
        text = "夜裡公車一直開過同一個站牌而那個沒有臉的乘客每一圈都坐得比我更近"
        data = {"segments": [{"zh": text, "en": "A shadow waited behind the glass."}]}
        rows = video.phrase_rows(data, "zh", 20)
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(len(s.split(r"\N")) <= 2 for _, _, s in rows))
        self.assertEqual("".join(s.replace(r"\N", "") for _, _, s in rows), text)
        self.assertAlmostEqual(rows[-1][1], 20)
        self.assertTrue(all(end > start for start, end, _ in rows))

    def test_ass_separate_title_and_narration_positions(self):
        data = {
            "title_zh": "不要替空房關電視",
            "title_en": "Never Turn Off That Television",
            "story_zh": "空房的電視裡有人叫出我的房號。",
            "story_en": "A voice from the TV said my room number.",
            "segments": [{"zh": "空房的電視裡有人叫出我的房號。", "en": "A voice from the TV said my room number."}],
            "en_promo": {"enabled": False}
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "zh.ass"
            video.write_ass(data, "zh", 67, 67, path)
            content = path.read_text(encoding="utf-8")
        self.assertIn("PlayResX: 1080", content)
        self.assertIn("PlayResY: 1920", content)
        self.assertIn(r"{\an5\pos(540,1010)}", content)
        self.assertIn(r"{\an5\pos(500,1280)}", content)
        self.assertIn("Style: Title,Noto Sans CJK TC,58,", content)
        self.assertIn("Style: Body,Noto Sans CJK TC,49,", content)
        self.assertIn("不要替空房關電視", content)

    def test_english_promo_kept_in_its_own_style(self):
        data = {
            "title_en": "The Last Bus",
            "story_en": "There was nobody driving.",
            "segments": [{"en": "There was nobody driving."}],
            "en_promo": {
                "enabled": True,
                "pause_seconds": 0.75,
                "voice_text": "Find English courses on our Instagram account.",
                "display_account": "IG @speakoutnow88",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "en.ass"
            video.write_ass(data, "en", 70, 78, path)
            content = path.read_text(encoding="utf-8")
        self.assertIn("PromoTitle", content)
        self.assertIn("IG @speakoutnow88", content)
        self.assertIn("English Course Promotion", content)


if __name__ == "__main__":
    unittest.main()
