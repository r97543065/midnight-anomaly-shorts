#!/usr/bin/env python3
"""Upload already-QA-approved Shorts with YouTube Data API v3."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from product_ads import ad_for_language, description_suffix, validate_offer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

def post(url, data, headers=None):
    req = Request(url, data=data, headers=headers or {}, method="POST")
    with urlopen(req, timeout=120) as response:
        return json.load(response)

def token():
    required = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError("Missing GitHub secrets: " + ", ".join(missing))
    body = urlencode({
        "client_id": os.environ["YOUTUBE_CLIENT_ID"],
        "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    return post("https://oauth2.googleapis.com/token", body,
                {"Content-Type": "application/x-www-form-urlencoded"})["access_token"]

def main():
    qa = json.loads((OUT / "production-status.json").read_text(encoding="utf-8"))
    if qa.get("qa_status") != "success" or qa.get("errors") or qa.get("warnings"):
        raise RuntimeError("Refusing upload: production QA is not clean SUCCESS")
    story = json.loads(Path(os.environ["STORY_FILE"]).read_text(encoding="utf-8"))
    if qa.get("story_id") and qa.get("story_id") != story.get("story_id"):
        raise RuntimeError("Story ID mismatch between video QA and metadata")
    language = os.environ["UPLOAD_LANGUAGE"]
    if language not in ("zh", "en"):
        raise ValueError("UPLOAD_LANGUAGE must be zh or en")
    video = OUT / f"{language}.mp4"
    if not video.is_file():
        raise FileNotFoundError(video)
    title, description = publishing_text(story, language, qa)
    metadata = {
        "snippet": {"title": title[:100], "description": description,
                    "categoryId": "24", "defaultLanguage": "zh-TW" if language == "zh" else "en"},
        "status": {"privacyStatus": os.environ.get("YOUTUBE_PRIVACY", "private"),
                   "selfDeclaredMadeForKids": False}
    }
    access_token = token()
    boundary = "midnight_upload_boundary"
    file_bytes = video.read_bytes()
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + json.dumps(metadata, ensure_ascii=False).encode()
            + f"\r\n--{boundary}\r\nContent-Type: video/mp4\r\n\r\n".encode()
            + file_bytes + f"\r\n--{boundary}--\r\n".encode())
    result = post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status",
                  body, {"Authorization": f"Bearer {access_token}",
                         "Content-Type": f"multipart/related; boundary={boundary}"})
    print("Uploaded video ID:", result["id"])
    print("URL: https://www.youtube.com/watch?v=" + result["id"])


def publishing_text(story, language, qa):
    publishing = story.get("youtube", {})
    title = publishing.get(f"title_{language}") or story[f"title_{language}"] + " #Shorts"
    description = publishing.get(f"description_{language}") or (
        "原創虛構怪談。#午夜異常廣播 #恐怖故事 #Shorts" if language == "zh"
        else "Original fictional horror short. #MidnightAnomaly #HorrorShorts #Shorts")
    ad_data = dict(story)
    if os.environ.get("DAILY_AD_JOB_FILE"):
        from ai_ad_job import apply_job
        ad_data = apply_job(ad_data, Path(os.environ["DAILY_AD_JOB_FILE"]))
    elif os.environ.get("PRODUCT_AD_FILE"):
        ad_data["product_ad"] = json.loads(Path(os.environ["PRODUCT_AD_FILE"]).read_text(encoding="utf-8"))
    # Match the *rendered* historical artifact even if the offer has since expired.
    # Never silently replace or omit a link from an already-rendered product card.
    ad = ad_for_language(ad_data, language, historical_snapshot=True)
    rendered = qa.get("product_ad", {})
    if language == "zh" and bool(ad) != bool(rendered.get("enabled")):
        raise ValueError("Product ad metadata does not match rendered video QA")
    if ad:
        if rendered.get("product_id") != ad["product"]["id"] or rendered.get("affiliate_url") != ad["product"]["affiliate_url"]:
            raise ValueError("Product link does not match rendered product; refusing upload")
        if rendered.get("verified_at") != ad["product"]["verified_at"]:
            raise ValueError("Offer verification snapshot differs from rendered artifact")
        try:
            validate_offer(ad["product"])  # Expiry, timestamp validity and eligibility still gate upload.
        except ValueError as exc:
            raise ValueError("Offer expired or timestamps invalid: refuse upload; correct and rebuild the same ad, never silently switch its link") from exc
        description += description_suffix(ad)
    if len(description) > 5000:
        raise ValueError("YouTube description exceeds 5000 characters")
    return title, description

if __name__ == "__main__":
    main()
