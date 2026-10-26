#!/usr/bin/env python3
"""Upload already-QA-approved Shorts with YouTube Data API v3."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
    if qa.get("story_id") != story.get("story_id"):
        raise RuntimeError("Story ID mismatch between video QA and metadata")
    language = os.environ["UPLOAD_LANGUAGE"]
    if language not in ("zh", "en"):
        raise ValueError("UPLOAD_LANGUAGE must be zh or en")
    video = OUT / f"{language}.mp4"
    if not video.is_file():
        raise FileNotFoundError(video)
    title = story["title_zh" if language == "zh" else "title_en"] + " #Shorts"
    description = (("原創虛構怪談。#午夜異常廣播 #恐怖故事 #Shorts" if language == "zh"
                    else "Original fictional horror short. #MidnightAnomaly #HorrorShorts #Shorts"))
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

if __name__ == "__main__":
    main()
