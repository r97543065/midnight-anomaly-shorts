"""Static regression checks for the optional low-volume ambient noise mix."""
import ast
import unittest
from pathlib import Path

CODE = Path(__file__).resolve().parents[1] / "scripts" / "make_video.py"

class AmbienceTests(unittest.TestCase):
    def test_script_parses(self):
        ast.parse(CODE.read_text(encoding="utf-8"))

    def test_optional_bed_is_present(self):
        source = CODE.read_text(encoding="utf-8")
        self.assertIn('MIDNIGHT_AMBIENCE_ENABLED', source)
        self.assertIn('anoisesrc=color=brown', source)
        self.assertIn('lowpass=f=650', source)
        self.assertIn('duration=first', source)
        self.assertIn('narration = add_horror_ambience(narration, temp)', source)

if __name__ == "__main__":
    unittest.main()
