import csv
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_ai_product import verify_selected_product

FIELDS = ("id","name","market","available","affiliate_eligible","affiliate_url","source","verified_at","expires_at","keywords","benefit_zh","commission_rate")

class VerifyAIProductTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.csv = Path(self.temp.name) / "products.csv"
        now = datetime.now(timezone.utc)
        self.row = dict(id="example",name="測試吊牌",market="TW",available="true",
            affiliate_eligible="true",affiliate_url="https://s.shopee.tw/test-link",
            source="operator-reviewed",verified_at=now.isoformat(),
            expires_at=(now+timedelta(hours=1)).isoformat(),
            keywords="夜路|深夜",benefit_zh="日常小配件",commission_rate="0.05")
        self.write_rows([self.row])

    def write_rows(self, rows):
        with self.csv.open("w",encoding="utf-8",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def selected(self):
        from import_affiliate_csv import convert
        return convert(self.csv)["products"][0]

    def test_exact_match(self):
        product=self.selected()
        self.assertEqual(verify_selected_product({"product":product},self.csv),product)

    def test_modified_link_rejected(self):
        product=self.selected()
        product["affiliate_url"]="https://s.shopee.tw/other"
        with self.assertRaisesRegex(ValueError,"differ"):
            verify_selected_product({"product":product},self.csv)

    def test_unlisted_id_rejected(self):
        product=self.selected()
        product["id"]="not-in-csv"
        with self.assertRaisesRegex(ValueError,"exactly once"):
            verify_selected_product({"product":product},self.csv)

    def test_duplicate_id_rejected(self):
        self.write_rows([self.row,self.row])
        with self.assertRaisesRegex(ValueError,"exactly once"):
            verify_selected_product({"product":self.selected()},self.csv)

    def test_unapproved_offer_rejected(self):
        self.row["affiliate_eligible"]="false"
        self.write_rows([self.row])
        with self.assertRaises(ValueError):
            verify_selected_product({"product":self.selected()},self.csv)

    def test_expired_offer_rejected(self):
        self.row["expires_at"]=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        self.write_rows([self.row])
        with self.assertRaises(ValueError):
            verify_selected_product({"product":self.selected()},self.csv)

if __name__ == "__main__":
    unittest.main()
