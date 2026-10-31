#!/usr/bin/env python3
"""Require an explicit, episode-specific image-review record with exact image hashes.

This is a CI integrity gate, not a substitute for showing the actual images
in the ChatGPT conversation and obtaining real human approval BEFORE upload.
No approval manifests are issued automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORY_ID = re.compile(r"^[A-Za-z0-9_-]{5,100}$")


def check_approval(story_path: Path, manifest_path: Path, story_id: str) -> dict:
    if not STORY_ID.fullmatch(story_id):
        raise ValueError("Invalid story ID")
    story = json.loads(story_path.read_text(encoding="utf-8"))
    if story.get("story_id") != story_id:
        raise ValueError("Reviewed story ID does not match story being rendered")
    if not manifest_path.is_file():
        raise PermissionError("Image review is missing: show EVERY image to the user BEFORE GitHub upload")
    review = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (review.get("story_id") != story_id or review.get("episode_id") != story.get("episode_id")
            or review.get("visual_review_approved") is not True):
        raise PermissionError("No explicit visual-review approval for this exact episode")
    images = story.get("assets", {}).get("images", [])
    checks = review.get("images", [])
    if not isinstance(images, list) or not 6 <= len(images) <= 8:
        raise ValueError("Story must have 6-8 images")
    if not isinstance(checks, list) or len(checks) != len(images):
        raise PermissionError("Review must enumerate EVERY image, in the same order")
    for i, (scene, check) in enumerate(zip(images, checks), start=1):
        name = scene.get("file")
        if not isinstance(name, str) or check.get("file") != name:
            raise PermissionError(f"Scene {i}: reviewed file differs from story")
        path = (ROOT / name).resolve()
        if not path.is_relative_to((ROOT / "assets").resolve()) or not path.is_file():
            raise ValueError(f"Scene {i}: image does not exist under assets/")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if not isinstance(check.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", check["sha256"]):
            raise PermissionError(f"Scene {i}: review SHA-256 is missing or malformed")
        if digest != check["sha256"]:
            raise PermissionError(f"Scene {i}: image changed since human review")
    print(f"Visual approval manifest verified: {story_id}, {len(images)} exact scene SHA-256 hashes")
    return review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--story-id", required=True)
    args = parser.parse_args()
    check_approval(args.story, args.manifest, args.story_id)


if __name__ == "__main__":
    main()
