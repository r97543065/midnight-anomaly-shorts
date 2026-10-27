"""Validate an AI-authored daily creative job and map it into the existing renderer."""
import argparse
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def asset_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Missing AI image path")
    path = (ROOT / value).resolve()
    if not path.is_relative_to((ROOT / "assets").resolve()) or not path.is_file():
        raise ValueError("AI image must exist inside assets/")
    with Image.open(path) as image:
        image.verify()
    return value

def apply_job(story, job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    if job.get("schema_version") != 1 or job.get("story_id") != story.get("story_id"):
        raise ValueError("AI job schema or story mismatch")
    scenes = job.get("scene_images")
    if not isinstance(scenes, list) or not 6 <= len(scenes) <= 8:
        raise ValueError("AI job requires 6-8 scene images")
    story["assets"]["images"] = [
        {"file": asset_path(scene["file"]), "effect": scene.get("effect", "slow_zoom")}
        for scene in scenes
    ]
    ad = job.get("product_ad")
    if ad is not None:
        if not isinstance(ad, dict):
            raise ValueError("Invalid product ad")
        if ad.get("enabled"):
            if job.get("publication_approved") is not True:
                raise ValueError("Ad approval required")
            asset_path(ad["card_image"])
            from product_ads import validate_ad
            validate_ad(ad, story)
        story["product_ad"] = ad
    return story

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--job", type=Path, default=Path("jobs/daily-ad-job.json"))
    p.add_argument("--story", type=Path, default=Path("stories/today.json"))
    args = p.parse_args()
    apply_job(json.loads(args.story.read_text(encoding="utf-8")), args.job)
    print("AI creative job validated")

if __name__ == "__main__":
    main()
