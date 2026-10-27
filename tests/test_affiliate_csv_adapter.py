import csv
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_affiliate_csv import convert
from build_product_candidate import generate

FIELDS = ["id", "name", "market", "available", "affiliate_eligible", "affiliate_url",
          "source", "verified_at", "expires_at", "keywords", "benefit_zh", "commission_rate"]

class AdapterTests(unittest.TestCase):
    def csv(self, folder, **changes):
        now = datetime.now(timezone.utc)
        item = dict(id="a", name="反光吊牌", market="TW", available="true",
                    affiliate_eligible="true", affiliate_url="https://s.shopee.tw/approved",
                    source="operator-approved-export", verified_at=now.isoformat(),
                    expires_at=(now+timedelta(hours=2)).isoformat(), keywords="末班車|深夜",
                    benefit_zh="日常配件", commission_rate="")
        item.update(changes)
        path = Path(folder)/"source.csv"
        with path.open("w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(item)
        return path

    def test_candidate_never_auto_approves(self):
        with tempfile.TemporaryDirectory() as d:
            result = generate({"story_id":"test", "title_zh":"末班車", "story_zh":"深夜末班車"}, self.csv(d))
            self.assertEqual(result["status"], "candidate_pending_user_confirmation")
            self.assertFalse(result["enabled"])
            self.assertFalse(result["publication_approved"])

    def test_no_assumed_eligibility(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.csv(d, affiliate_eligible="")
            with self.assertRaises(ValueError):
                convert(path)

    def test_expired_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.csv(d, verified_at="2020-01-01T00:00:00+00:00",
                            expires_at="2020-01-02T00:00:00+00:00")
            with self.assertRaises(ValueError):
                generate({"story_id":"test", "title_zh":"末班車", "story_zh":"深夜"}, path)

if __name__ == "__main__":
    unittest.main()
