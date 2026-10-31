#!/usr/bin/env python3
"""Build a non-publishing ad candidate from a manually refreshed CSV."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from import_affiliate_csv import convert
from product_ads import select_offer, make_ad

def generate(story: dict, csv_file: Path) -> dict:
    # No 24-hour age limit; the declared expiry and eligibility still apply.
    # Candidate selection is not permission to render an ad or upload videos.
    product = select_offer(story, convert(csv_file))
    ad = make_ad(story, product)
    # A verified offer is NOT authorization to use the ad in a video.
    ad["enabled"] = False
    ad["status"] = "candidate_pending_user_confirmation"
    ad["burn_into_zh_video"] = False
    ad["publication_approved"] = False
    ad["source_story_id"] = story["story_id"]
    return ad

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--story", type=Path, default=Path("stories/today.json"))
    parser.add_argument("--csv", type=Path, default=Path("data/affiliate/reviewed-products.csv"))
    parser.add_argument("--out", type=Path, default=Path("output/candidate-product-ad.json"))
    args = parser.parse_args()
    args.out.unlink(missing_ok=True)  # No stale candidate on failure.
    story = json.loads(args.story.read_text(encoding="utf-8"))
    try:
        candidate = generate(story, args.csv)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "status": "blocked_no_verified_offer",
            "story_id": story.get("story_id"),
            "reason": str(exc),
            "publication_approved": False,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("BLOCKED: " + str(exc))
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Candidate only; no MP4 render, YouTube upload, or approval.")

if __name__ == "__main__":
    main()
