"""Fail closed unless an AI-selected product exactly matches the reviewed CSV."""
from pathlib import Path
from import_affiliate_csv import convert
from product_ads import validate_offer

def verify_selected_product(ad, csv_path: Path):
    if not isinstance(ad, dict) or not isinstance(ad.get("product"), dict):
        raise ValueError("AI product_ad.product is required")
    selected = ad["product"]
    products = convert(csv_path)["products"]
    matches = [p for p in products if p.get("id") == selected.get("id")]
    if len(matches) != 1:
        raise ValueError("Selected product ID must appear exactly once in reviewed CSV")
    approved = validate_offer(matches[0])
    if selected != approved:
        raise ValueError("AI product fields differ from reviewed CSV; do not publish")
    return approved
