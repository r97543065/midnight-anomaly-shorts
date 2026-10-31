#!/usr/bin/env python3
"""Post an explicitly approved affiliate disclosure/comment to an existing YouTube video.

This DOES NOT upload videos or change their privacy. YouTube private videos
cannot receive comments; Shorts comment links are not clickable.
OAuth requires youtube.force-ssl (youtube.upload alone is insufficient).
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from product_ads import validate_ad
from upload_youtube import token
from verify_ai_product import verify_selected_product

ROOT = Path(__file__).resolve().parents[1]
CHANNEL_ID = "UCoJaSnd5EybHJEJ47Q5aZdQ"


def comment_text(ad: dict) -> str:
    validate_ad(ad)
    product = ad["product"]
    return ("【商品推廣｜故事後選物】\n"
            + product["name"] + "\n"
            + product["affiliate_url"] + "\n"
            + ad["disclosure"])


def youtube_json(url: str, access_token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method="POST" if body is not None else "GET",
                      headers={"Authorization": "Bearer " + access_token,
                               "Accept": "application/json",
                               "Content-Type": "application/json; charset=UTF-8"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def post_comment(video_id: str, ad: dict, access_token: str, *, channel_id: str = CHANNEL_ID) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Invalid YouTube video ID")
    text = comment_text(ad)
    info = youtube_json(
        "https://www.googleapis.com/youtube/v3/videos?"
        + urlencode({"part": "status,snippet", "id": video_id}),
        access_token)
    found = info.get("items", [])
    if len(found) != 1 or found[0].get("snippet", {}).get("channelId") != channel_id:
        raise ValueError("Video not found in the configured channel")
    privacy = found[0].get("status", {}).get("privacyStatus")
    if privacy not in ("unlisted", "public"):
        raise ValueError("Private videos cannot receive comments; approval and visibility change are separate")
    url = "https://www.googleapis.com/youtube/v3/commentThreads?"
    parameters = {"part": "snippet", "videoId": video_id, "maxResults": "100"}
    # Do not post duplicates on retries. Fail closed if there are too many comments to inspect.
    for _ in range(5):
        old = youtube_json(url + urlencode(parameters), access_token)
        for item in old.get("items", []):
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            if snippet.get("textOriginal", "") == text:
                return "already_present"
        if "nextPageToken" not in old:
            break
        parameters["pageToken"] = old["nextPageToken"]
    else:
        raise ValueError("Too many comments to check for duplicates; inspect manually")
    body = {"snippet": {"channelId": channel_id, "videoId": video_id,
                        "topLevelComment": {"snippet": {"textOriginal": text}}}}
    result = youtube_json(
        "https://www.googleapis.com/youtube/v3/commentThreads?part=snippet",
        access_token, body)
    if not result.get("id"):
        raise RuntimeError("Comment API did not confirm a comment thread ID")
    return result["id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--story-id", required=True)
    parser.add_argument("--job", type=Path, default=Path("jobs/daily-ad-job.json"))
    parser.add_argument("--csv", type=Path, default=Path("data/affiliate/reviewed-products.csv"))
    args = parser.parse_args()
    if os.environ.get("COMMENT_REVIEWED_AND_AUTHORIZED") != "true":
        raise PermissionError("Explicit human approval is required before posting affiliate comments")
    job = json.loads(args.job.read_text(encoding="utf-8"))
    if job.get("story_id") != args.story_id:
        raise ValueError("Story ID does not match reviewed daily job")
    ad = job.get("product_ad", {})
    if not ad.get("enabled") or ad.get("story_id") != args.story_id:
        raise ValueError("No matching approved-for-preview product ad in daily job")
    verify_selected_product(ad, args.csv)
    print("Comment result:", post_comment(args.video_id, ad, token()))


if __name__ == "__main__":
    main()
